from src.application.usecases import create_citizen_update
from src.handlers.handler_utils import get_header, get_path_param, handle_error, parse_body
from src.shared.response import created


def handler(event, context):
    try:
        request_id = get_path_param(event, "requestId")
        body = parse_body(event)
        idempotency_key = get_header(event, "X-Idempotency-Key")
        client_ip = get_header(event, "X-Forwarded-For")
        user_agent = get_header(event, "User-Agent")

        result = create_citizen_update.execute(
            request_id=request_id,
            body=body,
            idempotency_key=idempotency_key,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        return created(result)
    except Exception as e:
        return handle_error(e)
