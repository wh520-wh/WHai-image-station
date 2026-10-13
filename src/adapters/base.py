import asyncio
import base64
import io
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from PIL import Image

from src.adapters.errors import AdapterError, Category, Diagnostic, Field
from src.config import constants
from src.config.utils import get_thumbnail_path
from src.managers.image_assets import EXTENSIONS, create_thumbnail
from src.models.platform_config import PlatformConfig
from src.models.task import GenerationTask

AUTH_PRESETS = {
    "openai": ("Authorization", "Bearer {key}"),
    "anthropic": ("x-api-key", "{key}"),
    "gemini": ("x-goog-api-key", "{key}"),
    "xai": ("Authorization", "Bearer {key}"),
    "cohere": ("Authorization", "Bearer {key}"),
    "custom": ("Authorization", "Bearer {key}"),
    "bfl": ("x-key", "{key}"),
}


@dataclass
class GenerationResult:
    success: bool
    image_paths: list[str] | None = None
    error: str | None = None
    raw_response: dict | None = None


class BaseAdapter(ABC):
    platform_id: str = ""
    platform_name: str = ""

    def __init__(self):
        self._http_client: httpx.AsyncClient | None = None
        self._proxy_clients: dict[tuple[int, str], httpx.AsyncClient] = {}

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
        for client in self._proxy_clients.values():
            await client.aclose()
        self._proxy_clients.clear()

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
        if config.api_key and config.auth_preset != "none":
            header_name, template = AUTH_PRESETS.get(config.auth_preset, AUTH_PRESETS["openai"])
            headers[header_name] = template.format(key=config.api_key)
        if config.custom_headers:
            headers.update(config.custom_headers)
        return headers

    def redact_headers(self, headers: dict) -> dict:
        return {
            key: "<redacted>"
            if any(word in key.lower() for word in ("authorization", "key", "token", "secret", "cookie"))
            else value
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

    @staticmethod
    def classify_exception(exc: BaseException) -> Category:
        if isinstance(exc, (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError, httpx.TimeoutException)):
            return Category.NETWORK
        return Category.UNKNOWN

    @staticmethod
    def hint_for_category(category: Category) -> str | None:
        hints = {
            Category.AUTH: "请检查设置中的 API Key 是否正确。",
            Category.RATE_LIMIT: "请求频率超限，请稍后重试。",
            Category.NETWORK: "网络问题：检查 Base URL、代理或中转站可用性。",
            Category.SERVER: "服务器错误，请稍后重试。",
            Category.BAD_REQUEST: "请求参数不合法，请检查尺寸/质量等参数。",
            Category.CONTENT: "响应内容无法解析，请检查响应格式设置或模型兼容性。",
            Category.UNKNOWN: "请复制诊断发给开发者。",
        }
        return hints.get(category)

    def build_url(self, base_url: str, path: str, config: PlatformConfig | None = None) -> str:
        """Join API base URL and endpoint path for relay/proxy compatibility.
        当 interface_type 为 'custom' 时，base_url 将直接作为完整请求地址，不追加 path。
        """
        if config and config.interface_type == "custom":
            return base_url.rstrip("/")
        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    def get_http_client(self, config: PlatformConfig | None = None) -> httpx.AsyncClient:
        if config and config.proxy:
            try:
                loop_id = id(asyncio.get_running_loop())
            except RuntimeError:
                loop_id = 0
            cache_key = (loop_id, config.proxy)
            if cache_key not in self._proxy_clients:
                self._proxy_clients[cache_key] = httpx.AsyncClient(
                    proxy=config.proxy,
                    timeout=httpx.Timeout(constants.REQUEST_TIMEOUT, connect=10.0),
                    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                )
            return self._proxy_clients[cache_key]
        return self._get_shared_client()

    async def download_image(self, url: str, save_path: str, config: PlatformConfig) -> str:
        client = self.get_http_client(config)
        # Signed CDN URLs do not need the service's credentials.
        source_origin = urlsplit(config.api_base_url)
        target_origin = urlsplit(url)
        if target_origin.scheme not in {"http", "https"}:
            raise ValueError("图片下载地址必须使用 HTTP 或 HTTPS")
        same_origin = (source_origin.scheme, source_origin.netloc) == (target_origin.scheme, target_origin.netloc)
        headers = self.build_headers(config) if same_origin else {}

        response = await client.get(url, headers=headers)
        response.raise_for_status()

        try:
            with open(save_path, "wb") as f:
                f.write(response.content)
        except OSError as e:
            raise OSError(f"Failed to save image to {save_path}: {e}") from e
        return save_path

    async def reference_data(self, path: str) -> tuple[bytes, str]:
        reference = Path(path)
        if reference.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("参考图不能超过 50 MB")
        data = await asyncio.to_thread(reference.read_bytes)
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("参考图必须是 PNG、JPEG 或 WebP")
            mime_type = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[img.format]
            img.verify()
        return data, mime_type

    async def save_image_refs(self, refs: list[str], task: GenerationTask, config: PlatformConfig) -> list[str]:
        if not refs or not any(refs):
            raise ValueError("服务商没有返回图片，任务尚未完成或响应格式不匹配")
        paths = []
        os.makedirs(constants.GENERATIONS_DIR, exist_ok=True)
        for index, ref in enumerate(refs):
            if not ref:
                continue
            save_path = os.path.join(constants.GENERATIONS_DIR, f"{task.id}_{index + 1}.png")
            try:
                if ref.startswith(("https://", "http://")):
                    await self.download_image(ref, save_path, config)
                else:
                    encoded = ref.split(",", 1)[1] if ref.startswith("data:") else ref
                    data = base64.b64decode(encoded, validate=True)
                    await asyncio.to_thread(Path(save_path).write_bytes, data)
                # Keep file extensions consistent with the provider's actual encoding.
                with Image.open(save_path) as image:
                    extension = EXTENSIONS.get(image.format or "")
                    image.verify()
                if not extension:
                    raise ValueError("返回的文件不是支持的 PNG、JPEG 或 WebP 图片")
                correct_path = str(Path(save_path).with_suffix(extension))
                if correct_path != save_path:
                    await asyncio.to_thread(os.replace, save_path, correct_path)
                    save_path = correct_path
                await asyncio.to_thread(self._create_thumbnail, save_path)
                paths.append(save_path)
            except BaseException:
                for path in [*paths, save_path]:
                    Path(path).unlink(missing_ok=True)
                    Path(get_thumbnail_path(path)).unlink(missing_ok=True)
                raise
        return paths

    def _create_thumbnail(self, image_path: str):
        try:
            create_thumbnail(image_path)
        except Exception:
            pass
