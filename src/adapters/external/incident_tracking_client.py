import json
import uuid
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.shared.config import (
    INCIDENT_SYNC_ACCEPT,
    INCIDENT_SYNC_API_KEY,
    INCIDENT_SYNC_API_URL,
    INCIDENT_SYNC_HTTP_TIMEOUT_SECONDS,
    INCIDENT_SYNC_TRANSACTION_ID_HEADER,
)
from src.shared.errors import ServiceUnavailableError
from src.shared.logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _load_incident_tracking_config() -> dict:
    if not isinstance(INCIDENT_SYNC_API_URL, str) or not INCIDENT_SYNC_API_URL.strip():
        raise ServiceUnavailableError("INCIDENT_SYNC_API_URL is not configured")
    if not isinstance(INCIDENT_SYNC_API_KEY, str) or not INCIDENT_SYNC_API_KEY.strip():
        raise ServiceUnavailableError("INCIDENT_SYNC_API_KEY is not configured")

    return {
        "apiUrl": INCIDENT_SYNC_API_URL.strip(),
        "apiKey": INCIDENT_SYNC_API_KEY.strip(),
        "accept": INCIDENT_SYNC_ACCEPT.strip() if INCIDENT_SYNC_ACCEPT else "application/json",
        "transactionIdHeader": (
            INCIDENT_SYNC_TRANSACTION_ID_HEADER.strip() if INCIDENT_SYNC_TRANSACTION_ID_HEADER else "X-IncidentTNX-Id"
        ),
    }


def fetch_incidents() -> list[dict]:
    config = _load_incident_tracking_config()
    transaction_id = str(uuid.uuid4())
    request = Request(
        url=config["apiUrl"],
        headers={
            "Accept": config["accept"],
            "api-key": config["apiKey"],
            config["transactionIdHeader"]: transaction_id,
        },
        method="GET",
    )

    logger.info(
        "Calling IncidentTracking Service",
        extra={
            "extra_data": {
                "url": config["apiUrl"],
                "method": "GET",
                "timeoutSeconds": INCIDENT_SYNC_HTTP_TIMEOUT_SECONDS,
                "accept": config["accept"],
                "transactionIdHeader": config["transactionIdHeader"],
                "transactionId": transaction_id,
            }
        },
    )

    try:
        with urlopen(request, timeout=INCIDENT_SYNC_HTTP_TIMEOUT_SECONDS) as response:
            raw_payload = response.read()
            payload = json.loads(raw_payload.decode("utf-8"))
            logger.info(
                "IncidentTracking Service call completed",
                extra={
                    "extra_data": {
                        "statusCode": getattr(response, "status", None) or response.getcode(),
                        "responseBytes": len(raw_payload),
                        "responseType": type(payload).__name__,
                    }
                },
            )
    except HTTPError as exc:
        logger.exception("IncidentTracking Service returned HTTP %s", exc.code)
        raise ServiceUnavailableError("IncidentTracking Service request failed") from exc
    except URLError as exc:
        logger.exception("IncidentTracking Service is unreachable")
        raise ServiceUnavailableError("IncidentTracking Service is unreachable") from exc
    except TimeoutError as exc:
        logger.exception("IncidentTracking Service request timed out")
        raise ServiceUnavailableError("IncidentTracking Service request timed out") from exc
    except json.JSONDecodeError as exc:
        logger.exception("IncidentTracking Service returned invalid JSON")
        raise ServiceUnavailableError("IncidentTracking Service returned invalid JSON") from exc

    if not isinstance(payload, list):
        raise ServiceUnavailableError("IncidentTracking Service response must be a JSON array")

    incidents = [item for item in payload if isinstance(item, dict)]
    if len(incidents) != len(payload):
        logger.warning("IncidentTracking Service response contained non-object entries; ignoring invalid rows")
    logger.info(
        "IncidentTracking Service incidents parsed",
        extra={
            "extra_data": {
                "incidentCount": len(incidents),
                "droppedNonObjectRows": len(payload) - len(incidents),
            }
        },
    )
    return incidents
