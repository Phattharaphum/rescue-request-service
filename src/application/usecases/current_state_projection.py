from typing import Any


HIDDEN_CURRENT_STATE_FIELDS = {
    "PK",
    "SK",
    "itemType",
    "lastPrioritizationMessageId",
    "lastPrioritizationMessageType",
    "lastPrioritizationSentAt",
    "latestPrioritySourceEventId",
    "latestPrioritySourceEventType",
    "latestPrioritySourceOccurredAt",
}


def clean_current_state_item(item: dict[str, Any] | None) -> dict[str, Any]:
    if not item:
        return {}
    return {k: v for k, v in item.items() if k not in HIDDEN_CURRENT_STATE_FIELDS}
