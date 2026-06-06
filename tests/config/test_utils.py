import pytest
from src.config.utils import parse_headers, safe_int, get_thumbnail_path


class TestParseHeaders:
    def test_none_returns_empty_dict(self):
        assert parse_headers(None) == {}

    def test_empty_string_returns_empty_dict(self):
        assert parse_headers("") == {}

    def test_empty_dict_returns_empty_dict(self):
        assert parse_headers({}) == {}

    def test_dict_input_returns_stringified_dict(self):
        result = parse_headers({"X-Key": "value", "Auth": "Bearer token"})
        assert result == {"X-Key": "value", "Auth": "Bearer token"}

    def test_valid_json_string(self):
        result = parse_headers('{"X-Foo": "bar"}')
        assert result == {"X-Foo": "bar"}

    def test_invalid_json_returns_empty_dict(self):
        assert parse_headers("not json") == {}

    def test_json_array_returns_empty_dict(self):
        assert parse_headers('[1, 2, 3]') == {}

    def test_json_non_dict_returns_empty_dict(self):
        assert parse_headers('"a string"') == {}

    def test_int_values_are_stringified(self):
        result = parse_headers({"count": 42})
        assert result == {"count": "42"}


class TestSafeInt:
    def test_valid_int_string(self):
        assert safe_int("42") == 42

    def test_valid_int(self):
        assert safe_int(42) == 42

    def test_invalid_string_returns_default(self):
        assert safe_int("not a number", 10) == 10

    def test_none_returns_default(self):
        assert safe_int(None, 5) == 5

    def test_float_string_returns_default(self):
        assert safe_int("3.14", 0) == 0

    def test_negative_int(self):
        assert safe_int("-5") == -5


class TestGetThumbnailPath:
    def test_returns_expected_path(self, tmp_path, monkeypatch):
        from src.config import constants
        monkeypatch.setattr(constants, "THUMBNAILS_DIR", str(tmp_path))
        result = get_thumbnail_path("/some/path/image.png")
        assert result == str(tmp_path / "thumb_image.jpg")

    def test_empty_path_returns_empty(self):
        assert get_thumbnail_path("") == ""
