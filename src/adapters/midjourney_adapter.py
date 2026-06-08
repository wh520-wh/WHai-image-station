from .base import BaseAdapter, GenerationResult

import os
import httpx
import base64
from datetime import datetime

from src.adapters.errors import Category, Field, Diagnostic
from src.models.task import GenerationTask
from src.models.platform_config import PlatformConfig
from src.config import constants


class MidjourneyAdapter(BaseAdapter):
    platform_id = "midjourney"
    platform_name = "Midjourney"

    def get_params_schema(self) -> dict:
        return {
            "model": {
                "type": "select",
                "label": "模型版本",
                "options": ["V6", "V6.1", "V5.2", "V5.1", "Niji"],
                "default": "V6",
            },
            "aspect_ratio": {
                "type": "select",
                "label": "宽高比",
                "options": ["1:1", "16:9", "9:16", "4:3", "3:4", "2:3", "3:2"],
                "default": "1:1",
            },
            "style": {
                "type": "select",
                "label": "风格",
                "options": ["raw", "none", " Hayao", "Ghibli", "Steampunk"],
                "default": "raw",
            },
            "quality": {
                "type": "select",
                "label": "质量",
                "options": ["0.25", "0.5", "1"],
                "default": "1",
            },
            "seed": {
                "type": "input",
                "label": "种子",
                "placeholder": "留空随机",
            },
            "n": {
                "type": "select",
                "label": "数量",
                "options": ["1", "2"],
                "default": "1",
            },
            "tile": {
                "type": "checkbox",
                "label": "平铺模式",
                "default": False,
            },
            "no": {
                "type": "input",
                "label": "排除内容 (--no)",
                "placeholder": "如: text, watermark",
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

    async def generate(self, task: GenerationTask, config: PlatformConfig) -> GenerationResult:
        params = task.params or {}

        # 构建 prompt
        prompt_parts = [task.prompt]

        # 添加参数
        if params.get("model"):
            prompt_parts.append(f"--v {params['model'].lower()}")
        if params.get("aspect_ratio"):
            prompt_parts.append(f"--ar {params['aspect_ratio']}")
        if params.get("style") and params["style"] != "none":
            prompt_parts.append(f"--s {params['style']}")
        if params.get("quality"):
            prompt_parts.append(f"--q {params['quality']}")
        if params.get("seed"):
            prompt_parts.append(f"--seed {params['seed']}")
        if params.get("n", 1) > 1:
            prompt_parts.append(f"--n {params['n']}")
        if params.get("tile"):
            prompt_parts.append("--tile")
        if task.negative_prompt:
            prompt_parts.append(f"--no {task.negative_prompt}")

        full_prompt = " ".join(prompt_parts)

        # 构造请求体
        payload = {
            "prompt": full_prompt,
            "webhook_endpoint": None,
            "webhook_secret": None,
        }

        url: str = ""
        try:
            client = self.get_http_client(config)
            headers = self.build_headers(config)
            url = self.build_url(config.api_base_url, "/imagine", config)
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Midjourney API 通常返回任务 ID，需要轮询或 webhook
            task_id = data.get("id", str(task.id))
            image_url = data.get("image_url") or data.get("output", {}).get("url")

            if not image_url:
                return GenerationResult(
                    success=True,
                    image_paths=[],
                    raw_response=data,
                )

            # 下载图片
            os.makedirs(constants.GENERATIONS_DIR, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(
                constants.GENERATIONS_DIR,
                f"{task.id}_{timestamp}.png"
            )
            await self.download_image(image_url, save_path, config)
            self._create_thumbnail(save_path)

            return GenerationResult(success=True, image_paths=[save_path], raw_response=data)

        except httpx.HTTPStatusError as exc:
            original = f"HTTP错误 {exc.response.status_code}: {exc.response.text}"
            category = self.classify_status(exc.response.status_code)
            return GenerationResult(
                success=False,
                error=original,
                raw_response={"diagnostic": self._build_failure_diagnostic(
                    category, url, payload, original, exc.response.status_code,
                )},
            )
        except Exception as exc:
            original = f"生成失败: {exc}"
            category = self.classify_exception(exc)
            return GenerationResult(
                success=False,
                error=original,
                raw_response={"diagnostic": self._build_failure_diagnostic(
                    category, url, payload, original,
                )},
            )

    def _build_failure_diagnostic(
        self,
        category: Category,
        url: str,
        payload: dict,
        original: str,
        status_code: int | None = None,
    ) -> Diagnostic:
        fields: list[Field] = []
        if url:
            fields.append(Field(name="URL", value=url, issue="请求地址"))
        if status_code is not None:
            fields.append(Field(name="HTTP status", value=str(status_code), issue="响应状态码"))
        prompt_value = (payload or {}).get("prompt", "")
        if prompt_value:
            fields.append(Field(name="payload.prompt", value=str(prompt_value)[:200], issue="请求参数"))
        return Diagnostic(
            category=category,
            fields=tuple(fields),
            hint=self.hint_for_category(category),
            original=original,
            platform=self.platform_id,
        )