import json
import uuid
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3

from src.shared.config import (
    AWS_ENDPOINT_URL,
    AWS_REGION,
    INCIDENT_SYNC_HTTP_TIMEOUT_SECONDS,
    INCIDENT_SYNC_SECRET_ID,
    STAGE,
)
from src.shared.errors import ServiceUnavailableError
from src.shared.logger import get_logger

logger = get_logger(__name__)


def _get_secrets_manager_client():
    kwargs = {"region_name": AWS_REGION}
    if STAGE == "local" and AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = AWS_ENDPOINT_URL
    return boto3.client("secretsmanager", **kwargs)


@lru_cache(maxsize=1)
def _load_incident_tracking_secret() -> dict:
    if not INCIDENT_SYNC_SECRET_ID:
        raise ServiceUnavailableError("INCIDENT_SYNC_SECRET_ID is not configured")

    response = _get_secrets_manager_client().get_secret_value(SecretId=INCIDENT_SYNC_SECRET_ID)
    secret_string = response.get("SecretString", "")
    try:
        secret = json.loads(secret_string)
    except json.JSONDecodeError as exc:
        raise ServiceUnavailableError("Incident tracking secret must be valid JSON") from exc

    api_url = secret.get("apiUrl")
    api_key = secret.get("apiKey")
    if not isinstance(api_url, str) or not api_url.strip():
        raise ServiceUnavailableError("Incident tracking secret is missing apiUrl")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ServiceUnavailableError("Incident tracking secret is missing apiKey")

    return {
        "apiUrl": api_url.strip(),
        "apiKey": api_key.strip(),
        "accept": secret.get("accept", "application/json"),
        "transactionIdHeader": secret.get("transactionIdHeader", "X-IncidentTNX-Id"),
    }


def fetch_incidents() -> list[dict]:
    secret = _load_incident_tracking_secret()
    request = Request(
        url=secret["apiUrl"],
        headers={
            "Accept": secret["accept"],
            "api-key": secret["apiKey"],
            secret["transactionIdHeader"]: str(uuid.uuid4()),
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=INCIDENT_SYNC_HTTP_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
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
    return incidents
