import json

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


def test_auth_presets_build_expected_headers_and_allow_overrides():
    adapter = DummyAdapter()
    openai_config = PlatformConfig(
        id="openai",
        name="OpenAI",
        api_base_url="https://example.test/v1",
        api_key="sk-test",
        auth_preset="openai",
    )
    gemini_config = PlatformConfig(
        id="openai",
        name="Gemini",
        api_base_url="https://example.test/v1",
        api_key="AIza-test",
        auth_preset="gemini",
    )
    override_config = PlatformConfig(
        id="openai",
        name="Override",
        api_base_url="https://example.test/v1",
        api_key="sk-test",
        auth_preset="openai",
        custom_headers={"Authorization": "Bearer relay-token"},
    )

    assert adapter.build_headers(openai_config)["Authorization"] == "Bearer sk-test"
    assert adapter.build_headers(gemini_config)["x-goog-api-key"] == "AIza-test"
    assert adapter.build_headers(override_config)["Authorization"] == "Bearer relay-token"


def test_openai_payload_uses_selected_source_model_without_hardcoded_default():
    adapter = OpenAIAdapter()
    task = GenerationTask(
        source_id="source-1",
        model_config_id="model-1",
        prompt="cat",
        params={"size": "1536x1024", "quality": "high", "n": 1},
    )
    config = PlatformConfig(
        id="openai",
        name="Relay",
        api_base_url="https://relay.example/v1",
        model_name="gpt-image-2",
    )

    payload = adapter.build_generation_payload(task, config)

    assert payload == {
        "model": "gpt-image-2",
        "prompt": "cat",
        "n": 1,
        "size": "1536x1024",
        "quality": "high",
    }


def test_diagnostic_copy_redacts_sensitive_values():
    adapter = OpenAIAdapter()
    diagnostic = adapter.build_request_diagnostic(
        url="https://relay.example/v1/images/generations",
        source={"name": "Relay", "auth_preset": "openai"},
        model={"display_name": "GPT Image", "model_id": "gpt-image-2"},
        payload={"model": "gpt-image-2", "size": "1024x1024"},
        headers={"Authorization": "Bearer sk-secret", "X-Test": "ok"},
        duration_ms=1234,
        status="FAILED",
        error="timeout",
    )

    text = json.dumps(diagnostic, ensure_ascii=False)
    assert "sk-secret" not in text
    assert diagnostic["headers"]["Authorization"] == "<redacted>"
    assert diagnostic["payload"]["model"] == "gpt-image-2"
