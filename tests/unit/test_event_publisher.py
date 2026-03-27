from src.application.services import event_publisher


class TestPublishCitizenUpdated:
    def test_includes_updated_details_when_provided(self, monkeypatch):
        captured: dict = {}

        def _fake_publish_event(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(event_publisher, "publish_event", _fake_publish_event)

        event_publisher.publish_citizen_updated(
            request_id="req-1",
            update_id="upd-1",
            update_type="NOTE",
            update_payload={"note": "Water rising"},
            created_at="2026-03-10T03:00:00+00:00",
        )

        assert captured["event_type"] == "rescue-request.citizen-updated"
        assert captured["partition_key"] == "req-1"
        assert captured["body"] == {
            "requestId": "req-1",
            "updateId": "upd-1",
            "updateType": "NOTE",
            "updatePayload": {"note": "Water rising"},
            "createdAt": "2026-03-10T03:00:00+00:00",
        }

    def test_keeps_legacy_body_shape_when_details_not_provided(self, monkeypatch):
        captured: dict = {}

        def _fake_publish_event(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(event_publisher, "publish_event", _fake_publish_event)

        event_publisher.publish_citizen_updated(
            request_id="req-2",
            update_id="upd-2",
            update_type="PATCH",
        )

        assert captured["body"] == {
            "requestId": "req-2",
            "updateId": "upd-2",
            "updateType": "PATCH",
        }


class TestPublishPriorityScoreUpdated:
    def test_includes_priority_payload(self, monkeypatch):
        captured: dict = {}

        def _fake_publish_event(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(event_publisher, "publish_event", _fake_publish_event)

        event_publisher.publish_priority_score_updated(
            request_id="req-3",
            previous_priority_score=42.5,
            new_priority_score=88.0,
            priority_level="HIGH",
            note="Escalated by supervisor",
            updated_at="2026-03-27T10:30:00+00:00",
            correlation_id="corr-123",
        )

        assert captured["event_type"] == "rescue-request.priority-score-updated"
        assert captured["partition_key"] == "req-3"
        assert captured["correlation_id"] == "corr-123"
        assert captured["body"] == {
            "requestId": "req-3",
            "previousPriorityScore": 42.5,
            "newPriorityScore": 88.0,
            "priorityLevel": "HIGH",
            "note": "Escalated by supervisor",
            "updatedAt": "2026-03-27T10:30:00+00:00",
        }
