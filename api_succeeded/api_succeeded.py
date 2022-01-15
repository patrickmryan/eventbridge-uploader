import os
import json
import boto3
# from urllib.parse import urlencode
# import urllib3, ssl



def lambda_handler(event, context):

    print(json.dumps(event))

    return { "status" : "success" }
