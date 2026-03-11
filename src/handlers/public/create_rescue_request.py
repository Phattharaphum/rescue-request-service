from src.application.usecases import create_rescue_request
from src.handlers.handler_utils import cors_handler, get_header, handle_error, parse_body
from src.shared.response import created


@cors_handler
def handler(event, context):
    try:
        body = parse_body(event)
        idempotency_key = get_header(event, "X-Idempotency-Key")
        client_ip = get_header(event, "X-Forwarded-For")
        user_agent = get_header(event, "User-Agent")

        result = create_rescue_request.execute(
            body=body,
            idempotency_key=idempotency_key,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        return created(result)
    except Exception as e:
        return handle_error(e, event)

