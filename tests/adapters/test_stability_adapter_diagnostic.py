import asyncio
import httpx

from src.adapters.errors import Category, Diagnostic
from src.adapters.stability_adapter import StabilityAdapter
from src.models.task import GenerationTask
from src.models.platform_config import PlatformConfig


def _setup():
    task = GenerationTask(
        id="00000000-0000-0000-0000-000000000001",
        platform_id="stability",
        prompt="a forest",
        params={"n": 1},
    )
    config = PlatformConfig(
        id="stability",
        name="Stability",
        api_key="k",
        api_base_url="https://api.example.com",
        auth_preset="openai",
        interface_type="openai_images",
        model_name="stable-diffusion-xl-1024-v1-0",
        response_format="openai",
    )
    return task, config


def test_stability_generate_emits_diagnostic_on_500(monkeypatch):
    async def fake_post(self, url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(500, request=request, text="internal error")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    adapter = StabilityAdapter()
    task, config = _setup()
    result = asyncio.run(adapter.generate(task, config))
    assert result.success is False
    diag = result.raw_response["diagnostic"]
    assert isinstance(diag, Diagnostic)
    assert diag.category == Category.SERVER
    assert "500" in diag.original
    assert diag.platform == "stability"
