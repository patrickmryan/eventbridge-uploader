"""
Super important info about call_api.py
"""


import os
import os.path


import re
import json
from datetime import datetime, timezone
import boto3


def lambda_handler(event, context):

    """This method is the lambda event handler

    :param int num1: The first number
    :param int num2: The second number

    :returns: The answer

    :rtype: int
    """

    if "DEBUG" in os.environ:
        print(json.dumps(event))

    event_detail = event["detail"]

    s3 = boto3.resource("s3")
    s3_client = s3.meta.client
    event_client = boto3.client("events")

    # for testing, copy the object to another s3 bucket
    # begin TESTING cleverness

    target_bucket = s3.Bucket(os.environ.get("OUTBOUND_BUCKET"))
    source_object = s3.Object(event_detail["Bucket"], event_detail["Key"])

    last_modified = datetime.fromisoformat(event_detail["LastModified"])
    now = datetime.now(timezone.utc)
    elapsed_seconds = (now - last_modified).total_seconds()

    filename = os.path.basename(source_object.key)
    if re.search("fail", filename, re.I) and elapsed_seconds < 120:
        # after 120 seconds, let the transfer succeed
        api_status = "failed"
    elif re.search("reject", filename, re.I):
        api_status = "rejected"
    else:
        api_status = "succeeded"

    if api_status == "succeeded":
        try:
            target_object = target_bucket.Object(f"copied/{source_object.key}")

            target_object.copy_from(
                CopySource={
                    "Bucket": source_object.bucket_name,
                    "Key": source_object.key,
                },
                TaggingDirective="COPY",
            )

            # need to add ElapsedSeconds tag

            response = s3_client.get_object_tagging(
                Bucket=source_object.bucket_name, Key=source_object.key
            )
            tag_set = response["TagSet"]

            target_object.copy(
                {"Bucket": source_object.bucket_name, "Key": source_object.key}
            )

            tag_set.append({"Key": "ElapsedSeconds", "Value": str(elapsed_seconds)})

            s3_client.put_object_tagging(
                Bucket=target_object.bucket_name,
                Key=target_object.key,
                Tagging={"TagSet": tag_set},
            )

        except s3_client.exceptions.ClientError as exc:
            print(f"error copying {source_object} to {target_bucket} - {exc}")
            return {"status": "failed"}

    # end TESTING cleverness

    detail = event_detail.copy()
    detail["status"] = [api_status]

    status_event = {
        "DetailType": "API Status",
        "Source": context.invoked_function_arn,
        "Detail": json.dumps(detail),
    }

    try:
        print("sending event")
        print(json.dumps(status_event))
        response = event_client.put_events(Entries=[status_event])

    except event_client.exceptions.InternalException as exc:
        print(f"{exc} - " + json.dumps(status_event))

    return {"status": "success"}
