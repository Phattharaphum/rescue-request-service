from src.shared.validators import validate_latitude, validate_longitude


class TestFiniteCoordinateValidation:
    def test_validate_latitude_rejects_nan(self):
        errors = validate_latitude(float("nan"))
        assert errors
        assert errors[0]["field"] == "latitude"

    def test_validate_longitude_rejects_nan(self):
        errors = validate_longitude(float("nan"))
        assert errors
        assert errors[0]["field"] == "longitude"

    def test_validate_latitude_rejects_infinity(self):
        errors = validate_latitude(float("inf"))
        assert errors
        assert errors[0]["field"] == "latitude"

    def test_validate_longitude_rejects_infinity(self):
        errors = validate_longitude(float("-inf"))
        assert errors
        assert errors[0]["field"] == "longitude"
