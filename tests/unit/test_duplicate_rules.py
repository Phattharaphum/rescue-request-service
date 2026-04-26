from src.domain.rules.duplicate_rules import build_duplicate_signature, _compute_time_bucket


class TestBuildDuplicateSignature:
    def test_same_inputs_same_signature(self):
        sig1 = build_duplicate_signature(
            incident_id="inc-001",
            contact_phone="0812345678",
            request_type="EVACUATION",
            latitude=13.7563,
            longitude=100.5018,
            submitted_at="2024-01-01T12:00:00+00:00",
        )
        sig2 = build_duplicate_signature(
            incident_id="inc-001",
            contact_phone="0812345678",
            request_type="EVACUATION",
            latitude=13.7563,
            longitude=100.5018,
            submitted_at="2024-01-01T12:01:00+00:00",
        )
        assert sig1 == sig2  # Same 5-minute bucket

    def test_different_incident_different_signature(self):
        sig1 = build_duplicate_signature(
            incident_id="inc-001",
            contact_phone="0812345678",
            request_type="EVACUATION",
            latitude=13.7563,
            longitude=100.5018,
            submitted_at="2024-01-01T12:00:00+00:00",
        )
        sig2 = build_duplicate_signature(
            incident_id="inc-002",
            contact_phone="0812345678",
            request_type="EVACUATION",
            latitude=13.7563,
            longitude=100.5018,
            submitted_at="2024-01-01T12:00:00+00:00",
        )
        assert sig1 != sig2

    def test_different_phone_different_signature(self):
        sig1 = build_duplicate_signature(
            incident_id="inc-001",
            contact_phone="0812345678",
            request_type="EVACUATION",
            latitude=13.7563,
            longitude=100.5018,
            submitted_at="2024-01-01T12:00:00+00:00",
        )
        sig2 = build_duplicate_signature(
            incident_id="inc-001",
            contact_phone="0899999999",
            request_type="EVACUATION",
            latitude=13.7563,
            longitude=100.5018,
            submitted_at="2024-01-01T12:00:00+00:00",
        )
        assert sig1 != sig2

    def test_different_time_bucket_different_signature(self):
        sig1 = build_duplicate_signature(
            incident_id="inc-001",
            contact_phone="0812345678",
            request_type="EVACUATION",
            latitude=13.7563,
            longitude=100.5018,
            submitted_at="2024-01-01T12:00:00+00:00",
        )
        sig2 = build_duplicate_signature(
            incident_id="inc-001",
            contact_phone="0812345678",
            request_type="EVACUATION",
            latitude=13.7563,
            longitude=100.5018,
            submitted_at="2024-01-01T12:10:00+00:00",  # Different 5-minute bucket
        )
        assert sig1 != sig2

    def test_signature_is_hex_string(self):
        sig = build_duplicate_signature(
            incident_id="inc-001",
            contact_phone="0812345678",
            request_type="EVACUATION",
            latitude=13.7563,
            longitude=100.5018,
            submitted_at="2024-01-01T12:00:00+00:00",
        )
        assert len(sig) == 64  # SHA-256 hex digest


class TestComputeTimeBucket:
    def test_same_bucket(self):
        b1 = _compute_time_bucket("2024-01-01T12:00:00+00:00")
        b2 = _compute_time_bucket("2024-01-01T12:04:59+00:00")
        assert b1 == b2

    def test_different_bucket(self):
        b1 = _compute_time_bucket("2024-01-01T12:00:00+00:00")
        b2 = _compute_time_bucket("2024-01-01T12:05:00+00:00")
        assert b1 != b2
