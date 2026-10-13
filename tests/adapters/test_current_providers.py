import base64
import io
import json

import httpx
import pytest
from PIL import Image

from src.adapters.native_adapters import FluxAdapter, GeminiAdapter, MiniMaxAdapter
from src.adapters.openai_adapter import OpenAIAdapter
from src.config import constants
from src.config.providers import PROVIDER_PRESETS, make_preset
from src.models.platform_config import PlatformConfig
from src.models.task import GenerationTask


def image_base64():
    stream = io.BytesIO()
    Image.new("RGBA", (16, 16), (20, 120, 80, 128)).save(stream, "PNG")
    return base64.b64encode(stream.getvalue()).decode()


@pytest.fixture
def image_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "GENERATIONS_DIR", str(tmp_path / "images"))
    monkeypatch.setattr(constants, "THUMBNAILS_DIR", str(tmp_path / "thumbs"))
    return tmp_path


def config_for(provider):
    source, models = make_preset(provider, "source")
    return PlatformConfig(
        id=provider,
        name=source["name"],
        api_base_url=source["api_base_url"],
        api_key="synthetic-key",
        auth_preset=source["auth_preset"],
        interface_type=source["interface_type"],
        model_name=models[0]["model_id"],
        response_format=source["response_format"],
    )


def test_presets_have_live_models_and_native_protocols():
    assert {"openai", "gemini", "minimax", "bfl"} <= PROVIDER_PRESETS.keys()
    for name in ("openai", "gemini", "bfl", "minimax"):
        source, models = make_preset(name, "source")
        assert source["api_base_url"].startswith("https://")
        assert models
        assert not any(model["model_id"].startswith("dall-e") for model in models)


@pytest.mark.asyncio
async def test_gemini_consumes_output_images_and_ignores_thought_images(image_dirs):
    captured = {}

    def handle(request):
        captured.update(url=str(request.url), payload=json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "steps": [
                    {"type": "thought", "summary": [{"type": "image", "data": "invalid"}]},
                    {"type": "model_output", "content": [{"type": "image", "data": image_base64()}]},
                ]
            },
        )

    adapter = GeminiAdapter()
    adapter._http_client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    try:
        result = await adapter.generate(
            GenerationTask(prompt="a tree", params={"size": "16:9", "quality": "2K"}), config_for("gemini")
        )
        assert result.success
        assert len(result.image_paths) == 1
        assert captured["url"].endswith("/interactions")
        assert captured["payload"]["response_format"]["image_size"] == "2K"
        assert list((image_dirs / "thumbs").glob("*.jpg"))
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_openai_reference_image_uses_edits_multipart(image_dirs):
    reference = image_dirs / "reference.png"
    reference.write_bytes(base64.b64decode(image_base64()))
    captured = {}

    def handle(request):
        captured.update(url=str(request.url), headers=dict(request.headers), body=request.content)
        return httpx.Response(200, json={"data": [{"b64_json": image_base64()}]})

    adapter = OpenAIAdapter()
    adapter._http_client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    try:
        result = await adapter.generate(
            GenerationTask(prompt="edit", reference_image_path=str(reference)), config_for("openai")
        )
        assert result.success
        assert captured["url"].endswith("/images/edits")
        assert "multipart/form-data" in captured["headers"]["content-type"]
        assert b"reference.png" in captured["body"]
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_minimax_checks_application_error_in_success_http_response(image_dirs):
    adapter = MiniMaxAdapter()
    adapter._http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"base_resp": {"status_code": 1008, "status_msg": "balance insufficient"}}
            )
        )
    )
    try:
        result = await adapter.generate(GenerationTask(prompt="a tree"), config_for("minimax"))
        assert not result.success
        assert "balance insufficient" in result.error
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_flux_waits_until_ready_and_downloads_without_api_credentials(image_dirs):
    polls = []

    def handle(request):
        if request.method == "POST":
            assert request.headers["x-key"] == "synthetic-key"
            return httpx.Response(200, json={"id": "job", "polling_url": "https://api.bfl.ai/v1/result/job"})
        if "result/job" in str(request.url):
            polls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "Pending"}
                if len(polls) == 1
                else {"status": "Ready", "result": {"sample": "https://delivery.test/image.png"}},
            )
        assert "x-key" not in request.headers
        assert "authorization" not in request.headers
        return httpx.Response(200, content=base64.b64decode(image_base64()))

    adapter = FluxAdapter()
    adapter._http_client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    try:
        result = await adapter.generate(GenerationTask(prompt="a tree"), config_for("bfl"))
        assert result.success
        assert len(polls) == 2
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_empty_image_response_is_a_failure(image_dirs):
    adapter = GeminiAdapter()
    adapter._http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"steps": []}))
    )
    try:
        result = await adapter.generate(GenerationTask(prompt="a tree"), config_for("gemini"))
        assert not result.success
        assert not result.image_paths
    finally:
        await adapter.close()
