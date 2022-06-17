import boto3
from aws_cdk import (
    aws_iam as iam,
    aws_s3 as s3,
)

from constructs import Construct


class SecureBucket(s3.Bucket):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        trusted_role_names=[],
        trusted_user_names=[],
        **kwargs,
    ):

        super().__init__(scope, construct_id, **kwargs)

        resources = [self.bucket_arn, self.arn_for_objects("")]

        iam_resource = boto3.resource("iam")
        trusted_roles = [iam_resource.Role(name) for name in trusted_role_names]
        trusted_userids = [f"{role.role_id}:*" for role in trusted_roles]

        trusted_users = [iam_resource.User(name) for name in trusted_user_names]
        trusted_userids += [user.user_id for user in trusted_users]

        trusted_userids.append(str(scope.account))

        velvet_rope = iam.PolicyStatement(
            effect=iam.Effect.DENY,
            actions=["s3:*"],
            resources=resources,
            principals=[iam.AnyPrincipal()],
            conditions={"StringNotLike": {"aws:userId": trusted_userids}},
        )

        self.add_to_resource_policy(velvet_rope)
