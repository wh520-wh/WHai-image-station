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


def test_midjourney_generate_emits_diagnostic_with_url_on_network_error(monkeypatch):
    """Regression test: when an exception fires (e.g. httpx.ConnectError),
    the diagnostic must still include the URL field. T4 had a bug where
    the except-Exception branch passed url=""; T5's `url: str = ""` init
    before the try block ensures the URL is always preserved."""

    async def fake_post(self, url, **kwargs):
        raise httpx.ConnectError("connection refused", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    adapter = MidjourneyAdapter()
    task, config = _setup()
    result = asyncio.run(adapter.generate(task, config))
    assert result.success is False
    diag = result.raw_response["diagnostic"]
    assert isinstance(diag, Diagnostic)
    assert diag.category == Category.NETWORK
    url_fields = [f for f in diag.fields if f.name == "URL"]
    assert len(url_fields) == 1, f"expected 1 URL field, got {len(url_fields)}: {diag.fields}"
    assert "/imagine" in url_fields[0].value
