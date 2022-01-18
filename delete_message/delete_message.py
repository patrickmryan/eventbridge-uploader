import os
import json
import boto3


def lambda_handler(event, context):

    print(json.dumps(event))

    event_detail = event['detail']
    message_data = event_detail.get('message')
    if not message_data:
        print('no message found in event')
        return { "status" : 'failed' }

    sqs = boto3.resource('sqs')

    # delete message from Q
    message = sqs.Message(message_data['queue_url'], message_data['receipt_handle'])

    try:
        message.delete()
        status = 'succeeded'
    except sqs.meta.client.exceptions.ClientError as exc:
        status = 'failed'
        print(f'{message} - {exc}')

    return { "status" : status }
