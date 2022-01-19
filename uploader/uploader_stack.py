from aws_cdk import (
    Duration,
    Stack,
    CfnParameter,
    region_info,
    aws_iam as iam,
    aws_logs as logs,
    aws_sqs as sqs,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
)

# from aws_cdk.region_info import RegionInfo
from constructs import Construct


class UploaderStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        outgoing_bucket_param = CfnParameter(
            self,
            "OutgoingBucket",
            type="String",
            description="Bucket for data to be submitted to the API",
        )

        permissions_boundary_policy_param = self.node.try_get_context(
            "PermissionsBoundaryPolicy"
        )
        if permissions_boundary_policy_param:
            permissions_boundary = iam.ManagedPolicy.from_managed_policy_name(
                self, "PermissionsBoundary", permissions_boundary_policy_param
            )
            iam.PermissionsBoundary.of(self).apply(permissions_boundary)

        outgoing_bucket = s3.Bucket.from_bucket_name(
            self,
            "Outgoing",
            outgoing_bucket_param.value_as_string,
            # event_bridge_enabled=True
        )

        # standard service principals
        # this_region = Stack.of(self).region
        # region = region_info.RegionInfo.get(Stack.of(self).region)
        # s3_principal = region.service_principal('s3.amazonaws.com')

        # s3_principal     = region.service_principal(service='s3.amazonaws.com')
        # lambda_principal = region_info.RegionInfo.service_principal(service='lambda')

        # lambdas
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html

        # setting for all python Lambda functions
        runtime = _lambda.Runtime.PYTHON_3_8
        log_retention = logs.RetentionDays.ONE_WEEK

        event_bus = events.EventBus.from_event_bus_name(self, "EventBus", "default")
        basic_lambda_policy = iam.ManagedPolicy.from_aws_managed_policy_name(
            "service-role/AWSLambdaBasicExecutionRole"
        )

        # several roles need read access to the bucket
        bucket_resources = [
            # access to the bucket
            self.format_arn(
                service="s3",
                region="",
                account="",
                resource=outgoing_bucket.bucket_name,
            ),
            # access to objects
            self.format_arn(
                service="s3",
                region="",
                account="",
                resource=outgoing_bucket.bucket_name,
                resource_name="*",
            ),
        ]

        bucket_read_policy = iam.PolicyStatement(
            actions=["s3:GetObject"],
            effect=iam.Effect.ALLOW,
            resources=bucket_resources,
        )

        service_role = iam.Role(
            self,
            "NewObjectReceivedRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        bucket_read_policy,
                        iam.PolicyStatement(
                            actions=["events:PutEvents"],
                            effect=iam.Effect.ALLOW,
                            resources=[event_bus.event_bus_arn],
                        ),
                    ]
                )
            ],
        )

        new_object_received_lambda = _lambda.Function(
            self,
            "NewObjectReceived",
            runtime=runtime,
            code=_lambda.Code.from_asset("new_object_received"),
            handler="new_object_received.lambda_handler",
            timeout=Duration.seconds(60),
            role=service_role,
            log_retention=log_retention,
        )

        # rule for receiving events when PutObject happens
        # https://docs.aws.amazon.com/AmazonS3/latest/userguide/ev-events.html
        # https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns-content-based-filtering.html

        prefix = "processed/"  # for testing
        put_object_rule = events.Rule(
            self,
            "OutgoingPutObject",
            event_pattern=events.EventPattern(
                detail_type=["Object Created"],
                source=["aws.s3"],
                resources=[outgoing_bucket.bucket_arn],
                detail={"object": {"key": [{"prefix": prefix}]}},
            ),
            targets=[targets.LambdaFunction(new_object_received_lambda)],
        )

        # role and function for calling the API
        service_role = iam.Role(
            self,
            "CallApiRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        bucket_read_policy,
                        iam.PolicyStatement(  # policy for testing purposes
                            actions=["s3:PutObject"],
                            effect=iam.Effect.ALLOW,
                            resources=[
                                self.format_arn(
                                    service="s3",
                                    region="",
                                    account="",
                                    resource="uploader*",
                                ),
                                self.format_arn(
                                    service="s3",
                                    region="",
                                    account="",
                                    resource="uploader*",
                                    resource_name="*",
                                ),
                            ],
                        ),
                        iam.PolicyStatement(
                            actions=["events:PutEvents"],
                            effect=iam.Effect.ALLOW,
                            resources=[event_bus.event_bus_arn],
                        ),
                    ]
                )
            ],
        )

        call_api_lambda = _lambda.Function(
            self,
            "CallApi",
            runtime=runtime,
            code=_lambda.Code.from_asset("call_api"),
            handler="call_api.lambda_handler",
            # environment= {
            #     # 'CREDENTIAL' : udl_credential.value_as_string
            # },
            timeout=Duration.seconds(60),
            role=service_role,
            log_retention=log_retention,
        )

        # create a Q for retrying failed calls
        retry_queue = sqs.Queue(
            self,
            "RetryQueue",
            retention_period=Duration.days(2),
            visibility_timeout=Duration.seconds(60),
        )

        service_role = iam.Role(
            self,
            "DeleteMessageRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["sqs:DeleteMessage"],
                            effect=iam.Effect.ALLOW,
                            resources=[retry_queue.queue_arn],
                        )
                    ]
                )
            ],
        )

        delete_message_lambda = _lambda.Function(
            self,
            "DeleteMessage",
            runtime=runtime,
            code=_lambda.Code.from_asset("delete_message"),
            handler="delete_message.lambda_handler",
            timeout=Duration.seconds(60),
            role=service_role,
            log_retention=log_retention,
        )

        delete_message_rule = events.Rule(
            self,
            "DeleteMessageRule",
            event_pattern=events.EventPattern(
                detail_type=["API Status"],
                source=[call_api_lambda.function_arn],
                detail={
                    "Bucket": [outgoing_bucket.bucket_name],
                    "status": ["succeeded"],
                    "message": {"queue_url": [{"exists": True}]},
                },
            ),
            targets=[targets.LambdaFunction(delete_message_lambda)],
        )

        service_role = iam.Role(
            self,
            "DeleteObjectRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["s3:DeleteObject"],
                            effect=iam.Effect.ALLOW,
                            resources=bucket_resources,
                        )
                    ]
                )
            ],
        )

        delete_object_lambda = _lambda.Function(
            self,
            "DeleteObject",
            runtime=runtime,
            code=_lambda.Code.from_asset("delete_object"),
            handler="delete_object.lambda_handler",
            timeout=Duration.seconds(60),
            role=service_role,
            log_retention=log_retention,
        )

        delete_object_rule = events.Rule(
            self,
            "DeleteObjectRule",
            event_pattern=events.EventPattern(
                detail_type=["API Status"],
                source=[call_api_lambda.function_arn],
                detail={
                    "Bucket": [outgoing_bucket.bucket_name],
                    "status": ["succeeded"],
                },
            ),
            targets=[targets.LambdaFunction(delete_object_lambda)],
        )

        # role and function for the "failed" case
        service_role = iam.Role(
            self,
            "SendToRetryQueueRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["sqs:SendMessage"],
                            effect=iam.Effect.ALLOW,
                            resources=[retry_queue.queue_arn],
                        )
                    ]
                )
            ],
        )

        send_to_retry_queue_lambda = _lambda.Function(
            self,
            "SendToRetryQueue",
            runtime=runtime,
            code=_lambda.Code.from_asset("send_to_retry_queue"),
            handler="send_to_retry_queue.lambda_handler",
            environment={"QUEUE_URL": retry_queue.queue_url},
            timeout=Duration.seconds(60),
            role=service_role,
            log_retention=log_retention,
        )

        failed_rule = events.Rule(
            self,
            "ApiFailedRule",
            event_pattern=events.EventPattern(
                detail_type=["API Status"],
                source=[call_api_lambda.function_arn],
                detail={
                    "Bucket": [outgoing_bucket.bucket_name],
                    "status": ["failed"],
                    # next rule ensures that a failed API call results
                    # in exactly one message being put in the Q.
                    "message": {"queue_url": [{"exists": False}]},
                },
            ),
            targets=[targets.LambdaFunction(send_to_retry_queue_lambda)],
        )

        # handle retries
        service_role = iam.Role(
            self,
            "HandleRetriesRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["sqs:ReceiveMessage"],  # "sqs:SendMessage",
                            effect=iam.Effect.ALLOW,
                            resources=[retry_queue.queue_arn],
                        ),
                        iam.PolicyStatement(
                            actions=["events:PutEvents"],
                            effect=iam.Effect.ALLOW,
                            resources=[event_bus.event_bus_arn],
                        ),
                    ]
                )
            ],
        )

        handle_retries_lambda = _lambda.Function(
            self,
            "HandleRetries",
            runtime=runtime,
            code=_lambda.Code.from_asset("handle_retries"),
            handler="handle_retries.lambda_handler",
            environment={"QUEUE_URL": retry_queue.queue_url},
            timeout=Duration.seconds(60),
            role=service_role,
            log_retention=log_retention,
        )

        ready_for_api_rule = events.Rule(
            self,
            "ReadyForApiRule",
            event_pattern=events.EventPattern(
                detail_type=["API Status"],
                source=[
                    new_object_received_lambda.function_arn,
                    handle_retries_lambda.function_arn,
                ],
                detail={
                    "Bucket": [outgoing_bucket.bucket_name],
                    "status": ["ready_for_api"],
                },
            ),
            targets=[targets.LambdaFunction(call_api_lambda)],
        )

        # rule to run handle_retries once per minute
        handle_retries_rule = events.Rule(
            self,
            "HandleRetriesRule",
            enabled=False,
            schedule=events.Schedule.rate(Duration.minutes(1)),
            targets=[targets.LambdaFunction(handle_retries_lambda)],
        )
