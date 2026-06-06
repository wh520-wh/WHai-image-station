import os
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from src.adapters.base import BaseAdapter, GenerationResult


class _DummyAdapter(BaseAdapter):
    platform_id = "dummy"
    platform_name = "Dummy"
    def get_params_schema(self): return {}
    async def validate_config(self, config): return True
    async def generate(self, task, config): return GenerationResult(success=True)


@pytest.mark.asyncio
async def test_download_image_raises_typed_exception_on_http_error(tmp_path):
    adapter = _DummyAdapter()
    config = MagicMock()
    config.api_key = "key"
    config.custom_headers = None
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )
    adapter._get_shared_client = lambda: MagicMock(get=AsyncMock(return_value=mock_response))
    with pytest.raises(httpx.HTTPStatusError):
        await adapter.download_image("http://example.com/img.png", str(tmp_path / "out.png"), config)


@pytest.mark.asyncio
async def test_download_image_returns_path_on_success(tmp_path):
    adapter = _DummyAdapter()
    config = MagicMock()
    config.api_key = "key"
    config.custom_headers = None
    mock_response = MagicMock()
    mock_response.content = b"fake-image-bytes"
    mock_response.raise_for_status = MagicMock()
    adapter._get_shared_client = lambda: MagicMock(get=AsyncMock(return_value=mock_response))
    result = await adapter.download_image("http://example.com/img.png", str(tmp_path / "out.png"), config)
    assert result == str(tmp_path / "out.png")
    assert (tmp_path / "out.png").read_bytes() == b"fake-image-bytes"


@pytest.mark.asyncio
async def test_download_image_wraps_io_error(tmp_path):
    adapter = _DummyAdapter()
    config = MagicMock()
    config.api_key = "key"
    config.custom_headers = None
    mock_response = MagicMock()
    mock_response.content = b"data"
    mock_response.raise_for_status = MagicMock()
    adapter._get_shared_client = lambda: MagicMock(get=AsyncMock(return_value=mock_response))
    # 传入目录作为保存路径，触发 IOError
    with pytest.raises(IOError, match="Failed to save image"):
        await adapter.download_image("http://example.com/img.png", str(tmp_path), config)
