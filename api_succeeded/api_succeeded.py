import os
import json
import boto3


def lambda_handler(event, context):

    print(json.dumps(event))

    # delete message from Q, if present

    return { "status" : "success" }
