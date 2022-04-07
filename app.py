#!/usr/bin/env python3
import os

import aws_cdk as cdk

# from constructs import Construct
# from aws_cdk import aws_iam as iam

from uploader.uploader_stack import UploaderStack

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
)

app = cdk.App()
stack = UploaderStack(app, "UploaderStack", env=env)
app.synth()
