import pytest

from src.adapters.base import BaseAdapter
from src.adapters.openai_adapter import OpenAIAdapter
from src.models.platform_config import PlatformConfig
from src.models.task import GenerationTask


class DummyAdapter(BaseAdapter):
    def get_params_schema(self):
        return {}

    async def validate_config(self, config):
        return True

    async def generate(self, task, config):
        return None


def test_base_adapter_joins_relay_urls_without_double_slashes():
    adapter = DummyAdapter()
    assert adapter.build_url("https://relay.example/v1/", "/models") == "https://relay.example/v1/models"
    assert adapter.build_url("https://relay.example/v1", "images/generations") == "https://relay.example/v1/images/generations"


def test_openai_payload_uses_custom_relay_model_and_omits_empty_style():
    adapter = OpenAIAdapter()
    task = GenerationTask(
        platform_id="openai",
        prompt="cat",
        negative_prompt="",
        params={"model": "gpt-image-1", "size": "1024x1024", "quality": "standard", "style": "", "n": 1},
    )

    payload = adapter.build_generation_payload(task)

    assert payload["model"] == "gpt-image-1"
    assert payload["prompt"] == "cat"
    assert "style" not in payload
    assert "negative_prompt" not in payload


def test_openai_payload_prefers_configured_model_over_task_params():
    adapter = OpenAIAdapter()
    task = GenerationTask(
        platform_id="openai",
        prompt="cat",
        negative_prompt="",
        params={"model": "legacy-template-model", "size": "1024x1024", "quality": "standard", "n": 1},
    )
    config = PlatformConfig(
        id="openai",
        name="Relay",
        api_base_url="https://relay.example/v1",
        api_key="sk-test",
        model_name="gpt-image-2",
    )

    payload = adapter.build_generation_payload(task, config)

    assert payload["model"] == "gpt-image-2"


def test_openai_validate_config_uses_custom_headers_and_normalized_url(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            captured["url"] = url
            captured["headers"] = headers
            return Response()

    adapter = OpenAIAdapter()
    monkeypatch.setattr(adapter, "get_http_client", lambda config: Client())
    config = PlatformConfig(
        id="openai",
        name="Relay",
        api_base_url="https://relay.example/v1/",
        api_key="sk-test",
        custom_headers={"X-Relay-Key": "abc"},
    )

    import asyncio
    assert asyncio.run(adapter.validate_config(config)) is True
    assert captured["url"] == "https://relay.example/v1/models"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["headers"]["X-Relay-Key"] == "abc"



def test_generation_panel_omits_model_param_because_model_is_configured_in_settings():
    import sys
    from PySide6.QtWidgets import QApplication
    from src.managers.queue_manager import QueueManager
    from src.widgets.generation_panel import GenerationPanel

    app = QApplication.instance() or QApplication(sys.argv)
    panel = GenerationPanel(QueueManager())

    assert "model" not in panel._get_params()



def test_openai_validate_config_rejects_unauthorized(monkeypatch):
    class Response:
        status_code = 401

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return Response()

    adapter = OpenAIAdapter()
    monkeypatch.setattr(adapter, "get_http_client", lambda config: Client())
    config = PlatformConfig(
        id="openai",
        name="Relay",
        api_base_url="https://relay.example/v1",
        api_key="bad-key",
    )

    import asyncio
    assert asyncio.run(adapter.validate_config(config)) is False


def test_openai_adapter_formats_empty_exception_with_type():
    adapter = OpenAIAdapter()

    message = adapter.format_generation_exception(TimeoutError())

    assert "TimeoutError" in message
    assert message != "生成失败: "


def test_openai_adapter_explains_read_timeout_in_plain_language():
    import httpx

    adapter = OpenAIAdapter()

    message = adapter.format_generation_exception(
        httpx.ReadTimeout(""),
        "https://relay.example/v1/images/generations",
        {"model": "gpt-image-2", "size": "1024x1024", "quality": "standard", "n": 1},
    )

    assert "生成超时" in message
    assert "中转站" in message
    assert "https://relay.example/v1/images/generations" in message


def test_openai_adapter_extracts_http_error_message_from_json():
    import httpx


    adapter = OpenAIAdapter()
    response = httpx.Response(
        400,
        json={"error": {"message": "Invalid size", "code": "invalid_value"}},
        request=httpx.Request("POST", "https://relay.example/v1/images/generations"),
    )

    message = adapter.format_http_status_error(httpx.HTTPStatusError("bad", request=response.request, response=response))

    assert message == "HTTP错误 400: Invalid size"
