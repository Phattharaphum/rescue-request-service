import hashlib
import json
import os
import time

from src.adapters.messaging.mission_status_parser import parse_mission_status_record
from src.application.usecases import ingest_mission_status_changed
from src.shared.errors import ValidationError
from src.shared.logger import get_logger

logger = get_logger(__name__)
MAX_SQS_BODY_PREVIEW_CHARS = 2000
LOG_PAYLOAD_PREVIEW = os.environ.get("LOG_PAYLOAD_PREVIEW", "false").strip().lower() in {"1", "true", "yes"}


def handler(event, context):
    records = event.get("Records", [])
    batch_failures: list[dict[str, str]] = []
    started_at = time.perf_counter()
    aws_request_id = getattr(context, "aws_request_id", None)

    logger.info(
        "MissionStatusChanged SQS batch received",
        extra={
            "extra_data": {
                "awsRequestId": aws_request_id,
                "recordCount": len(records),
            }
        },
    )

    for index, record in enumerate(records):
        message_id = record.get("messageId")
        logger.info(
            "Received MissionStatusChanged SQS record",
            extra={
                "extra_data": {
                    "awsRequestId": aws_request_id,
                    "recordIndex": index,
                    "recordMessageId": message_id,
                    "bodySummary": _summarize_record_body(record.get("body")),
                    "messageAttributeKeys": sorted((record.get("messageAttributes") or {}).keys()),
                }
            },
        )

        try:
            message = parse_mission_status_record(record)
            header = message.get("header") or {}
            body = message.get("body") or {}
            logger.info(
                "Parsed MissionStatusChanged record",
                extra={
                    "extra_data": {
                        "awsRequestId": aws_request_id,
                        "recordIndex": index,
                        "recordMessageId": message_id,
                        "messageType": header.get("messageType") or header.get("eventType"),
                        "channel": header.get("channel"),
                        "topicArn": header.get("topicArn"),
                        "correlationId": header.get("correlationId"),
                        "requestId": body.get("requestId") or body.get("request_id"),
                        "missionId": body.get("mission_id") or body.get("missionId"),
                        "newStatus": body.get("new_status") or body.get("newStatus"),
                    }
                },
            )
            result = ingest_mission_status_changed.execute(message)
            logger.info(
                "Ingested MissionStatusChanged message",
                extra={
                    "extra_data": {
                        "awsRequestId": aws_request_id,
                        "recordIndex": index,
                        "recordMessageId": message_id,
                        "result": result,
                    }
                },
            )
        except ValidationError as exc:
            logger.error(
                "Failed to ingest MissionStatusChanged event due to validation error",
                extra={
                    "extra_data": {
                        "awsRequestId": aws_request_id,
                        "recordIndex": index,
                        "recordMessageId": message_id,
                        "validationDetails": exc.details,
                    }
                },
            )
            batch_failures.append({"itemIdentifier": message_id or ""})
        except Exception:
            logger.exception(
                "Failed to ingest MissionStatusChanged event",
                extra={
                    "extra_data": {
                        "awsRequestId": aws_request_id,
                        "recordIndex": index,
                        "recordMessageId": message_id,
                    }
                },
            )
            batch_failures.append({"itemIdentifier": message_id or ""})

    logger.info(
        "MissionStatusChanged SQS batch completed",
        extra={
            "extra_data": {
                "awsRequestId": aws_request_id,
                "recordCount": len(records),
                "failedCount": len(batch_failures),
                "durationMs": int((time.perf_counter() - started_at) * 1000),
            }
        },
    )

    return {"batchItemFailures": batch_failures}


def _summarize_record_body(raw_body):
    if raw_body is None:
        return {"present": False}
    if not isinstance(raw_body, str):
        serialized = json.dumps(raw_body, default=str, ensure_ascii=False)
        summary = {
            "present": True,
            "kind": type(raw_body).__name__,
            "sizeBytes": len(serialized.encode("utf-8")),
            "sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        }
        if LOG_PAYLOAD_PREVIEW:
            summary["preview"] = serialized[:MAX_SQS_BODY_PREVIEW_CHARS]
        return summary

    summary = {
        "present": True,
        "kind": "string",
        "sizeBytes": len(raw_body.encode("utf-8")),
        "sha256": hashlib.sha256(raw_body.encode("utf-8")).hexdigest(),
    }
    if LOG_PAYLOAD_PREVIEW:
        summary["preview"] = raw_body[:MAX_SQS_BODY_PREVIEW_CHARS]
    return summary
