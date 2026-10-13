import os
import time
from urllib.parse import urlsplit

import httpx

from src.adapters.errors import Category, Diagnostic, Field
from src.config import constants
from src.config.providers import RETIRED_MODELS, model_capabilities
from src.models.platform_config import PlatformConfig
from src.models.task import GenerationTask

from .base import BaseAdapter, GenerationResult


class OpenAIAdapter(BaseAdapter):
    platform_id = "openai"
    platform_name = "GPT Image / OpenAI Compatible"

    def get_params_schema(self) -> dict:
        return {
            "model": {
                "type": "input",
                "label": "模型",
                "options": ["gpt-image-2.5-flare", "gpt-image-2.5-sunburst", "gpt-image-2"],
                "default": "gpt-image-2.5-flare",
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
        gpt_image = str(payload["model"] or "").startswith("gpt-image-")
        caps = model_capabilities(config.interface_type if config else "openai_images", str(payload["model"] or ""))
        if gpt_image:
            payload["quality"] = {"standard": "auto", "hd": "high"}.get(
                str(payload.get("quality") or "auto"), payload.get("quality", "auto")
            )
            payload["size"] = {"1792x1024": "1536x1024", "1024x1792": "1024x1536"}.get(payload["size"], payload["size"])
            payload.pop("style", None)
            if caps["format"]:
                for key in ("output_format", "background"):
                    if params.get(key):
                        payload[key] = params[key]
            if payload.get("background") == "transparent" and payload.get("output_format") == "jpeg":
                raise ValueError("透明背景请选择 PNG 或 WebP 格式")
        if caps["seed"] and params.get("seed") is not None:
            payload["seed"] = params["seed"]
        if task.negative_prompt and caps["negative"]:
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
        started_at = time.perf_counter()
        try:
            if config.model_name in RETIRED_MODELS and urlsplit(config.api_base_url).hostname == "api.openai.com":
                raise ValueError("DALL·E 2/3 已退役，请在来源设置中选择 GPT Image 模型")
            client = self.get_http_client(config)
            if task.reference_image_path:
                if config.interface_type != "openai_images" or not config.model_name.startswith("gpt-image-"):
                    raise ValueError("当前模型不支持参考图编辑，请选择 GPT Image 模型")
                generation_url = self.build_url(config.api_base_url, "/images/edits", config)
                image_bytes, mime_type = await self.reference_data(task.reference_image_path)
                headers.pop("Content-Type", None)
                response = await client.post(
                    generation_url,
                    data={key: str(value) for key, value in payload.items()},
                    files={"image": (os.path.basename(task.reference_image_path), image_bytes, mime_type)},
                    headers=headers,
                )
            else:
                response = await client.post(generation_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            duration_ms = int((time.perf_counter() - started_at) * 1000)

            os.makedirs(constants.GENERATIONS_DIR, exist_ok=True)
            image_refs = self._extract_image_refs(data, config.response_format)
            if not image_refs:
                original = f"响应格式不匹配：当前使用「{config.response_format}」解析，未提取到图片。请检查设置的响应格式选项。原始响应: {str(data)[:500]}"
                diagnostic = self._build_diagnostic(
                    Category.CONTENT,
                    generation_url,
                    payload,
                    duration_ms,
                    source_info,
                    original,
                )
                return GenerationResult(
                    success=False,
                    error=original,
                    raw_response={"diagnostic": diagnostic},
                )
            image_paths = await self.save_image_refs(image_refs, task, config)

            diagnostic = self._build_diagnostic(
                Category.UNKNOWN,
                generation_url,
                payload,
                duration_ms,
                source_info,
                original=None,
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
                category,
                generation_url,
                payload,
                duration_ms,
                source_info,
                original,
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
                category,
                generation_url,
                payload,
                duration_ms,
                source_info,
                original,
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
            hint=self.hint_for_category(category) if original else "请求完成，图片已保存到本地。",
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
                key: payload.get(key) for key in ("model", "size", "quality", "n") if payload.get(key) is not None
            }
            details.append("请求参数: " + ", ".join(f"{key}={value}" for key, value in payload_summary.items()))
        return "；".join(details)
