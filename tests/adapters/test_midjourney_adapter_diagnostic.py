import asyncio
import httpx

from src.adapters.errors import Category, Diagnostic
from src.adapters.midjourney_adapter import MidjourneyAdapter
from src.models.task import GenerationTask
from src.models.platform_config import PlatformConfig


def _setup():
    task = GenerationTask(platform_id="midjourney", prompt="a city", params={"n": 1})
    config = PlatformConfig(
        id="midjourney",
        name="Midjourney",
        api_key="k",
        api_base_url="https://api.example.com",
        auth_preset="openai",
        interface_type="openai_images",
        model_name="V6",
        response_format="openai",
    )
    return task, config


def test_midjourney_generate_emits_diagnostic_on_429(monkeypatch):
    async def fake_post(self, url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(429, request=request, text="rate limited")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    adapter = MidjourneyAdapter()
    task, config = _setup()
    result = asyncio.run(adapter.generate(task, config))
    assert result.success is False
    diag = result.raw_response["diagnostic"]
    assert isinstance(diag, Diagnostic)
    assert diag.category == Category.RATE_LIMIT
    assert diag.platform == "midjourney"
