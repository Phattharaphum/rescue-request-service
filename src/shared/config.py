import os


STAGE = os.environ.get("STAGE", "local")
AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "RescueRequestTable")
IDEMPOTENCY_TABLE_NAME = os.environ.get("IDEMPOTENCY_TABLE_NAME", "IdempotencyTable")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", None)
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
IDEMPOTENCY_TTL_HOURS = 24
DUPLICATE_TIME_BUCKET_MINUTES = 5
TRACKING_CODE_LENGTH = 6
SERVICE_NAME = "rescue-request-service"
