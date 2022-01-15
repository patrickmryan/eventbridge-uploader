import os
import json
import boto3
# from urllib.parse import urlencode
# import urllib3, ssl



def lambda_handler(event, context):

    # for testing, copy the object to another s3 bucket
    # print(json.dumps(event))

    s3 = boto3.resource('s3')
    event_client = boto3.client('events')
    # arn:aws:lambda:us-east-1:458358814065:function:UploaderStack-InvokeApi313C8B49-vesKaS0k2oYp
    lambda_arn = context.invoked_function_arn

    for sns_record in event.get('Records', []):
        message = sns_record['Sns']['Message']
        loaded = json.loads(message)
        for s3_record in loaded['Records']:
            # print(json.dumps(s3_record))

            s3_info = s3_record['s3']
            s3_object = s3.Object(s3_info['bucket']['name'], s3_info['object']['key'])
            s3_arn = 'arn:aws:s3:::' + s3_object.bucket_name + '/' + s3_object.key
            # print(s3_object)

            # do the API thing
            # determine success, fatal error, or transient failure

            detail = {
                "status" : "success"
            }

            status_event = {
                'Source' : "",
                'Resources' : [ lambda_arn, s3_arn ],
                # "DetailType" :
                "Detail" : detail   #json.dumps(detail)
            }

            try:
                print('sending event')
                print(json.dumps(status_event))
                response = event_client.put_events(Entries = [status_event])

            except event_client.exceptions.InternalException as exc:
                print(f'{exc} - ' + json.dumps(status_event))


    return { "status" : "success" }
