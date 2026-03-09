from enum import Enum


class RequestStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    TRIAGED = "TRIAGED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"

    @classmethod
    def terminal_states(cls) -> set["RequestStatus"]:
        return {cls.RESOLVED, cls.CANCELLED}

    @classmethod
    def is_terminal(cls, status: "RequestStatus") -> bool:
        return status in cls.terminal_states()
