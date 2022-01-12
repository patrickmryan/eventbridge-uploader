import aws_cdk as core
import aws_cdk.assertions as assertions

from uploader.uploader_stack import UploaderStack

# example tests. To run these tests, uncomment this file along with the example
# resource in uploader/uploader_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = UploaderStack(app, "uploader")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
