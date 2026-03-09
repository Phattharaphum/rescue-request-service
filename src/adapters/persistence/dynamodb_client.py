import boto3

from src.shared.config import AWS_REGION, DYNAMODB_ENDPOINT, STAGE


def get_dynamodb_resource():
    kwargs = {"region_name": AWS_REGION}
    if STAGE == "local" and DYNAMODB_ENDPOINT:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT
    return boto3.resource("dynamodb", **kwargs)


def get_dynamodb_client():
    kwargs = {"region_name": AWS_REGION}
    if STAGE == "local" and DYNAMODB_ENDPOINT:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT
    return boto3.client("dynamodb", **kwargs)
