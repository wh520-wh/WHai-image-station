"""Native image APIs; provider payloads are deliberately kept separate."""

import asyncio
import base64
import time
from urllib.parse import urlsplit

import httpx

from src.adapters.base import BaseAdapter, GenerationResult
from src.adapters.errors import Category, Diagnostic, Field
from src.models.platform_config import PlatformConfig
from src.models.task import GenerationTask


class NativeImageAdapter(BaseAdapter):
    def get_params_schema(self) -> dict:
        return {}

    async def validate_config(self, config: PlatformConfig) -> bool:
        return bool(config.api_key and config.model_name and urlsplit(config.api_base_url).scheme in {"http", "https"})

    async def generate(self, task: GenerationTask, config: PlatformConfig) -> GenerationResult:
        try:
            refs = await self.request_images(task, config)
            paths = await self.save_image_refs(refs, task, config)
            return GenerationResult(success=True, image_paths=paths)
        except Exception as exc:
            category = (
                self.classify_status(exc.response.status_code)
                if isinstance(exc, httpx.HTTPStatusError)
                else self.classify_exception(exc)
            )
            if isinstance(exc, ValueError):
                category = Category.CONTENT
            original = str(exc)
            if isinstance(exc, httpx.HTTPStatusError):
                original = f"HTTP {exc.response.status_code}：{exc.response.text[:1000]}"
            if config.api_key:
                original = original.replace(config.api_key, "***")
            diagnostic = Diagnostic(
                category=category,
                fields=(Field("来源", config.name, ""), Field("模型", config.model_name, "")),
                hint=self.hint_for_category(category),
                original=original,
                platform=self.platform_id,
                source_id=config.source_id,
            )
            return GenerationResult(success=False, error=original, raw_response={"diagnostic": diagnostic})

    async def request_images(self, task: GenerationTask, config: PlatformConfig) -> list[str]:
        raise NotImplementedError


class GeminiAdapter(NativeImageAdapter):
    platform_id = "gemini"
    platform_name = "Google Gemini"

    async def validate_config(self, config: PlatformConfig) -> bool:
        if not await super().validate_config(config):
            return False
        response = await self.get_http_client(config).get(
            self.build_url(config.api_base_url, f"/models/{config.model_name}"),
            headers=self.build_headers(config),
        )
        response.raise_for_status()
        return True

    async def request_images(self, task: GenerationTask, config: PlatformConfig) -> list[str]:
        parts = [{"type": "text", "text": task.prompt}]
        if task.reference_image_path:
            image, mime_type = await self.reference_data(task.reference_image_path)
            parts.append({"type": "image", "data": base64.b64encode(image).decode(), "mime_type": mime_type})
        payload = {
            "model": config.model_name,
            "input": parts,
            "response_format": {
                "type": "image",
                "aspect_ratio": task.params.get("size", "1:1"),
                "image_size": task.params.get("quality", "1K"),
            },
        }
        response = await self.get_http_client(config).post(
            self.build_url(config.api_base_url, "/interactions"),
            json=payload,
            headers=self.build_headers(config),
        )
        response.raise_for_status()
        data = response.json()
        refs = []
        for step in data.get("steps", []):
            if step.get("type") != "model_output":
                continue
            for block in step.get("content", []):
                if block.get("type") == "image" and block.get("data"):
                    refs.append(block["data"])
        return refs


class MiniMaxAdapter(NativeImageAdapter):
    platform_id = "minimax"
    platform_name = "MiniMax"

    async def request_images(self, task: GenerationTask, config: PlatformConfig) -> list[str]:
        payload = {
            "model": config.model_name,
            "prompt": task.prompt,
            "aspect_ratio": task.params.get("size", "1:1"),
            "n": int(task.params.get("n", 1)),
            "response_format": "url",
        }
        if len(task.prompt) > 1500:
            raise ValueError("MiniMax 提示词不能超过 1500 字符")
        if task.params.get("seed") not in (None, ""):
            payload["seed"] = int(task.params["seed"])
        if task.reference_image_path:
            image, mime_type = await self.reference_data(task.reference_image_path)
            payload["subject_reference"] = [
                {"type": "character", "image_file": f"data:{mime_type};base64,{base64.b64encode(image).decode()}"}
            ]
        response = await self.get_http_client(config).post(
            self.build_url(config.api_base_url, "/image_generation"),
            json=payload,
            headers=self.build_headers(config),
        )
        response.raise_for_status()
        data = response.json()
        if data.get("base_resp", {}).get("status_code", 0) != 0:
            raise ValueError(data["base_resp"].get("status_msg", "MiniMax 生成失败"))
        return data.get("data", {}).get("image_urls", [])


class FluxAdapter(NativeImageAdapter):
    platform_id = "bfl"
    platform_name = "Black Forest Labs"

    async def request_images(self, task: GenerationTask, config: PlatformConfig) -> list[str]:
        width, height = (int(value) for value in task.params.get("size", "1024x1024").split("x"))
        if width % 16 or height % 16 or not (256 <= width <= 2048 and 256 <= height <= 2048):
            raise ValueError("FLUX 尺寸须为 16 的倍数，宽高需在 256–2048 之间")
        payload = {"prompt": task.prompt, "width": width, "height": height}
        if task.params.get("seed") not in (None, ""):
            payload["seed"] = int(task.params["seed"])
        if task.reference_image_path:
            raise ValueError("当前 FLUX 预设支持文生图，请选择 OpenAI 或 Gemini 进行参考图编辑")
        client = self.get_http_client(config)
        headers = self.build_headers(config)
        response = await client.post(
            self.build_url(config.api_base_url, f"/{config.model_name}"), json=payload, headers=headers
        )
        response.raise_for_status()
        polling_url = response.json().get("polling_url")
        if not polling_url:
            raise ValueError("FLUX 未返回任务查询地址")
        origin = urlsplit(config.api_base_url)
        target = urlsplit(polling_url)
        trusted = target.hostname and (target.hostname == origin.hostname or target.hostname.endswith(".bfl.ai"))
        if target.scheme != "https" or not trusted:
            raise ValueError("FLUX 返回了不受信任的任务查询地址")
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            response = await client.get(polling_url, headers=headers)
            response.raise_for_status()
            result = response.json()
            if result.get("status") == "Ready":
                return [result.get("result", {}).get("sample", "")]
            if result.get("status") in {"Error", "Failed", "Request Moderated", "Content Moderated"}:
                raise ValueError(f"FLUX 任务未完成：{result.get('status')}")
        raise httpx.ReadTimeout("FLUX 等待结果超过 5 分钟，请先在服务商处查询任务结果")
