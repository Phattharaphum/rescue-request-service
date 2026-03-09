from src.adapters.utils.phone_normalizer import normalize_phone


class TestNormalizePhone:
    def test_thai_mobile(self):
        assert normalize_phone("081-234-5678") == "0812345678"

    def test_with_country_code_plus(self):
        assert normalize_phone("+66812345678") == "0812345678"

    def test_with_country_code_no_plus(self):
        assert normalize_phone("66812345678") == "0812345678"

    def test_already_normalized(self):
        assert normalize_phone("0812345678") == "0812345678"

    def test_with_spaces(self):
        assert normalize_phone("081 234 5678") == "0812345678"

    def test_with_parentheses(self):
        assert normalize_phone("(081) 234-5678") == "0812345678"

    def test_empty_string(self):
        assert normalize_phone("") == ""

    def test_none_like(self):
        assert normalize_phone("") == ""
