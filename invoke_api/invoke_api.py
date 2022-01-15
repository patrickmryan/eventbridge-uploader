import os
import json
import boto3
# from urllib.parse import urlencode
# import urllib3, ssl



def lambda_handler(event, context):

    # for testing, copy the object to another s3 bucket
    print(event)

    return { "status" : "success" }
