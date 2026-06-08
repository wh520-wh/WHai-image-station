from .base import BaseAdapter, GenerationResult

import base64
import os
import time
from datetime import datetime

import httpx

from src.adapters.errors import Category, Field, Diagnostic
from src.models.task import GenerationTask
from src.models.platform_config import PlatformConfig
from src.config import constants


class OpenAIAdapter(BaseAdapter):
    platform_id = "openai"
    platform_name = "DALL·E / OpenAI Compatible"

    def get_params_schema(self) -> dict:
        return {
            "model": {
                "type": "input",
                "label": "模型",
                "options": ["dall-e-3", "gpt-image-1", "dall-e-2"],
                "default": "dall-e-3",
                "placeholder": "中转模型名，如 gpt-image-1",
            },
            "size": {
                "type": "select",
                "label": "尺寸",
                "options": ["1024x1024", "1792x1024", "1024x1792"],
                "default": "1024x1024",
            },
            "quality": {
                "type": "select",
                "label": "质量",
                "options": ["standard", "hd"],
                "default": "standard",
            },
            "style": {
                "type": "select",
                "label": "风格",
                "options": ["", "vivid", "natural"],
                "default": "",
            },
            "n": {
                "type": "select",
                "label": "数量",
                "options": ["1", "2", "4", "6", "8", "10"],
                "default": "1",
            },
        }

    async def validate_config(self, config: PlatformConfig) -> bool:
        if not config.api_key or not config.api_base_url:
            return False
        try:
            client = self.get_http_client(config)
            response = await client.get(
                self.build_url(config.api_base_url, "/models", config),
                headers=self.build_headers(config),
            )
            return 200 <= response.status_code < 300
        except Exception:
            return False

    def build_generation_payload(self, task: GenerationTask, config: PlatformConfig | None = None) -> dict:
        params = task.params or {}
        payload = {
            "model": (config.model_name if config and config.model_name else "") or params.get("model"),
            "prompt": task.prompt,
            "n": int(params.get("n", 1)),
            "size": params.get("size") or "1024x1024",
        }
        if params.get("quality"):
            payload["quality"] = params["quality"]
        if params.get("style"):
            payload["style"] = params["style"]
        if task.negative_prompt:
            payload["negative_prompt"] = task.negative_prompt
        return payload

    async def generate(self, task: GenerationTask, config: PlatformConfig) -> GenerationResult:
        payload = self.build_generation_payload(task, config)
        generation_url = self.build_url(config.api_base_url, "/images/generations", config)
        headers = self.build_headers(config)
        source_info = {
            "name": config.source_name or config.name,
            "auth_preset": config.auth_preset,
            "interface_type": config.interface_type,
        }
        model_info = {
            "display_name": config.model_display_name or config.model_name,
            "model_id": config.model_name,
        }
        started_at = time.perf_counter()
        try:
            client = self.get_http_client(config)
            response = await client.post(
                generation_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            duration_ms = int((time.perf_counter() - started_at) * 1000)

            os.makedirs(constants.GENERATIONS_DIR, exist_ok=True)
            image_refs = self._extract_image_refs(data, config.response_format)
            if not image_refs:
                original = f"响应格式不匹配：当前使用「{config.response_format}」解析，未提取到图片。请检查设置的响应格式选项。原始响应: {str(data)[:500]}"
                diagnostic = self._build_diagnostic(
                    Category.CONTENT, generation_url, payload, duration_ms,
                    source_info, original,
                )
                return GenerationResult(
                    success=False,
                    error=original,
                    raw_response={"diagnostic": diagnostic},
                )
            image_paths = []
            for index, image_ref in enumerate(image_refs):
                if not image_ref:
                    continue
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = os.path.join(constants.GENERATIONS_DIR, f"{task.id}_{index + 1}_{timestamp}.png")
                if image_ref.startswith("data:"):
                    image_bytes = base64.b64decode(image_ref.split(",", 1)[1])
                    with open(save_path, "wb") as file:
                        file.write(image_bytes)
                elif len(image_ref) > 100 and not image_ref.startswith(("http://", "https://")):
                    with open(save_path, "wb") as file:
                        file.write(base64.b64decode(image_ref))
                else:
                    await self.download_image(image_ref, save_path, config)
                image_paths.append(save_path)
                self._create_thumbnail(save_path)

            diagnostic = self._build_diagnostic(
                Category.UNKNOWN, generation_url, payload, duration_ms,
                source_info, original=None,
            )
            return GenerationResult(
                success=True,
                image_paths=image_paths,
                raw_response={"data": data, "diagnostic": diagnostic},
            )
        except httpx.HTTPStatusError as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            original = self.format_http_status_error(exc)
            category = self.classify_status(exc.response.status_code)
            diagnostic = self._build_diagnostic(
                category, generation_url, payload, duration_ms,
                source_info, original,
                status_code=exc.response.status_code,
            )
            return GenerationResult(
                success=False,
                error=original,
                raw_response={"diagnostic": diagnostic},
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            original = self.format_generation_exception(exc, generation_url, payload)
            category = self.classify_exception(exc)
            diagnostic = self._build_diagnostic(
                category, generation_url, payload, duration_ms,
                source_info, original,
            )
            return GenerationResult(
                success=False,
                error=original,
                raw_response={"diagnostic": diagnostic},
            )

    def _build_diagnostic(
        self,
        category: Category,
        url: str,
        payload: dict,
        duration_ms: int,
        source_info: dict,
        original: str | None,
        status_code: int | None = None,
    ) -> Diagnostic:
        fields: list[Field] = []
        fields.append(Field(name="URL", value=url, issue="请求地址"))
        if status_code is not None:
            fields.append(Field(name="HTTP status", value=str(status_code), issue="响应状态码"))
        for key, value in (payload or {}).items():
            if value in (None, ""):
                continue
            fields.append(Field(name=f"payload.{key}", value=str(value)[:200], issue="请求参数"))
        return Diagnostic(
            category=category,
            fields=tuple(fields),
            hint=self.hint_for_category(category),
            original=original or "",
            platform=self.platform_id,
            source_id=source_info.get("name", ""),
        )

    def _extract_image_refs(self, data: dict, response_format: str = "openai") -> list[str]:
        """按指定的响应格式提取图片 URL/base64 列表。"""
        items = data.get("data", [])
        if response_format == "openai":
            if isinstance(items, list):
                return [item.get("url") or item.get("b64_json") or "" for item in items if isinstance(item, dict)]
            return []
        if response_format == "minimax":
            if isinstance(items, dict) and "image_urls" in items:
                return items["image_urls"]
            return []
        if response_format == "auto":
            return self._extract_auto(items) or self._extract_auto(data)
        return []

    def _extract_auto(self, obj) -> list[str]:
        if not isinstance(obj, dict):
            return []
        for key in ("image_urls", "images", "urls", "output", "url", "image_url", "data"):
            val = obj.get(key)
            if isinstance(val, str):
                return [val]
            if isinstance(val, list) and val and isinstance(val[0], str):
                return val
            if isinstance(val, list) and val and isinstance(val[0], dict):
                return [item.get("url") or item.get("b64_json") or "" for item in val if isinstance(item, dict)]
        return []

    def build_request_diagnostic(
        self,
        url: str,
        source: dict,
        model: dict,
        payload: dict,
        headers: dict,
        duration_ms: int,
        status: str,
        error: str | None = None,
        response_summary: str | None = None,
    ) -> dict:
        return {
            "request_url": url,
            "source": source,
            "model": model,
            "payload": payload,
            "headers": self.redact_headers(headers),
            "duration_ms": duration_ms,
            "status": status,
            "error": error,
            "response_summary": response_summary,
        }

    def format_http_status_error(self, exc: httpx.HTTPStatusError) -> str:
        response = exc.response
        message = response.text
        try:
            data = response.json()
            error = data.get("error") if isinstance(data, dict) else None
            if isinstance(error, dict):
                message = error.get("message") or message
            elif isinstance(error, str):
                message = error
        except ValueError:
            pass
        return f"HTTP错误 {response.status_code}: {message}"

    def format_generation_exception(self, exc: Exception, url: str = "", payload: dict | None = None) -> str:
        if isinstance(exc, httpx.ReadTimeout):
            message = "生成超时：中转站或模型生成图片太久没有返回结果。可以稍后重试，或换更小尺寸/更低质量。"
        elif isinstance(exc, httpx.ConnectTimeout):
            message = "连接超时：程序连不上中转站，请检查网络、代理或 Base URL。"
        elif isinstance(exc, httpx.ConnectError):
            message = "连接失败：无法连接到中转站，请检查网络、代理或 Base URL。"
        else:
            raw_message = str(exc).strip()
            message = raw_message or exc.__class__.__name__
        details = [message]
        if url:
            details.append(f"请求地址: {url}")
        if payload:
            payload_summary = {
                key: payload.get(key)
                for key in ("model", "size", "quality", "n")
                if payload.get(key) is not None
            }
            details.append(
                "请求参数: "
                + ", ".join(f"{key}={value}" for key, value in payload_summary.items())
            )
        return "；".join(details)
