from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import httpx
from PIL import Image

import os

from src.config import constants
from src.config.utils import get_thumbnail_path
from src.models.task import GenerationTask
from src.models.platform_config import PlatformConfig
from src.adapters.errors import Category, Field, Diagnostic, AdapterError


AUTH_PRESETS = {
    "openai": ("Authorization", "Bearer {key}"),
    "anthropic": ("x-api-key", "{key}"),
    "gemini": ("x-goog-api-key", "{key}"),
    "xai": ("Authorization", "Bearer {key}"),
    "cohere": ("Authorization", "Bearer {key}"),
    "custom": ("Authorization", "Bearer {key}"),
}


@dataclass
class GenerationResult:
    success: bool
    image_paths: list[str] = None
    error: str = None
    raw_response: dict = None


class BaseAdapter(ABC):
    platform_id: str = ""
    platform_name: str = ""

    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None

    def _get_shared_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(constants.REQUEST_TIMEOUT, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._http_client

    async def close(self):
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    @abstractmethod
    def get_params_schema(self) -> dict:
        """返回该平台支持的参数定义"""
        pass

    @abstractmethod
    async def validate_config(self, config: PlatformConfig) -> bool:
        """验证配置是否有效"""
        pass

    @abstractmethod
    async def generate(self, task: GenerationTask, config: PlatformConfig) -> GenerationResult:
        """执行图片生成"""
        pass

    def build_headers(self, config: PlatformConfig) -> dict:
        """构建请求头"""
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            header_name, template = AUTH_PRESETS.get(config.auth_preset, AUTH_PRESETS["openai"])
            headers[header_name] = template.format(key=config.api_key)
        if config.custom_headers:
            headers.update(config.custom_headers)
        return headers

    def redact_headers(self, headers: dict) -> dict:
        sensitive = {"authorization", "x-api-key", "x-goog-api-key", "cookie"}
        return {
            key: "<redacted>" if key.lower() in sensitive else value
            for key, value in (headers or {}).items()
        }

    def report_error(
        self,
        category: Category,
        *,
        original: str = "",
        fields: list[Field] | None = None,
        hint: str | None = None,
        source_id: str = "",
    ) -> "AdapterError":
        diagnostic = Diagnostic(
            category=category,
            fields=tuple(fields or ()),
            hint=hint,
            original=original,
            platform=self.platform_id,
            source_id=source_id,
        )
        return AdapterError(str(diagnostic), diagnostic)

    @staticmethod
    def classify_status(status_code: int) -> Category:
        if status_code in (401, 403):
            return Category.AUTH
        if status_code == 429:
            return Category.RATE_LIMIT
        if 500 <= status_code < 600:
            return Category.SERVER
        if 400 <= status_code < 500:
            return Category.BAD_REQUEST
        return Category.UNKNOWN

    def build_url(self, base_url: str, path: str, config: Optional[PlatformConfig] = None) -> str:
        """Join API base URL and endpoint path for relay/proxy compatibility.
        当 interface_type 为 'custom' 时，base_url 将直接作为完整请求地址，不追加 path。
        """
        if config and config.interface_type == "custom":
            return base_url.rstrip('/')
        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    def get_http_client(self, config: PlatformConfig = None) -> httpx.AsyncClient:
        return self._get_shared_client()

    async def download_image(self, url: str, save_path: str, config: PlatformConfig) -> str:
        client = self._get_shared_client()
        headers = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        if config.custom_headers:
            headers.update(config.custom_headers)

        response = await client.get(url, headers=headers)
        response.raise_for_status()

        try:
            with open(save_path, "wb") as f:
                f.write(response.content)
        except (IOError, OSError) as e:
            raise IOError(f"Failed to save image to {save_path}: {e}") from e
        return save_path

    def _create_thumbnail(self, image_path: str):
        thumb_path = get_thumbnail_path(image_path)
        if not thumb_path:
            return
        os.makedirs(constants.THUMBNAILS_DIR, exist_ok=True)
        try:
            img = Image.open(image_path)
            img.thumbnail((200, 200))
            img.save(thumb_path, "JPEG", quality=85, optimize=True)
        except Exception:
            pass
