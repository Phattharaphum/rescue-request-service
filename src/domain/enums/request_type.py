from enum import Enum


class RequestType(str, Enum):
    FLOOD = "FLOOD"
    FIRE = "FIRE"
    EARTHQUAKE = "EARTHQUAKE"
    LANDSLIDE = "LANDSLIDE"
    STORM = "STORM"
    MEDICAL = "MEDICAL"
    EVACUATION = "EVACUATION"
    SUPPLY = "SUPPLY"
    OTHER = "OTHER"
