import os
import os.path
import re
import json
from datetime import datetime, timezone
import boto3

TEST_BUCKET='uploader-incoming-test'

# class ApiResult():
#     def event_detail(self, event=None):
#         pass
#
# class Succeeded(ApiResult):
#     pass


def lambda_handler(event, context):

    # for testing, copy the object to another s3 bucket
    print(json.dumps(event))
    event_detail = event['detail']

    s3 = boto3.resource('s3')
    s3_client = s3.meta.client
    event_client = boto3.client('events')
    sqs = boto3.resource('sqs')
    lambda_arn = context.invoked_function_arn

    # begin TESTING cleverness

    target_bucket = s3.Bucket(TEST_BUCKET)
    s3_object = s3.Object(event_detail["Bucket"], event_detail["Key"])
    last_modified = datetime.fromisoformat(event_detail["LastModified"])
    now = datetime.now(timezone.utc)
    elapsed_seconds = (now - last_modified).total_seconds()

    filename = os.path.basename(s3_object.key)
    if re.search('fail', filename, re.I) and elapsed_seconds < 180:
        # after 180 seconds, let the transfer succeed
        api_status = 'failed'
    elif re.search('reject', filename, re.I):
        api_status = 'rejected'
    else:
        api_status = 'succeeded'

    if api_status == 'succeeded':
        try:
            new_object = target_bucket.Object(f'copied/{s3_object.key}')
            new_object.copy({ 'Bucket' : s3_object.bucket_name, 'Key' : s3_object.key })

        except s3_client.exceptions.ClientError as exc:
            print(f'error copying {s3_object} to {target_bucket} - {exc}')
            api_status = 'failed'

    # end TESTING cleverness

    detail = event_detail.copy()
    detail['status'] = [ api_status ]

    status_event = {
        "DetailType" : "API Status",
        "Source" : lambda_arn,
        "Detail" : json.dumps(detail)
    }

    try:
        print('sending event')
        print(json.dumps(status_event))
        response = event_client.put_events(Entries = [status_event])

    except event_client.exceptions.InternalException as exc:
        print(f'{exc} - ' + json.dumps(status_event))

    return { "status" : "success" }
