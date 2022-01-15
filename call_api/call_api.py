import os
import os.path
import re
import json
import boto3
# from urllib.parse import urlencode
# import urllib3, ssl



def lambda_handler(event, context):

    # for testing, copy the object to another s3 bucket
    # print(json.dumps(event))

    # dynamo resource


    s3 = boto3.resource('s3')
    event_client = boto3.client('events')
    lambda_arn = context.invoked_function_arn

    for sns_record in event.get('Records', []):
        message = sns_record['Sns']['Message']
        loaded = json.loads(message)
        for s3_record in loaded['Records']:
            # print(json.dumps(s3_record))

            s3_info = s3_record['s3']
            s3_object = s3.Object(s3_info['bucket']['name'], s3_info['object']['key'])
            etag = s3_info['object']['eTag']
            # be careful of hardcoded partition
            # s3_arn = 'arn:aws:s3:::' + s3_object.bucket_name + '/' + s3_object.key

            # look up this object in the dynamo cache. if found, continue to next iteration

            # do the API thing

            #  copy to some other bucket

            # determine success, fatal error, or transient failure


            # TESTING cleverness
            filename = os.path.basename(s3_object.key)
            if re.search('fail', filename, re.I):
                api_status = 'failed'
            elif re.search('reject', filename, re.I):
                api_status = 'rejected'
            else:
                api_status = 'succeeded'
            # TESTING cleverness

            detail = {
                "s3Bucket" : s3_object.bucket_name,
                "s3Object" : s3_object.key,
                "status" : [ api_status ]
            }

            status_event = {
                "DetailType" : "API Status",
                'Source' : lambda_arn,
                "Detail" : json.dumps(detail)
            }

            # if success, write the key in dynamo
            #  some combination of bucket name, object key, etag
            #  md5, uuid modules

            try:
                print('sending event')
                print(json.dumps(status_event))
                response = event_client.put_events(Entries = [status_event])

            except event_client.exceptions.InternalException as exc:
                print(f'{exc} - ' + json.dumps(status_event))


    return { "status" : "success" }
