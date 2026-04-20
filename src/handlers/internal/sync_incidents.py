import time

from src.application.usecases import sync_incident_catalog
from src.shared.logger import get_logger

logger = get_logger(__name__)


def handler(event, context):
    started_at = time.perf_counter()
    aws_request_id = getattr(context, "aws_request_id", None)
    event_source = (event or {}).get("source")
    detail_type = (event or {}).get("detail-type")

    logger.info(
        "Incident sync handler invoked",
        extra={
            "extra_data": {
                "awsRequestId": aws_request_id,
                "eventSource": event_source,
                "detailType": detail_type,
            }
        },
    )

    try:
        result = sync_incident_catalog.execute()
        logger.info(
            "Incident sync handler completed",
            extra={
                "extra_data": {
                    "awsRequestId": aws_request_id,
                    "durationMs": int((time.perf_counter() - started_at) * 1000),
                    "result": result,
                }
            },
        )
        return result
    except Exception:
        logger.exception(
            "Incident sync handler failed",
            extra={
                "extra_data": {
                    "awsRequestId": aws_request_id,
                    "durationMs": int((time.perf_counter() - started_at) * 1000),
                }
            },
        )
        raise
