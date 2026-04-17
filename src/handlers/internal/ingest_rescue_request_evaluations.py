from src.adapters.messaging.prioritization_parser import parse_prioritization_record
from src.application.usecases import ingest_rescue_request_evaluation
from src.shared.logger import get_logger

logger = get_logger(__name__)


def handler(event, context):
    records = event.get("Records", [])
    batch_failures: list[dict[str, str]] = []

    for record in records:
        try:
            message = parse_prioritization_record(record)
            ingest_rescue_request_evaluation.execute(message)
        except Exception:
            logger.exception("Failed to ingest RescueRequestEvaluatedEvent")
            batch_failures.append({"itemIdentifier": record.get("messageId", "")})

    return {"batchItemFailures": batch_failures}
