import os
import json
import boto3


def lambda_handler(event, context):

    print(json.dumps(event))

    sqs = boto3.resource('sqs')

    event_detail = event['detail']
    message_data = event_detail.get('message')
    if message_data:
        # delete message from Q, if present
        message = sqs.Message(message_data['queue_url'], message_data['receipt_handle'])

        try:
            message.delete()
        except sqs.meta.client.exceptions.ClientError as exc:
            print(f'{message} - {exc}')

    return { "status" : "success" }
