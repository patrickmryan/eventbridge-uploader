from aws_cdk import (
    Duration,
    Stack,
    Tags,
    CfnOutput,
    RemovalPolicy,
    aws_iam as iam,
    aws_logs as logs,
    aws_sqs as sqs,
    aws_s3 as s3,
    aws_kms as kms,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_apigateway as apigw,
)

from constructs import Construct


class UploaderStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        permissions_boundary_policy_arn = self.node.try_get_context(
            "PermissionsBoundaryPolicyArn"
        )
        if permissions_boundary_policy_arn:
            policy = (
                iam.ManagedPolicy.from_managed_policy_arn(  #   from_managed_policy_name
                    self, "PermissionsBoundary", permissions_boundary_policy_arn
                )
            )
            iam.PermissionsBoundary.of(self).apply(policy)

        Tags.of(self).add("TESTTAG", "testvalue")

        # If debugging is enabled, set up a dict with an environment variable in Lambda.
        debug_env = {}
        debug_param_value = self.node.try_get_context("EnableDebug")
        if debug_param_value and debug_param_value.lower() == "true":
            debug_env["DEBUG"] = "true"

        # if a KMS key name is provided, enable bucket encryption
        kms_key_alias = self.node.try_get_context("KmsKeyAlias")
        if kms_key_alias:
            kms_params = {
                "encryption": s3.BucketEncryption.KMS,
                "bucket_key_enabled": True,
                "encryption_key": kms.Key.from_lookup(
                    self, "KmsS3Key", alias_name=kms_key_alias
                ),
            }
        else:
            kms_params = {}

        inbound_bucket = s3.Bucket(
            self,
            "Inbound",
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY,
            event_bridge_enabled=True,
            **kms_params
        )
        outbound_bucket = s3.Bucket(
            self,
            "Outbound",
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY,
            **kms_params
        )

        # setting for all python Lambda functions
        runtime = _lambda.Runtime.PYTHON_3_8
        log_retention = logs.RetentionDays.ONE_WEEK
        lambda_principal = iam.ServicePrincipal("lambda.amazonaws.com")

        event_bus = events.EventBus.from_event_bus_name(self, "EventBus", "default")
        basic_lambda_policy = iam.ManagedPolicy.from_aws_managed_policy_name(
            "service-role/AWSLambdaBasicExecutionRole"
        )

        allow_read_inbound_bucket_read = iam.PolicyStatement(
            actions=["s3:GetObject", "s3:GetObjectTagging"],
            effect=iam.Effect.ALLOW,
            resources=[
                inbound_bucket.bucket_arn,
                inbound_bucket.arn_for_objects("*"),
            ],
        )

        service_role = iam.Role(
            self,
            "NewObjectReceivedRole",
            assumed_by=lambda_principal,
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    assign_sids=True,
                    statements=[
                        allow_read_inbound_bucket_read,
                        iam.PolicyStatement(
                            actions=["events:PutEvents"],
                            effect=iam.Effect.ALLOW,
                            resources=[event_bus.event_bus_arn],
                        ),
                    ],
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
        # there is no event pattern syntax for matching on suffix. would have to do this in code if necessary.

        detail_type = "API Status"

        put_object_rule = events.Rule(
            self,
            "NewObjectInBucketRule",
            event_pattern=events.EventPattern(
                detail_type=["Object Created"],
                source=["aws.s3"],
                resources=[inbound_bucket.bucket_arn],
                detail={"object": {"key": [{"prefix": prefix}]}},
            ),
            targets=[targets.LambdaFunction(new_object_received_lambda)],
        )

        # role and function for calling the API
        service_role = iam.Role(
            self,
            "TestApiRole",
            assumed_by=lambda_principal,
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    assign_sids=True,
                    statements=[
                        allow_read_inbound_bucket_read,
                        iam.PolicyStatement(
                            actions=["s3:PutObject", "s3:PutObjectTagging"],
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
                    ],
                )
            ],
        )

        test_api_lambda = _lambda.Function(
            self,
            "TestApi",
            runtime=runtime,
            code=_lambda.Code.from_asset("test_api"),
            handler="test_api.lambda_handler",
            environment={**debug_env, "OUTBOUND_BUCKET": outbound_bucket.bucket_name},
            timeout=Duration.seconds(60),
            role=service_role,
            log_retention=log_retention,
        )

        # add API gw
        test_api = apigw.LambdaRestApi(self, "RestApi", handler=test_api_lambda)

        items = test_api.root.add_resource("submit")
        items.add_method("POST", apigw.LambdaIntegration(test_api_lambda))

        # test_api = apigw.RestApi(
        #     self,
        #     "RestApi",
        #     endpoint_configuration=apigw.EndpointConfiguration(
        #         types=[apigw.EndpointType.PRIVATE]
        #     ),  # EDGE
        #     # default_integration=apigw.LambdaIntegration(
        #     #     # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_apigateway/LambdaIntegration.html
        #     #     test_api_lambda,
        #     #     # content_handling
        #     #     # request_parameters
        #     #     # vpc_link
        #     # ),
        #     deploy=True,
        # )

        # test_api.root.add_method("POST",
        #     apigw.LambdaIntegration(
        #         # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_apigateway/LambdaIntegration.html
        #         test_api_lambda,
        #         # content_handling
        #         # request_parameters
        #         # vpc_link
        #     ),
        # )

        # . maybe. might be automagic.
        # test_api_lambda.add_permission(
        #     "ApiGwCallTestApi",
        #     principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
        #     # source_arn=test_api.arn
        # )

        # role and function for calling the API
        service_role = iam.Role(
            self,
            "CallApiRole",
            assumed_by=lambda_principal,
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    assign_sids=True,
                    statements=[
                        allow_read_inbound_bucket_read,
                        iam.PolicyStatement(
                            actions=["s3:PutObject", "s3:PutObjectTagging"],
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
                    ],
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
            assumed_by=lambda_principal,
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    assign_sids=True,
                    statements=[
                        iam.PolicyStatement(
                            actions=["sqs:DeleteMessage"],
                            effect=iam.Effect.ALLOW,
                            resources=[retry_queue.queue_arn],
                        )
                    ],
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
                detail_type=[detail_type],
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
            assumed_by=lambda_principal,
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    assign_sids=True,
                    statements=[
                        iam.PolicyStatement(
                            actions=["s3:DeleteObject"],
                            effect=iam.Effect.ALLOW,
                            resources=[
                                inbound_bucket.bucket_arn,
                                inbound_bucket.arn_for_objects("*"),
                            ],
                        )
                    ],
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
                detail_type=[detail_type],
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
            assumed_by=lambda_principal,
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    assign_sids=True,
                    statements=[
                        iam.PolicyStatement(
                            actions=["sqs:SendMessage"],
                            effect=iam.Effect.ALLOW,
                            resources=[retry_queue.queue_arn],
                        )
                    ],
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
                detail_type=[detail_type],
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
            assumed_by=lambda_principal,
            managed_policies=[basic_lambda_policy],
            inline_policies=[
                iam.PolicyDocument(
                    assign_sids=True,
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
                    ],
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
                detail_type=[detail_type],
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

        # addToResourcePolicy()?
        inbound_bucket.grant_read(call_api_lambda.role)
        inbound_bucket.grant_read(new_object_received_lambda.role)
        inbound_bucket.grant_delete(delete_object_lambda.role)
        outbound_bucket.grant_put(call_api_lambda.role)
        # need explicit deny for none-of-the-above

        CfnOutput(self, "InboundBucket", value=inbound_bucket.bucket_name)
        CfnOutput(self, "OutboundBucket", value=outbound_bucket.bucket_name)
