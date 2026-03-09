import random
import string

from src.shared.config import TRACKING_CODE_LENGTH


def generate_tracking_code(length: int = TRACKING_CODE_LENGTH) -> str:
    characters = string.digits
    return "".join(random.choices(characters, k=length))
