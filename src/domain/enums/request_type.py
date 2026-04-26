from enum import Enum


class RequestType(str, Enum):
    MEDICAL = "MEDICAL"
    EVACUATION = "EVACUATION"
    SUPPLY = "SUPPLY"
