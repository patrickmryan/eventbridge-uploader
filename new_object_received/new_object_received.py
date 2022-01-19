import os
import os.path
import re
import json
from datetime import datetime, timedelta
import boto3

# from urllib.parse import urlencode
# import urllib3, ssl

def lambda_handler(event, context):

    print(json.dumps(event))

    s3 = boto3.resource('s3')
    event_client = boto3.client('events')

    s3_info = event['detail']

    s3_object = s3.Object(s3_info['bucket']['name'], s3_info['object']['key'])
    detail = {
        "Bucket"       : s3_object.bucket_name,
        "Key"          : s3_object.key,
        "LastModified" : s3_object.last_modified.isoformat(),
        "eTag"         : s3_object.e_tag,
        "status"       : [ "ready_for_api" ]    # [ "new_object_received" ]
    }

    status_event = {
        "DetailType" : "API Status",
        "Source" : context.invoked_function_arn,
        "Detail" : json.dumps(detail)
    }

    # if success, write the key in dynamo
    #  some combination of bucket name, object key, etag
    #  md5, uuid modules

    try:
        print('sending event')
        print(json.dumps(status_event))
        response = event_client.put_events(Entries = [status_event])
        status= "succeeded"

    except event_client.exceptions.InternalException as exc:
        print(f'{exc} - ' + json.dumps(status_event))
        status= "failed"

    return { "status" : status }
