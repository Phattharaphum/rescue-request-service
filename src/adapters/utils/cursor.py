import base64
import json


def encode_cursor(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data, default=str).encode()).decode()


def decode_cursor(cursor: str) -> dict | None:
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        return None
