from src.adapters.utils.hashing import (
    hash_idempotency_key,
    hash_phone,
    hash_request_fingerprint,
    hash_scoped_idempotency_key,
    hash_tracking_code,
)


class TestHashFunctions:
    def test_hash_phone_deterministic(self):
        h1 = hash_phone("0812345678")
        h2 = hash_phone("0812345678")
        assert h1 == h2

    def test_hash_phone_different_inputs(self):
        h1 = hash_phone("0812345678")
        h2 = hash_phone("0899999999")
        assert h1 != h2

    def test_hash_phone_is_hex(self):
        h = hash_phone("0812345678")
        assert len(h) == 64

    def test_hash_tracking_code_deterministic(self):
        h1 = hash_tracking_code("123456")
        h2 = hash_tracking_code("123456")
        assert h1 == h2

    def test_hash_tracking_code_different_inputs(self):
        h1 = hash_tracking_code("123456")
        h2 = hash_tracking_code("654321")
        assert h1 != h2

    def test_hash_idempotency_key_deterministic(self):
        h1 = hash_idempotency_key("550e8400-e29b-41d4-a716-446655440000")
        h2 = hash_idempotency_key("550e8400-e29b-41d4-a716-446655440000")
        assert h1 == h2

    def test_hash_scoped_idempotency_key_changes_with_scope(self):
        key = "550e8400-e29b-41d4-a716-446655440000"
        h1 = hash_scoped_idempotency_key(key, "POST:/v1/rescue-requests")
        h2 = hash_scoped_idempotency_key(key, "PATCH:/v1/rescue-requests/abc")
        assert h1 != h2

    def test_hash_request_fingerprint_deterministic(self):
        h1 = hash_request_fingerprint('{"key": "value"}')
        h2 = hash_request_fingerprint('{"key": "value"}')
        assert h1 == h2

    def test_hash_request_fingerprint_different_inputs(self):
        h1 = hash_request_fingerprint('{"key": "value1"}')
        h2 = hash_request_fingerprint('{"key": "value2"}')
        assert h1 != h2

    def test_different_hash_functions_different_results(self):
        value = "0812345678"
        h_phone = hash_phone(value)
        h_tracking = hash_tracking_code(value)
        h_idemp = hash_idempotency_key(value)
        assert h_phone != h_tracking
        assert h_phone != h_idemp
        assert h_tracking != h_idemp
