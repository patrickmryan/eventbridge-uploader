from aws_cdk import (
    Duration,
    Stack,
    CfnParameter, # CfnCondition, Fn,
    aws_iam as iam,
    aws_logs as logs,
    aws_sqs as sqs,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets
)
from constructs import Construct

class UploaderStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        outgoing_bucket_param = CfnParameter(self,
                "OutgoingBucket", type="String",
                description="Bucket for data to be submitted to the API")

        # this still seems wrong. should still be including conditional logic
        # in PermissionBoundary value for each Role.
        # but maybe OK if going to resythesize for each deployment.
        permissions_boundary_policy_param = self.node.try_get_context("PermissionsBoundaryPolicy")
        if permissions_boundary_policy_param:
            permissions_boundary=iam.ManagedPolicy.from_managed_policy_name(self,
                'PermissionsBoundary', permissions_boundary_policy_param)
            iam.PermissionsBoundary.of(self).apply(permissions_boundary)

        outgoing_bucket = s3.Bucket.from_bucket_name(self, "Outgoing",
                outgoing_bucket_param.value_as_string )

        # SNS for notification of new objects
        new_object_topic = sns.Topic(self, "NewObjectTopic")
        topic_policy = sns.TopicPolicy(self,
                    "NewObjectTopicPolicy",
                    topics=[new_object_topic])
        topic_policy.document.add_statements(
                iam.PolicyStatement(
                actions=["sns:Subscribe"],
                principals=[ iam.ServicePrincipal("s3.amazonaws.com") ],
                resources=[new_object_topic.topic_arn]))

        # https://constructs.dev/packages/@aws-cdk/aws-s3/v/1.139.0?lang=python

        outgoing_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.SnsDestination(new_object_topic),
            s3.NotificationKeyFilter(prefix="processed/", suffix=".json") )

        # normal lambda permissions, eventbridge actions, s3 read,write,list, SNS, SQS

        # lambdas
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html

        runtime = _lambda.Runtime.PYTHON_3_8
        log_retention=logs.RetentionDays.ONE_WEEK


        event_bus = events.EventBus.from_event_bus_name(self, "EventBus", "default")

        service_role = iam.Role(self,
            "NewObjectReceivedRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole') ],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["events:PutEvents"],
                            effect=iam.Effect.ALLOW,
                            resources=[event_bus.event_bus_arn]),
                    ]
                )
            ])

        new_object_received_lambda = _lambda.Function(
                self, 'NewObjectReceived',
                runtime=runtime,
                code=_lambda.Code.from_asset('new_object_received'),
                handler='new_object_received.lambda_handler',
                # environment= {
                #     # 'CREDENTIAL' : udl_credential.value_as_string
                # },
                timeout=Duration.seconds(60),
                role=service_role,
                log_retention=log_retention)


        # subscribe the lambda to the topic
        new_object_topic.add_subscription(subscriptions.LambdaSubscription(new_object_received_lambda))

        # call_api

        # role and function for calling the API
        service_role = iam.Role(self,
            "CallApiRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole') ],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[ "s3:GetObject", ],
                            effect=iam.Effect.ALLOW,
                            resources=[
                                self.format_arn(service='s3', region='', account='', resource=outgoing_bucket.bucket_name),
                                self.format_arn(service='s3', region='', account='', resource=outgoing_bucket.bucket_name,
                                    resource_name='*'),
                            ]),
                        iam.PolicyStatement(   # policy for testing purposes
                            actions=[ "s3:PutObject" ],
                            effect=iam.Effect.ALLOW,
                            resources=[
                                self.format_arn(service='s3', region='', account='', resource='uploader*'),
                                self.format_arn(service='s3', region='', account='', resource='uploader*',
                                    resource_name='*'),
                            ]),
                        iam.PolicyStatement(
                            actions=["events:PutEvents"],
                            effect=iam.Effect.ALLOW,
                            resources=[event_bus.event_bus_arn]),
                    ]
                )
            ])

        call_api_lambda = _lambda.Function(
                self, 'CallApi',
                runtime=runtime,
                code=_lambda.Code.from_asset('call_api'),
                handler='call_api.lambda_handler',
                # environment= {
                #     # 'CREDENTIAL' : udl_credential.value_as_string
                # },
                timeout=Duration.seconds(60),
                role=service_role,
                log_retention=log_retention)

        # # subscribe the lambda to the topic
        # new_object_topic.add_subscription(subscriptions.LambdaSubscription(call_api_lambda))

        # role and function for the "succeeded" case
        service_role = iam.Role(self,
            "ApiSucceededRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole') ],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["s3:GetObject", "s3:PutObject"],
                            effect=iam.Effect.ALLOW,
                            resources=[outgoing_bucket.bucket_arn]),
                        # iam.PolicyStatement(
                        #     actions=["events:PutEvents"],
                        #     effect=iam.Effect.ALLOW,
                        #     resources=[event_bus.event_bus_arn]),
                    ]
                )
            ])

        api_succeeded_lambda = _lambda.Function(
                self, 'ApiSucceded',
                runtime=runtime,
                code=_lambda.Code.from_asset('api_succeeded'),
                handler='api_succeeded.lambda_handler',
                timeout=Duration.seconds(60),
                role=service_role,
                log_retention=log_retention)

        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events_targets/README.html#invoke-a-lambda-function
        succeeded_rule = events.Rule(self, "ApiSucceededRule",
                event_pattern=events.EventPattern(
                    detail_type=["API Status"],
                    source=[ call_api_lambda.function_arn ],
                    detail={
                        "Bucket" : [ outgoing_bucket.bucket_name ],
                        "status" : [ "succeeded" ]
                    }),
                targets = [ targets.LambdaFunction(api_succeeded_lambda) ])

        # create a Q for retrying failed calls
        retry_queue = sqs.Queue(
            self, "RetryQueue",
            retention_period=Duration.days(2),
            visibility_timeout=Duration.seconds(60))

        # role and function for the "failed" case
        service_role = iam.Role(self,
            "ApiFailedRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole') ],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["sqs:SendMessage"],
                            effect=iam.Effect.ALLOW,
                            resources=[retry_queue.queue_arn]),
                    ]
                )
            ])

        api_failed_lambda = _lambda.Function(
                self, 'ApiFailed',
                runtime=runtime,
                code=_lambda.Code.from_asset('api_failed'),
                handler='api_failed.lambda_handler',
                environment= {
                    'QUEUE_URL' : retry_queue.queue_url
                },
                timeout=Duration.seconds(60),
                role=service_role,
                log_retention=log_retention)

        failed_rule = events.Rule(self, "ApiFailedRule",
                event_pattern=events.EventPattern(
                    detail_type=["API Status"],
                    source=[ call_api_lambda.function_arn ],
                    detail={
                        "Bucket" : [ outgoing_bucket.bucket_name ],
                        "status" : [ "failed" ]
                    }),
                targets = [ targets.LambdaFunction(api_failed_lambda) ])

        # handle retries
        service_role = iam.Role(self,
            "HandleRetriesRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole') ],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["sqs:SendMessage", "sqs:ReceiveMessage"],
                            effect=iam.Effect.ALLOW,
                            resources=[retry_queue.queue_arn]) ] ) ])

        handle_retries_lambda = _lambda.Function(
                self, 'HandleRetries',
                runtime=runtime,
                code=_lambda.Code.from_asset('handle_retries'),
                handler='handle_retries.lambda_handler',
                environment= {
                    'QUEUE_URL' : retry_queue.queue_url
                },
                timeout=Duration.seconds(60),
                role=service_role,
                log_retention=log_retention)

        new_object_received_rule = events.Rule(self, "NewObjectReceivedRule",
                event_pattern=events.EventPattern(
                    detail_type=["API Status"],
                    source=[
                        new_object_received_lambda.function_arn,
                        handle_retries_lambda.function_arn
                    ],
                    detail={
                        "Bucket" : [ outgoing_bucket.bucket_name ],
                        "status" : [ "new_object_received" ]
                    }),
                targets = [ targets.LambdaFunction(call_api_lambda) ])

        # rule to run handle_retries onc per minute
