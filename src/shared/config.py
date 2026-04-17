import os


STAGE = os.environ.get("STAGE", "local")
# Prefer APP_AWS_REGION so local runtime can override Lambda/SAM-managed AWS_REGION safely.
AWS_REGION = (
    os.environ.get("APP_AWS_REGION")
    or os.environ.get("AWS_REGION")
    or os.environ.get("AWS_DEFAULT_REGION")
    or "ap-southeast-1"
)
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "RescueRequestTable")
IDEMPOTENCY_TABLE_NAME = os.environ.get("IDEMPOTENCY_TABLE_NAME", "IdempotencyTable")
INCIDENT_CATALOG_TABLE_NAME = os.environ.get("INCIDENT_CATALOG_TABLE_NAME", "IncidentCatalogTable")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
PRIORITIZATION_COMMANDS_TOPIC_ARN = os.environ.get("PRIORITIZATION_COMMANDS_TOPIC_ARN", "")
PRIORITIZATION_REEVALUATE_TOPIC_ARN = os.environ.get("PRIORITIZATION_REEVALUATE_TOPIC_ARN", "")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", None)
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL") or DYNAMODB_ENDPOINT
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
INCIDENT_SYNC_SECRET_ID = os.environ.get("INCIDENT_SYNC_SECRET_ID", "")
INCIDENT_SYNC_HTTP_TIMEOUT_SECONDS = int(os.environ.get("INCIDENT_SYNC_HTTP_TIMEOUT_SECONDS", "30"))
IDEMPOTENCY_TTL_HOURS = 24
DUPLICATE_TIME_BUCKET_MINUTES = 5
TRACKING_CODE_LENGTH = 6
SERVICE_NAME = "rescue-request-service"
