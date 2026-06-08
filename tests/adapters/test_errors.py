from src.adapters.errors import Category, Field, Diagnostic, AdapterError


def test_category_has_seven_stable_values():
    assert Category.AUTH.value == "auth"
    assert Category.RATE_LIMIT.value == "rate"
    assert Category.NETWORK.value == "network"
    assert Category.SERVER.value == "server"
    assert Category.BAD_REQUEST.value == "bad_req"
    assert Category.CONTENT.value == "content"
    assert Category.UNKNOWN.value == "unknown"
    assert len(list(Category)) == 7


import json


def test_diagnostic_round_trip():
    d = Diagnostic(
        category=Category.AUTH,
        fields=(Field(name="Authorization", value="Bearer sk-***", issue="missing or invalid"),),
        hint="请检查设置中的 API Key",
        original="HTTP错误 401: Unauthorized",
        platform="openai",
        source_id="src_abc",
    )
    d2 = Diagnostic.from_dict(d.to_dict())
    assert d2.category == Category.AUTH
    assert len(d2.fields) == 1
    assert d2.fields[0].name == "Authorization"
    assert d2.hint == d.hint
    assert d2.original == d.original


def test_field_redact_omits_value_in_dict():
    f = Field(name="Authorization", value="sk-secret", issue="invalid", redact=True)
    assert f.to_dict()["value"] == "***"


def test_from_dict_accepts_legacy_message_key():
    d = Diagnostic.from_dict({"message": "401 Unauthorized"})
    assert d.category == Category.UNKNOWN
    assert "401 Unauthorized" in d.original


def test_from_dict_accepts_none():
    assert Diagnostic.from_dict(None).category == Category.UNKNOWN
    assert Diagnostic.from_dict({}).category == Category.UNKNOWN


def test_from_dict_invalid_category_falls_back():
    d = Diagnostic.from_dict({"category": "made-up", "original": "x"})
    assert d.category == Category.UNKNOWN


def test_from_dict_invalid_category_type_falls_back():
    assert Diagnostic.from_dict({"category": ["auth"]}).category == Category.UNKNOWN
    assert Diagnostic.from_dict({"category": 401}).category == Category.UNKNOWN
    assert Diagnostic.from_dict({"category": {"x": 1}}).category == Category.UNKNOWN


def test_adapter_error_str_includes_category():
    d = Diagnostic(category=Category.RATE_LIMIT, original="429 too many requests")
    err = AdapterError("rate limited", d)
    assert "rate" in str(err)
    assert "429" in str(err)


def test_diagnostic_to_dict_is_json_safe():
    d = Diagnostic(category=Category.NETWORK, original="timeout")
    json.dumps(d.to_dict())  # must not raise
