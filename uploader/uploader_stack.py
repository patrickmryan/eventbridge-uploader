from aws_cdk import (
    Duration,
    Stack,
    # CfnParameter,
    CfnOutput,
    RemovalPolicy,
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

        permissions_boundary_policy_param = self.node.try_get_context(
            "PermissionsBoundaryPolicy"
        )
        if permissions_boundary_policy_param:
            permissions_boundary = iam.ManagedPolicy.from_managed_policy_name(
                self, "PermissionsBoundary", permissions_boundary_policy_param
            )
            iam.PermissionsBoundary.of(self).apply(permissions_boundary)

        # If debugging is enabled, set up a dict with an environment variable in Lambda.
        debug_env = {}
        debug_param_value = self.node.try_get_context("EnableDebug")
        if debug_param_value and debug_param_value.lower() == "true":
            debug_env["DEBUG"] = "true"

        inbound_bucket = s3.Bucket(
            self,
            "Inbound",
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY,
            # event_bridge_enabled=True
        )
        outbound_bucket = s3.Bucket(
            self,
            "Outbound",
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # https://docs.aws.amazon.com/cdk/v2/guide/environments.html
        # MyDevStack(app, "dev", env=cdk.Environment(
        #     account=os.environ["CDK_DEFAULT_ACCOUNT"],
        #     region=os.environ["CDK_DEFAULT_REGION"]))

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

        inbound_bucket_read_policy = iam.PolicyStatement(
            actions=["s3:GetObject"],
            effect=iam.Effect.ALLOW,
            resources=[
                inbound_bucket.bucket_arn,
                inbound_bucket.arn_for_objects("*"),
            ],
        )

        service_role = iam.Role(
            self,
            "NewObjectReceivedRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        inbound_bucket_read_policy,
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
            environment={**debug_env},
            timeout=Duration.seconds(60),
            role=service_role,
            log_retention=log_retention,
        )

        # rule for receiving events when PutObject happens
        # https://docs.aws.amazon.com/AmazonS3/latest/userguide/ev-events.html
        # https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns-content-based-filtering.html

        prefix = "processed/"  # for testing
        # there is no event pattern syntax for matching on suffix.
        # would have to do this in code if necessary.

        put_object_rule = events.Rule(
            self,
            "ObjectPutInBucketRule",  # "S3EventPutObject",  # "OutgoingPutObject",
            event_pattern=events.EventPattern(
                detail_type=["Object Created"],
                source=["aws.s3"],
                resources=[inbound_bucket.bucket_arn],
                detail={"object": {"key": [{"prefix": prefix}]}},
            ),
            targets=[targets.LambdaFunction(new_object_received_lambda)],
        )

        # inbound_bucket.add_event_notification(
        #     s3.EventType.OBJECT_CREATED_PUT, #OBJECT_CREATED,
        #     # targets.LambdaFunction(new_object_received_lambda),
        #     s3n.LambdaDestination(new_object_received_lambda), #
        #     s3.NotificationKeyFilter(prefix=prefix, suffix=".json") )

        # role and function for calling the API
        service_role = iam.Role(
            self,
            "CallApiRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        inbound_bucket_read_policy,
                        iam.PolicyStatement(
                            actions=["s3:PutObject"],
                            effect=iam.Effect.ALLOW,
                            resources=[
                                outbound_bucket.bucket_arn,
                                outbound_bucket.arn_for_objects("*"),
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
            environment={**debug_env, "OUTBOUND_BUCKET": outbound_bucket.bucket_name},
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
            environment={**debug_env},
            timeout=Duration.seconds(60),
            role=service_role,
            log_retention=log_retention,
        )

        delete_message_rule = events.Rule(
            self,
            "ApiSucceededMessageRule",
            event_pattern=events.EventPattern(
                detail_type=["API Status"],
                source=[call_api_lambda.function_arn],
                detail={
                    "Bucket": [inbound_bucket.bucket_name],
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
                            resources=[
                                inbound_bucket.bucket_arn,
                                inbound_bucket.arn_for_objects("*"),
                            ],
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
            environment={**debug_env},
            timeout=Duration.seconds(60),
            role=service_role,
            log_retention=log_retention,
        )

        delete_object_rule = events.Rule(
            self,
            "ApiSucceededObjectRule",
            event_pattern=events.EventPattern(
                detail_type=["API Status"],
                source=[call_api_lambda.function_arn],
                detail={
                    "Bucket": [inbound_bucket.bucket_name],
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
            environment={**debug_env, "QUEUE_URL": retry_queue.queue_url},
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
                    "Bucket": [inbound_bucket.bucket_name],
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
                            actions=["sqs:ReceiveMessage"],
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
            environment={**debug_env, "QUEUE_URL": retry_queue.queue_url},
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
                    "Bucket": [inbound_bucket.bucket_name],
                    "status": ["ready_for_api"],
                },
            ),
            targets=[targets.LambdaFunction(call_api_lambda)],
        )

        # rule to run handle_retries once per minute
        handle_retries_rule = events.Rule(
            self,
            "HandleRetriesRule",
            enabled=True,
            schedule=events.Schedule.rate(Duration.minutes(1)),
            targets=[targets.LambdaFunction(handle_retries_lambda)],
        )

        CfnOutput(self, "InboundBucket", value=inbound_bucket.bucket_name)
        CfnOutput(self, "OutboundBucket", value=outbound_bucket.bucket_name)
