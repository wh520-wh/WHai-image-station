import base64
import io
import json

import httpx
import pytest
from PIL import Image

from src.adapters.openai_adapter import OpenAIAdapter
from src.config import constants
from src.models.platform_config import PlatformConfig
from src.models.task import GenerationTask


@pytest.mark.parametrize(
    "interface_type,model_id",
    [
        ("custom", "relay-model"),
        ("openai_images", "relay-model"),
        ("custom", "gpt-image-2"),
    ],
)
@pytest.mark.asyncio
async def test_declared_seed_and_negative_prompt_are_sent_to_compatible_request(
    tmp_path, monkeypatch, interface_type, model_id
):
    monkeypatch.setattr(constants, "GENERATIONS_DIR", str(tmp_path / "images"))
    monkeypatch.setattr(constants, "THUMBNAILS_DIR", str(tmp_path / "thumbs"))
    stream = io.BytesIO()
    Image.new("RGB", (8, 8)).save(stream, "PNG")
    encoded = base64.b64encode(stream.getvalue()).decode()
    captured = {}

    def handle(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"data": [{"b64_json": encoded}]})

    adapter = OpenAIAdapter()
    adapter._http_client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    config = PlatformConfig(
        id="test",
        name="Offline relay",
        api_base_url="https://relay.test/v1",
        model_name=model_id,
        interface_type=interface_type,
        api_key="synthetic-key",
    )
    try:
        result = await adapter.generate(
            GenerationTask(prompt="a tree", negative_prompt="blur", params={"seed": 0}), config
        )
        assert result.success
        assert captured["seed"] == 0
        assert captured["negative_prompt"] == "blur"
    finally:
        await adapter.close()


def test_gpt_image_payload_filters_seed_negative_and_style():
    adapter = OpenAIAdapter()
    payload = adapter.build_generation_payload(
        GenerationTask(prompt="a tree", negative_prompt="blur", params={"seed": 17, "style": "vivid"}),
        PlatformConfig(
            id="test",
            name="Offline GPT",
            api_base_url="https://api.openai.com/v1",
            interface_type="openai_images",
            model_name="gpt-image-2",
        ),
    )
    assert "seed" not in payload
    assert "negative_prompt" not in payload
    assert "style" not in payload
