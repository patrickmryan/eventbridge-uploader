import sys
import os
import json
from datetime import datetime, timedelta, timezone
import boto3

def lambda_handler(event, context):

    print(json.dumps(event))

    # https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-basic-architecture.html

    queue_url = os.environ.get('QUEUE_URL')
    sqs = boto3.resource('sqs')
    sqs_client = sqs.meta.client
    # sqs_client = boto3.client('sqs')

    event_client = boto3.client('events')
    lambda_arn = context.invoked_function_arn

    retry_queue = sqs.Queue(queue_url)
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(minutes=1)

    messages_processed = 0
    done= False
    # check context value for time remaining?
    while not done:
        try:
            messages = retry_queue.receive_messages(
        #             VisibilityTimeout=60,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=15)
        except sqs_client.exceptions.ClientError as exc:
            print(f'{queue_url} - {exc}')
            break

        if not messages:
            done = True
            continue

        for message in messages:
            print(message.message_id)
            body = json.loads(message.body)

            detail = (body['detail']).copy()

            # create a new event to send to the event bus
            detail["status"] = [ "new_object_received" ]
            detail["message"] = {
                "queue_url"      : queue_url,
                "receipt_handle" : message.receipt_handle
            }

            status_event = {
                "DetailType" : "API Status",
                "Source" : lambda_arn,
                "Detail" : json.dumps(detail)
            }

            try:
                print('sending event')
                print(json.dumps(status_event))
                response = event_client.put_events(Entries = [status_event])
                messages_processed += 1

            except event_client.exceptions.InternalException as exc:
                print(f'{exc} - ' + json.dumps(status_event))

        done = datetime.now(timezone.utc) >= end_time

    return { "messages_processed" : messages_processed }


if __name__ == '__main__':
    import pdb

    event={}
    # with open(sys.argv[1], 'r') as fp:
    #     event = json.load(fp)

    lambda_handler(event=event, context={})

    # "invoked_function_arn":
    #     "arn:aws:lambda:us-east-1:458358814065:function:UploaderStack-HandleRetriesCC180680-4dxbnXpWEBRc"
