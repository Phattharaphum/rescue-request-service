from enum import Enum


class SourceChannel(str, Enum):
    WEB = "WEB"
    MOBILE = "MOBILE"
    LINE = "LINE"
    PHONE = "PHONE"
    WALK_IN = "WALK_IN"
    OTHER = "OTHER"
