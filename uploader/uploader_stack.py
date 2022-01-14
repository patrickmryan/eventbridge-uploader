from aws_cdk import (
    Duration,
    Stack,
    CfnParameter,
    aws_iam as iam,
    aws_sqs as sqs,
    aws_s3 as s3,
    aws_sns as sns,
    aws_lambda as _lambda,
    aws_events as events
)
from constructs import Construct

class UploaderStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        outgoing_bucket = CfnParameter(self,
                "OutgoingBucket", type="String",
                description="Bucket for data to be submitted to the API")

        permissions_boundary_policy = CfnParameter(self,
                "PermissionsBoundaryPolicy", type="String",
                description="(optional) Policy to be added as permissions boundary to all IAM roles")


        # need to make boundary policy an optional parameter. update role definitions accordingly.
        permissions_boundary=iam.ManagedPolicy.from_managed_policy_name(self, 'PermissionBoundaryLambda', "T_PROJADMIN_U")
        iam.PermissionsBoundary.of(self).apply(permissions_boundary)


        runtime = _lambda.Runtime.PYTHON_3_8

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


        # role(s) for lambdas?


        # normal lambda permissions, eventbridge actions, s3 read,write,list, SNS, SQS

        # lambdas
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html

        # invoke_api

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
                # role=lambda_role
            )




        # event subscriptions
