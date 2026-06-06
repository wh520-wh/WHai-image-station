from src.adapters.base import BaseAdapter
from src.models.platform_config import PlatformConfig


class DummyAdapter(BaseAdapter):
    def get_params_schema(self):
        return {}

    async def validate_config(self, config):
        return True

    async def generate(self, task, config):
        return None


def test_http_client_accepts_saved_proxy_setting():
    adapter = DummyAdapter()
    config = PlatformConfig(
        id="dummy",
        name="Dummy",
        api_base_url="https://example.test",
        proxy="http://127.0.0.1:8080",
    )
    client = adapter.get_http_client(config)
    try:
        assert client.timeout.connect == 10.0
    finally:
        import asyncio
        asyncio.run(client.aclose())


def test_http_client_allows_long_image_generation_waits():
    adapter = DummyAdapter()
    config = PlatformConfig(
        id="dummy",
        name="Dummy",
        api_base_url="https://example.test",
    )
    client = adapter.get_http_client(config)
    try:
        assert client.timeout.read >= 300.0
    finally:
        import asyncio
        asyncio.run(client.aclose())
