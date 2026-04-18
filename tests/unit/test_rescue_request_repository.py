from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from src.adapters.persistence import rescue_request_repository as repository


class _FakeClient:
    def __init__(self, error=None):
        self.calls: list[list[dict]] = []
        self.error = error

    def transact_write_items(self, TransactItems):
        self.calls.append(TransactItems)
        if self.error:
            raise self.error


class _FakeTable:
    def __init__(self, update_error=None):
        self.put_calls: list[dict] = []
        self.delete_calls: list[dict] = []
        self.update_calls: list[dict] = []
        self.update_error = update_error

    def put_item(self, **kwargs):
        self.put_calls.append(kwargs)
        return kwargs

    def update_item(self, **kwargs):
        self.update_calls.append(kwargs)
        if self.update_error:
            raise self.update_error
        return kwargs

    def delete_item(self, **kwargs):
        self.delete_calls.append(kwargs)
        return kwargs


class _FakeResource:
    def __init__(self, client, table):
        self.meta = SimpleNamespace(client=client)
        self._table = table

    def Table(self, _name: str):
        return self._table


def _item(pk, sk, **extra):
    return {
        "PK": pk,
        "SK": sk,
        "requestId": "req-123",
        **extra,
    }


def test_create_rescue_request_normalizes_pre_serialized_keys(monkeypatch):
    client = _FakeClient()
    table = _FakeTable()
    resource = _FakeResource(client, table)
    monkeypatch.setattr(repository, "get_dynamodb_resource", lambda: resource)

    repository.create_rescue_request(
        master_item=_item({"S": "REQ#req-123"}, {"S": "META"}, itemType="MASTER"),
        current_item=_item("REQ#req-123", "CURRENT", itemType="CURRENT"),
        event_item=_item("REQ#req-123", "EVENT#0000000001", itemType="EVENT"),
        tracking_item=_item("TRACK#phone", "CODE#tracking", itemType="TRACKING"),
        phone_unique_item=_item("PHONE#phone", "UNIQUE", itemType="PHONE_UNIQUE"),
        incident_item=_item("INCIDENT#inc-123", "REQUEST#ts#req-123", itemType="INCIDENT"),
        duplicate_item=_item("DUP#sig", "REQUEST#req-123", itemType="DUPLICATE"),
    )

    transact_items = client.calls[0]
    serialized_keys = [
        (item["Put"]["Item"]["PK"], item["Put"]["Item"]["SK"])
        for item in transact_items
    ]

    assert serialized_keys == [
        ({"S": "REQ#req-123"}, {"S": "META"}),
        ({"S": "REQ#req-123"}, {"S": "CURRENT"}),
        ({"S": "REQ#req-123"}, {"S": "EVENT#0000000001"}),
        ({"S": "TRACK#phone"}, {"S": "CODE#tracking"}),
        ({"S": "INCIDENT#inc-123"}, {"S": "REQUEST#ts#req-123"}),
        ({"S": "PHONE#phone"}, {"S": "UNIQUE"}),
        ({"S": "DUP#sig"}, {"S": "REQUEST#req-123"}),
    ]


def test_append_event_and_update_current_normalizes_event_keys(monkeypatch):
    client = _FakeClient()
    table = _FakeTable()
    resource = _FakeResource(client, table)
    monkeypatch.setattr(repository, "get_dynamodb_resource", lambda: resource)

    repository.append_event_and_update_current(
        request_id="req-123",
        event_item=_item({"S": "REQ#req-123"}, {"S": "EVENT#0000000002"}, itemType="EVENT", version=2),
        current_updates={"status": "DISPATCHED", "stateVersion": 2},
        expected_version=1,
    )

    put_item = client.calls[0][0]["Put"]["Item"]
    update_item = client.calls[0][1]["Update"]

    assert put_item["PK"] == {"S": "REQ#req-123"}
    assert put_item["SK"] == {"S": "EVENT#0000000002"}
    assert update_item["Key"] == {
        "PK": {"S": "REQ#req-123"},
        "SK": {"S": "CURRENT"},
    }


def test_create_rescue_request_falls_back_on_key_type_mismatch_validation(monkeypatch):
    error = ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Transaction cancelled",
            },
            "CancellationReasons": [
                {
                    "Code": "ValidationError",
                    "Message": "One or more parameter values were invalid: Type mismatch for key PK expected: S actual: M",
                }
            ],
        },
        "TransactWriteItems",
    )
    client = _FakeClient(error=error)
    table = _FakeTable()
    resource = _FakeResource(client, table)
    monkeypatch.setattr(repository, "get_dynamodb_resource", lambda: resource)
    monkeypatch.setattr(repository, "STAGE", "dev")

    repository.create_rescue_request(
        master_item=_item("REQ#req-123", "META", itemType="MASTER"),
        current_item=_item("REQ#req-123", "CURRENT", itemType="CURRENT"),
        event_item=_item("REQ#req-123", "EVENT#0000000001", itemType="EVENT"),
        tracking_item=_item("TRACK#phone", "CODE#tracking", itemType="TRACKING"),
        phone_unique_item=_item("PHONE#phone", "UNIQUE", itemType="PHONE_UNIQUE"),
        incident_item=_item("INCIDENT#inc-123", "REQUEST#ts#req-123", itemType="INCIDENT"),
        duplicate_item=_item("DUP#sig", "REQUEST#req-123", itemType="DUPLICATE"),
    )

    assert len(client.calls) == 1
    assert len(table.put_calls) == 7
    assert table.delete_calls == []


def test_append_event_and_update_current_falls_back_on_key_type_mismatch_validation(monkeypatch):
    error = ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Transaction cancelled",
            },
            "CancellationReasons": [
                {
                    "Code": "ValidationError",
                    "Message": "One or more parameter values were invalid: Type mismatch for key PK expected: S actual: M",
                }
            ],
        },
        "TransactWriteItems",
    )
    client = _FakeClient(error=error)
    table = _FakeTable()
    resource = _FakeResource(client, table)
    monkeypatch.setattr(repository, "get_dynamodb_resource", lambda: resource)
    monkeypatch.setattr(repository, "STAGE", "dev")

    repository.append_event_and_update_current(
        request_id="req-123",
        event_item=_item("REQ#req-123", "EVENT#0000000002", itemType="EVENT", version=2),
        current_updates={"status": "TRIAGED", "stateVersion": 2},
        expected_version=1,
    )

    assert len(client.calls) == 1
    assert len(table.put_calls) == 1
    assert len(table.update_calls) == 1
    assert table.delete_calls == []
    assert table.update_calls[0]["ConditionExpression"] == "#cv = :expected_version"


def test_append_event_and_update_current_rolls_back_event_when_fallback_update_fails(monkeypatch):
    transact_error = ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Transaction cancelled",
            },
            "CancellationReasons": [
                {
                    "Code": "ValidationError",
                    "Message": "One or more parameter values were invalid: Type mismatch for key PK expected: S actual: M",
                }
            ],
        },
        "TransactWriteItems",
    )
    update_error = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "condition failed"}},
        "UpdateItem",
    )
    client = _FakeClient(error=transact_error)
    table = _FakeTable(update_error=update_error)
    resource = _FakeResource(client, table)
    monkeypatch.setattr(repository, "get_dynamodb_resource", lambda: resource)
    monkeypatch.setattr(repository, "STAGE", "dev")

    with pytest.raises(repository.ConflictError):
        repository.append_event_and_update_current(
            request_id="req-123",
            event_item=_item("REQ#req-123", "EVENT#0000000002", itemType="EVENT", version=2),
            current_updates={"status": "TRIAGED", "stateVersion": 2},
            expected_version=1,
        )

    assert len(table.put_calls) == 1
    assert table.delete_calls == [{"Key": {"PK": "REQ#req-123", "SK": "EVENT#0000000002"}}]


def test_update_current_fields_targets_current_item_and_enforces_expected_version(monkeypatch):
    client = _FakeClient()
    table = _FakeTable()
    resource = _FakeResource(client, table)
    monkeypatch.setattr(repository, "get_dynamodb_resource", lambda: resource)

    repository.update_current_fields(
        request_id="req-123",
        updates={"priorityScore": 0.905, "latestNote": "Escalated"},
        expected_version=3,
    )

    call = table.update_calls[0]
    assert call["Key"] == {"PK": "REQ#req-123", "SK": "CURRENT"}
    assert "stateVersion = :expected_version" in call["ConditionExpression"]
    assert call["ExpressionAttributeValues"][":expected_version"] == 3
