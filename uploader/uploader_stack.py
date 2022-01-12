from aws_cdk import (
    Duration,
    Stack,
    CfnParameter,
    aws_iam as iam,
    aws_sqs as sqs,
    aws_sns as sns,
    aws_lambda as _lambda,
    aws_events as events
)
from constructs import Construct

class UploaderStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # udl_credential = CfnParameter(self,
        #         "UDLcredential", type="String",
        #         description="Access credentials encoded using base64")

        runtime = _lambda.Runtime.PYTHON_3_8

        # need to make boundary policy an optional parameter. update role definitions accordingly.
        permissions_boundary=iam.ManagedPolicy.from_managed_policy_name(self, 'PermissionBoundaryLambda', "T_PROJADMIN_U")
        iam.PermissionsBoundary.of(self).apply(permissions_boundary)


        retry_queue = sqs.Queue(
            self, "RetryQueue",
            visibility_timeout=Duration.seconds(60),
        )

        # SNS for status

        # role(s) for lambdas?

        # normal lambda permissions, eventbridge actions, s3 read,write,list, SNS, SQS

        # lambdas
        # invoke_api

        invoke_api_lambda = _lambda.Function(
                self, 'InvokeApi',
                runtime=runtime,
                code=_lambda.Code.from_asset('invoke_api'),
                handler='invoke_api.lambda_handler',
                environment= {
                    # 'CREDENTIAL' : udl_credential.value_as_string
                },
                # layers = [ pandas_layer ]
                # role=lambda_role
            )




        # event subscriptions
