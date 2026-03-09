import json

from src.adapters.utils.hashing import hash_request_fingerprint


def compute_request_fingerprint(payload: dict) -> str:
    stable_json = json.dumps(payload, sort_keys=True, default=str)
    return hash_request_fingerprint(stable_json)
