import os
import json
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
    sqs = boto3.resource('sqs')
    retry_queue = sqs.Queue(queue_url)
