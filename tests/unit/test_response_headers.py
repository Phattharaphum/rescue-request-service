from src.handlers.handler_utils import handle_error
from src.shared.errors import ValidationError
from src.shared.response import ALLOWED_ORIGIN, ok


def test_ok_response_includes_access_control_allow_origin():
    response = ok({"status": "ok"})

    assert response["headers"]["Access-Control-Allow-Origin"] == ALLOWED_ORIGIN


def test_handle_error_includes_access_control_allow_origin():
    response = handle_error(ValidationError("Input validation failed", [{"field": "x", "issue": "bad"}]))

    assert response["headers"]["Access-Control-Allow-Origin"] == ALLOWED_ORIGIN
