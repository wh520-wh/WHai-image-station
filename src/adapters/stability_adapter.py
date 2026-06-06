from .base import BaseAdapter, GenerationResult

import base64
import os
import httpx
from datetime import datetime

from src.models.task import GenerationTask
from src.models.platform_config import PlatformConfig
from src.config import constants


class StabilityAdapter(BaseAdapter):
    platform_id = "stability"
    platform_name = "Stable Diffusion"

    def get_params_schema(self) -> dict:
        return {
            "engine": {
                "type": "select",
                "label": "引擎",
                "options": [
                    "stable-diffusion-xl-1024-v1-0",
                    "stable-diffusion-v1-6",
                    "stable-diffusion-xl-beta-v2-2-2",
                ],
                "default": "stable-diffusion-xl-1024-v1-0",
            },
            "height": {
                "type": "select",
                "label": "高度",
                "options": ["320", "384", "512", "640", "768", "896", "1024"],
                "default": "1024",
            },
            "width": {
                "type": "select",
                "label": "宽度",
                "options": ["320", "384", "512", "640", "768", "896", "1024"],
                "default": "1024",
            },
            "steps": {
                "type": "slider",
                "label": "步数",
                "min": 10,
                "max": 50,
                "default": 30,
            },
            "seed": {
                "type": "input",
                "label": "种子",
                "placeholder": "留空随机",
            },
            "style_preset": {
                "type": "select",
                "label": "风格预设",
                "options": [
                    "none", "3d-model", "analog-film", "anime", "cinematic",
                    "comic-book", "digital-art", "enhance", "fantasy-art",
                    "isometric", "line-art", "low-poly", "modeling-compound",
                    "neon-punk", "origami", "photographic", "pixel-art",
                    "texture", "tileable",
                ],
                "default": "none",
            },
        }

    async def validate_config(self, config: PlatformConfig) -> bool:
        if not config.api_key or not config.api_base_url:
            return False
        try:
            client = self.get_http_client(config)
            response = await client.get(
                self.build_url(config.api_base_url, "/engines/list", config),
                headers=self.build_headers(config),
            )
            return 200 <= response.status_code < 300
        except Exception:
            return False

    async def generate(self, task: GenerationTask, config: PlatformConfig) -> GenerationResult:
        params = task.params or {}
        engine = params.get("engine", "stable-diffusion-xl-1024-v1-0")
        height = int(params.get("height", 1024))
        width = int(params.get("width", 1024))
        steps = int(params.get("steps", 30))
        seed = params.get("seed")
        style_preset = params.get("style_preset", "none")
        n = int(params.get("n", 1))

        # 构建请求体
        payload = {
            "text_prompts": [{"text": task.prompt, "weight": 1}],
            "cfg_scale": params.get("cfg_scale", 7),
            "height": height,
            "width": width,
            "steps": steps,
            "samples": n,
        }
        if task.negative_prompt:
            payload["text_prompts"].append({"text": task.negative_prompt, "weight": -1})
        if seed:
            payload["seed"] = int(seed)
        if style_preset != "none":
            payload["style_preset"] = style_preset

        # 参考图（image-to-image）
        if task.reference_image_path:
            with open(task.reference_image_path, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode()
            payload["image"] = img_base64
            payload["image_strength"] = params.get("image_strength", 0.35)

        try:
            client = self.get_http_client(config)
            headers = self.build_headers(config)
            headers["Accept"] = "application/json"
            url = self.build_url(config.api_base_url, f"/generation/{engine}/text-to-image", config)
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            # 保存图片
            os.makedirs(constants.GENERATIONS_DIR, exist_ok=True)
            image_paths = []
            artifacts = data.get("artifacts", [])
            for i, artifact in enumerate(artifacts):
                if artifact.get("base64"):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    save_path = os.path.join(
                        constants.GENERATIONS_DIR,
                        f"{task.id}_{i+1}_{timestamp}.png"
                    )
                    img_bytes = base64.b64decode(artifact["base64"])
                    with open(save_path, "wb") as f:
                        f.write(img_bytes)
                    image_paths.append(save_path)
                    self._create_thumbnail(save_path)

            return GenerationResult(success=True, image_paths=image_paths, raw_response=data)

        except httpx.HTTPStatusError as e:
            return GenerationResult(success=False, error=f"HTTP错误: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            return GenerationResult(success=False, error=f"生成失败: {str(e)}")