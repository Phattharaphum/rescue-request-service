import json

from src.handlers.public import health_check


def _event(path: str) -> dict:
    return {
        "httpMethod": "GET",
        "path": path,
        "headers": {},
        "requestContext": {"requestId": "health-req"},
    }


class _HealthyDynamoClient:
    def describe_table(self, TableName: str) -> dict:
        return {"Table": {"TableStatus": "ACTIVE"}}


def test_live_health_returns_200():
    response = health_check.handler(_event("/v1/health/live"), None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "pass"
    assert body["checks"]["process"]["status"] == "pass"
    assert isinstance(body["checks"]["process"]["uptimeMs"], int)


def test_ready_health_returns_200_when_dynamodb_is_healthy(monkeypatch):
    monkeypatch.setattr(health_check, "get_dynamodb_client", lambda: _HealthyDynamoClient())

    response = health_check.handler(_event("/v1/health/ready"), None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "pass"
    assert body["checks"]["dynamodb"]["status"] == "pass"
    assert len(body["checks"]["dynamodb"]["tables"]) == 3
    assert all(item["status"] == "pass" for item in body["checks"]["dynamodb"]["tables"])


def test_ready_health_returns_503_when_dependency_fails(monkeypatch):
    class _FailingDynamoClient:
        def describe_table(self, TableName: str) -> dict:
            if TableName == health_check.IDEMPOTENCY_TABLE_NAME:
                raise RuntimeError("idempotency table unreachable")
            return {"Table": {"TableStatus": "ACTIVE"}}

    monkeypatch.setattr(health_check, "get_dynamodb_client", lambda: _FailingDynamoClient())

    response = health_check.handler(_event("/v1/health/ready"), None)

    assert response["statusCode"] == 503
    body = json.loads(response["body"])
    assert body["status"] == "fail"
    idempotency_check = next(
        item for item in body["checks"]["dynamodb"]["tables"] if item["name"] == "idempotencyTable"
    )
    assert idempotency_check["status"] == "fail"
    assert "idempotency table unreachable" in (idempotency_check["issue"] or "")


def test_summary_health_returns_200_and_combines_live_and_ready(monkeypatch):
    monkeypatch.setattr(health_check, "get_dynamodb_client", lambda: _HealthyDynamoClient())

    response = health_check.handler(_event("/v1/health"), None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "pass"
    assert body["checks"]["liveness"]["status"] == "pass"
    assert body["checks"]["readiness"]["status"] == "pass"
