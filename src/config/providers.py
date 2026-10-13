"""Official source presets and model capabilities, verified 2026-10-12."""

from copy import deepcopy

INTERFACE_LABELS = {
    "openai_images": "OpenAI / 兼容图像 API",
    "gemini": "Google Gemini · Interactions",
    "bfl": "Black Forest Labs · FLUX",
    "minimax": "MiniMax 图像 API",
    "custom": "自定义完整地址 · OpenAI 请求格式",
}

PROVIDER_PRESETS = {
    "openai": {
        "name": "OpenAI",
        "interface_type": "openai_images",
        "auth_preset": "openai",
        "api_base_url": "https://api.openai.com/v1",
        "response_format": "openai",
        "docs_url": "https://developers.openai.com/api/docs/guides/image-generation",
        "description": "GPT Image · 图像生成、参考图编辑与透明背景",
        "models": [
            ("GPT Image 2.5 Flare · 快速", "gpt-image-2.5-flare"),
            ("GPT Image 2.5 Sunburst · 精细", "gpt-image-2.5-sunburst"),
            ("GPT Image 2", "gpt-image-2"),
            ("GPT Image 1 Mini · 轻量", "gpt-image-1-mini"),
        ],
    },
    "gemini": {
        "name": "Google Gemini",
        "interface_type": "gemini",
        "auth_preset": "gemini",
        "api_base_url": "https://generativelanguage.googleapis.com/v1beta",
        "response_format": "auto",
        "docs_url": "https://ai.google.dev/gemini-api/docs/image-generation",
        "description": "Nano Banana · 图像生成、参考图编辑与多种画幅",
        "models": [
            ("Nano Banana 2.1", "gemini-nano-banana-2.1"),
            ("Nano Banana Pro", "gemini-3-pro-image"),
            ("Nano Banana 2 Lite", "gemini-3.1-flash-lite-image"),
        ],
    },
    "bfl": {
        "name": "Black Forest Labs",
        "interface_type": "bfl",
        "auth_preset": "bfl",
        "api_base_url": "https://api.bfl.ai/v1",
        "response_format": "auto",
        "docs_url": "https://docs.bfl.ai/quick_start/generating_images",
        "description": "FLUX.2 · 摄影与设计，自动等待异步生成结果",
        "models": [("FLUX.2 Pro", "flux-2-pro"), ("FLUX.2 Max", "flux-2-max"), ("FLUX.2 Klein 4B", "flux-2-klein-4b")],
    },
    "minimax": {
        "name": "MiniMax",
        "interface_type": "minimax",
        "auth_preset": "openai",
        "api_base_url": "https://api.minimax.io/v1",
        "response_format": "minimax",
        "docs_url": "https://platform.minimax.io/docs/api-reference/image-generation-t2i",
        "description": "Image-01 · 图像生成与人物参考图",
        "models": [("MiniMax Image-01", "image-01")],
    },
    "compatible": {
        "name": "OpenAI 兼容来源",
        "interface_type": "openai_images",
        "auth_preset": "openai",
        "api_base_url": "",
        "response_format": "auto",
        "docs_url": "",
        "description": "用于中转或自托管服务，自行填写地址与模型 ID",
        "models": [],
    },
}

RETIRED_MODELS = {"dall-e-2", "dall-e-3"}
ASPECT_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"]


def make_preset(preset_id: str, source_id: str) -> tuple[dict, list[dict]]:
    preset = deepcopy(PROVIDER_PRESETS[preset_id])
    pairs = preset.pop("models")
    preset.pop("description")
    preset.pop("docs_url")
    preset.update(id=source_id, api_key_encrypted=None, custom_headers="{}", proxy=None, is_active=1)
    caps = model_capabilities(preset["interface_type"], pairs[0][1] if pairs else "")
    models = [
        {
            "id": f"{source_id}_model_{index}",
            "source_id": source_id,
            "display_name": label,
            "model_id": model_id,
            "default_size": caps["sizes"][0],
            "default_quality": caps["qualities"][0],
            "default_n": 1,
            "sort_order": index,
            "is_active": 1,
            "reference_image_enabled": caps["reference"],
        }
        for index, (label, model_id) in enumerate(pairs)
    ]
    return preset, models


def model_capabilities(interface_type: str, model_id: str = "") -> dict:
    caps = {
        "sizes": ["1024x1024", "1536x1024", "1024x1536"],
        "qualities": ["auto", "low", "medium", "high"],
        "reference": True,
        "negative": False,
        "seed": False,
        "size_label": "尺寸",
        "quality_label": "质量",
        "format": True,
        "counts": [1, 2, 4, 8],
        "custom_size": True,
    }
    if model_id.startswith("gpt-image-2.5"):
        caps["qualities"] += ["xhigh", "max"]
    if interface_type == "gemini":
        caps.update(
            sizes=ASPECT_RATIOS,
            qualities=["1K", "2K", "4K"],
            size_label="画幅",
            quality_label="分辨率",
            format=False,
            counts=[1],
            custom_size=False,
        )
    elif interface_type == "bfl":
        caps.update(qualities=["auto"], seed=True, format=False, reference=False, counts=[1])
    elif interface_type == "minimax":
        caps.update(
            sizes=ASPECT_RATIOS, qualities=["auto"], seed=True, size_label="画幅", format=False, custom_size=False
        )
    elif interface_type == "custom" or not model_id.startswith("gpt-image-"):
        caps.update(
            qualities=["auto", "standard", "hd", "low", "medium", "high"],
            negative=True,
            seed=True,
            reference=False,
            format=False,
        )
    return caps


def adapter_id(interface_type: str) -> str:
    return {"openai_images": "openai", "custom": "custom"}.get(interface_type, interface_type)
