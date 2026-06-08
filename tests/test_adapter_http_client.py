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


from src.adapters.errors import Category, AdapterError


class _ProbeAdapter(BaseAdapter):
    platform_id = "probe"

    def get_params_schema(self):
        return {}

    async def validate_config(self, config):
        return True

    async def generate(self, task, config):
        return None


def test_report_error_returns_adapter_error_with_diagnostic():
    adapter = _ProbeAdapter()
    err = adapter.report_error(
        category=Category.AUTH,
        original="HTTP 401: Unauthorized",
        fields=[],
        hint="请检查 API Key",
    )
    assert isinstance(err, AdapterError)
    assert err.diagnostic.category == Category.AUTH
    assert err.diagnostic.original == "HTTP 401: Unauthorized"
    assert err.diagnostic.hint == "请检查 API Key"
    assert err.diagnostic.platform == "probe"


def test_classify_status_maps_status_codes_to_categories():
    adapter = _ProbeAdapter()
    assert adapter.classify_status(401) == Category.AUTH
    assert adapter.classify_status(403) == Category.AUTH
    assert adapter.classify_status(429) == Category.RATE_LIMIT
    assert adapter.classify_status(500) == Category.SERVER
    assert adapter.classify_status(502) == Category.SERVER
    assert adapter.classify_status(503) == Category.SERVER
    assert adapter.classify_status(400) == Category.BAD_REQUEST
    assert adapter.classify_status(404) == Category.BAD_REQUEST
    assert adapter.classify_status(200) == Category.UNKNOWN
