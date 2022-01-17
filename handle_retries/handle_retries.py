import os
import json
from datetime import datetime, timedelta
import boto3

def lambda_handler(event, context):

    print(json.dumps(event))

    # https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-basic-architecture.html

    # iterate through receive_messages
    # for each
    #    determine if enough wait time has elapsed
    #      if not, ignore it and continue

    #      in detail for call_api, append message info
    #      think about optimal place to delete message

    queue_url = os.environ.get('QUEUE_URL')
    # sqs = boto3.resource('sqs')
    # sqs_client = sqs.meta.client
    sqs_client = boto3.client('sqs')
    event_client = boto3.client('events')
    lambda_arn = context.invoked_function_arn

    # retry_queue = sqs.Queue(queue_url)

    done= False
    while not done:
        try:
            mesg_dict = sqs_client.receive_message(QueueUrl=queue_url, WaitTimeSeconds=15) ##, VisibilityTimeout=60

        except sqs_client.exceptions.ClientError as exc:
            print(f'{queue_url} - {exc}')
            return


        messages = mesg_dict.get('Messages', [])
        if not messages:
            done = True
            continue  # nothing more to see here

        for message in messages:
            # print(message)

            body = json.loads(message["Body"])
            detail = body['detail']

            # create a new message to send to the event bus
            detail["status"] = [ "new_object_received" ]
            detail["message"] = {
                "queue_url" : queue_url,
                "receipt_handle" : message["ReceiptHandle"]
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

            except event_client.exceptions.InternalException as exc:
                print(f'{exc} - ' + json.dumps(status_event))



    return


if __name__ == '__main__':
    import pdb

    lambda_handler(event={}, context={})

    # "invoked_function_arn":
    #     "arn:aws:lambda:us-east-1:458358814065:function:UploaderStack-HandleRetriesCC180680-4dxbnXpWEBRc"
