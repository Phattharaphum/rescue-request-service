from src.adapters.persistence.rescue_request_repository import get_current_state
from src.application.usecases.current_state_projection import clean_current_state_item
from src.shared.errors import NotFoundError
from src.shared.logger import get_logger

logger = get_logger(__name__)


def execute(request_id: str) -> dict:
    current = get_current_state(request_id)
    if not current:
        raise NotFoundError(f"Request {request_id} not found")

    return clean_current_state_item(current)
