import os
import json
import boto3

def lambda_handler(event, context):

    print(json.dumps(event))

    queue_url = os.environ.get('QUEUE_URL')
    sqs = boto3.resource('sqs')
    retry_queue = sqs.Queue(queue_url)

    response = None
    try:
        response = retry_queue.send_message(MessageBody=json.dumps(event))
    except sqs.meta.client.exceptions.InvalidMessageContents as exc:
        print(exc)

    print(json.dumps(response))

    return { "status" : "failed" }
