from src.application.usecases import citizen_tracking_lookup
from src.handlers.handler_utils import handle_error, parse_body
from src.shared.response import ok


def handler(event, context):
    try:
        body = parse_body(event)
        result = citizen_tracking_lookup.execute(
            contact_phone=body.get("contactPhone", ""),
            tracking_code=body.get("trackingCode", ""),
        )
        return ok(result)
    except Exception as e:
        return handle_error(e)
