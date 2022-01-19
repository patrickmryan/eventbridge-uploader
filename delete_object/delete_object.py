import os
import json
import boto3


def lambda_handler(event, context):

    print(json.dumps(event))

    s3 = boto3.resource("s3")
    s3_client = s3.meta.client

    event_detail = event["detail"]

    # delete the object from the originating bucket
    s3_object = s3.Object(event_detail["Bucket"], event_detail["Key"])

    try:
        s3_object.delete()
        status = "succeeded"

    except s3_client.exceptions.ClientError as exc:
        print(f"error deleting {s3_object} - {exc}")
        status = "failed"

    return {"status": status}
