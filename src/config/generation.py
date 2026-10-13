"""Shared generation options for interactive drafts and saved workflows."""

from pathlib import Path

from src.config.providers import model_capabilities


def _integer(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{label}请填写整数。")
    try:
        result = int(value)
    except (ValueError, OverflowError) as error:
        raise ValueError(f"{label}请填写整数。") from error
    if isinstance(value, float) and value != result:
        raise ValueError(f"{label}请填写整数。")
    return result


def generation_options(interface_type: str, model_id: str, draft: dict) -> dict:
    """Validate supported options without imposing unknown relay/provider limits."""
    caps = model_capabilities(interface_type, model_id)
    size = str(draft.get("size") or caps["sizes"][0]).strip().replace("×", "x").lower()
    if caps["custom_size"]:
        dimensions = size.split("x")
        if len(dimensions) != 2 or not all(
            value.isascii() and value.isdigit() and int(value) > 0 for value in dimensions
        ):
            raise ValueError("尺寸请填写正整数宽高，例如 1280x768。")
    elif size not in caps["sizes"]:
        raise ValueError("当前模型不支持这个画幅，请选择可用的画幅。")
    if interface_type == "bfl" and any(int(value) % 16 or not 256 <= int(value) <= 2048 for value in size.split("x")):
        raise ValueError("FLUX 尺寸须为 16 的倍数，宽高需在 256–2048 之间。")
    if interface_type == "minimax" and len(str(draft.get("prompt") or "")) > 1500:
        raise ValueError("MiniMax 提示词不能超过 1500 字符。")

    quality = str(draft.get("quality") or caps["qualities"][0]).strip()
    compatible = interface_type == "custom" or (
        interface_type == "openai_images" and not model_id.startswith("gpt-image-")
    )
    if not quality or (not compatible and quality not in caps["qualities"]):
        raise ValueError("当前模型不支持这个质量或分辨率，请选择可用选项。")

    count = _integer(draft.get("n", 1), "数量")
    if count < 1:
        raise ValueError("数量请填写正整数。")
    if len(caps["counts"]) == 1 and count != caps["counts"][0]:
        raise ValueError("当前模型每次只能生成一张图片。")
    params = {"size": size, "quality": quality, "n": count}
    seed = draft.get("seed")
    if caps["seed"] and seed is not None and str(seed).strip():
        params["seed"] = _integer(seed, "种子")
    if caps["format"]:
        output_format = str(draft.get("output_format") or "png").strip().lower()
        if output_format not in {"png", "jpeg", "webp"}:
            raise ValueError("图片格式请选择 PNG、JPEG 或 WebP。")
        params["output_format"] = output_format
        if draft.get("transparent"):
            if output_format == "jpeg":
                raise ValueError("透明背景请选择 PNG 或 WebP。")
            params["background"] = "transparent"

    reference = str(draft.get("reference") or "").strip() if caps["reference"] else ""
    if reference and not Path(reference).is_file():
        raise ValueError("参考图文件不存在，请重新选择。")
    return {
        "params": params,
        "negative_prompt": str(draft.get("negative_prompt") or "") if caps["negative"] else "",
        "reference_image_path": reference or None,
    }
