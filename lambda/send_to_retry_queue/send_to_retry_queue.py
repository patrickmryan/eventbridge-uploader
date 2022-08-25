import os
import json
import boto3


def lambda_handler(event, context):

    print(json.dumps(event))

    key = "QUEUE_URL"
    queue_url = os.environ.get(key)
    if not queue_url:
        print(f"missing value for {key}")
        return {"status": "failed"}

    sqs = boto3.resource("sqs")
    retry_queue = sqs.Queue(queue_url)

    try:
        response = retry_queue.send_message(MessageBody=json.dumps(event))
        print(json.dumps(response))
    except sqs.meta.client.exceptions.InvalidMessageContents as exc:
        print(exc)

    return {"status": "message_sent"}
