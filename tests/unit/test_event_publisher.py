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


class TestPublishPrioritizationMessages:
    def test_builds_prioritization_command_payload(self, monkeypatch):
        captured: dict = {}

        def _fake_publish(**kwargs):
            captured.update(kwargs)
            return {"messageId": "msg-1", "messageType": "RescueRequestPrioritizeCommand", "sentAt": "2026-04-17T00:00:00+00:00"}

        monkeypatch.setattr(event_publisher, "publish_prioritization_command_message", _fake_publish)

        header = event_publisher.publish_prioritization_command({
            "requestId": "req-100",
            "incidentId": "019c774d-1ac5-758b-ae95-5cd4aeb89258",
            "requestType": "FLOOD",
            "description": "Need evacuation",
            "peopleCount": 4,
            "specialNeeds": "bedridden",
            "latitude": 13.75,
            "longitude": 100.5,
            "province": "Bangkok",
            "district": "Bang Rak",
            "subdistrict": "Si Phraya",
            "addressLine": "123 Road",
            "locationDetails": "Near the canal",
            "submittedAt": "2026-04-17T00:00:00+00:00",
        })

        assert header["messageId"] == "msg-1"
        assert captured["body"] == {
            "requestId": "req-100",
            "incidentId": "019c774d-1ac5-758b-ae95-5cd4aeb89258",
            "requestType": "FLOOD",
            "description": "Need evacuation",
            "peopleCount": 4,
            "specialNeeds": ["bedridden"],
            "location": {
                "latitude": 13.75,
                "longitude": 100.5,
                "province": "Bangkok",
                "district": "Bang Rak",
                "subdistrict": "Si Phraya",
                "addressLine": "123 Road",
            },
            "submittedAt": "2026-04-17T00:00:00+00:00",
            "locationDetails": "Near the canal",
        }

    def test_builds_prioritization_re_evaluation_payload(self, monkeypatch):
        captured: dict = {}

        def _fake_publish(**kwargs):
            captured.update(kwargs)
            return {"messageId": "msg-2", "messageType": "RescueRequestReEvaluateEvent", "sentAt": "2026-04-17T00:10:00+00:00"}

        monkeypatch.setattr(event_publisher, "publish_prioritization_re_evaluation_message", _fake_publish)

        header = event_publisher.publish_prioritization_re_evaluation(
            request_data={
                "requestId": "req-101",
                "incidentId": "019c774d-1ac5-758b-ae95-5cd4aeb89258",
                "requestType": "FLOOD",
                "description": "Water still rising",
                "peopleCount": 6,
                "latitude": 13.7,
                "longitude": 100.6,
                "submittedAt": "2026-04-17T00:05:00+00:00",
            },
            correlation_id="msg-1",
        )

        assert header["messageId"] == "msg-2"
        assert captured["correlation_id"] == "msg-1"
        assert captured["body"]["requestId"] == "req-101"
        assert captured["body"]["location"]["latitude"] == 13.7
