from aws_cdk import (
    Duration,
    Stack,
    CfnParameter,
    aws_iam as iam,
    aws_sqs as sqs,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_sns as sns,
    aws_lambda as _lambda,
    aws_events as events
)
from constructs import Construct

class UploaderStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        outgoing_bucket_param = CfnParameter(self,
                "OutgoingBucket", type="String",
                description="Bucket for data to be submitted to the API")

        permissions_boundary_policy_param = CfnParameter(self,
                "PermissionsBoundaryPolicy", type="String",
                description="(optional) Policy to be added as permissions boundary to all IAM roles")


        # need to make boundary policy an optional parameter. update role definitions accordingly.
        # create a conditional object
        permissions_boundary=iam.ManagedPolicy.from_managed_policy_name(self, 'PermissionBoundaryLambda', "T_PROJADMIN_U")
        iam.PermissionsBoundary.of(self).apply(permissions_boundary)

        outgoing_bucket = s3.Bucket.from_bucket_name(self, "Outgoing",
                outgoing_bucket_param.value_as_string )

        # topic

        # buckets
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_s3/Bucket.html


        retry_queue = sqs.Queue(
            self, "RetryQueue",
            visibility_timeout=Duration.seconds(60),
        )

        # SNS for status
        new_object_topic = sns.Topic(self,
                        "NewObjectTopic")
        topic_policy = sns.TopicPolicy(self,
                    "NewObjectTopicPolicy",
                    topics=[new_object_topic])
        topic_policy.document.add_statements(
                iam.PolicyStatement(
                actions=["sns:Subscribe"],
                principals=[
                    iam.ServicePrincipal("s3.amazonaws.com")
                    # iam.AnyPrincipal()
                ],
                resources=[new_object_topic.topic_arn]))

        # https://constructs.dev/packages/@aws-cdk/aws-s3/v/1.139.0?lang=python

        # outgoing_bucket.add_event_notification(
        #     s3.EventType.OBJECT_CREATED,
        #     s3n.SnsDestination(new_object_topic),
        #     s3.NotificationKeyFilter(prefix="processed/*"))

        # role(s) for lambdas?


        # normal lambda permissions, eventbridge actions, s3 read,write,list, SNS, SQS

        # lambdas
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html

        runtime = _lambda.Runtime.PYTHON_3_8

        # invoke_api

        service_role = iam.Role(self,
            "InvokeApiRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole')
            ],
            inline_policies=[
                iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["s3:GetObject"],
                            effect=iam.Effect.ALLOW,
                            resources=[outgoing_bucket.bucket_arn])
                    ]
                )
            ])

        invoke_api_lambda = _lambda.Function(
                self, 'InvokeApi',
                runtime=runtime,
                code=_lambda.Code.from_asset('invoke_api'),
                handler='invoke_api.lambda_handler',
                environment= {
                    # 'CREDENTIAL' : udl_credential.value_as_string
                },
                timeout=Duration.seconds(60),
                # memory_size
                # layers = [ pandas_layer ]
                role=service_role
            )




        # event subscriptions
