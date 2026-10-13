"""Local image files shared by generation, saved references, backups and tools."""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
import threading
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from PIL import Image, ImageOps

from src.config import constants
from src.config.utils import get_thumbnail_path

EXTENSIONS = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}
MAX_BYTES = 50 * 1024 * 1024
MAX_PIXELS = 40_000_000
_reference_publish_lock = threading.Lock()


class ImageInfo(TypedDict):
    path: str
    name: str
    width: int
    height: int
    format: str
    bytes: int
    sizeText: str
    hasAlpha: bool


class ImageEditInfo(ImageInfo):
    operation: str
    savedPercent: float


def reference_dir() -> Path:
    return Path(constants.GENERATIONS_DIR).parent / "references"


def _check_image(image):
    if image.format not in EXTENSIONS:
        raise ValueError("请选择 PNG、JPEG 或 WebP 图片。")
    if image.width * image.height > MAX_PIXELS:
        raise ValueError("图片超过 4000 万像素，请先缩小后再处理。")
    if getattr(image, "is_animated", False):
        raise ValueError("暂不支持动画图片，请选择静态图片。")


def _has_alpha(image):
    return "A" in image.getbands() or "transparency" in image.info


def _describe_image(source: Path, image, image_format: str, size: int) -> ImageInfo:
    width, height = image.size
    if image.getexif().get(274) in (5, 6, 7, 8):
        width, height = height, width
    return {
        "path": str(source.resolve()), "name": source.name,
        "width": width, "height": height, "format": image_format, "bytes": size,
        "sizeText": f"{size / 1024**2:.2f} MB" if size >= 1024**2 else f"{size / 1024:.1f} KB",
        "hasAlpha": _has_alpha(image),
    }


def inspect_image(path: str) -> ImageInfo:
    source = Path(path)
    if not source.is_file():
        raise ValueError("图片文件不存在，请重新选择。")
    size = source.stat().st_size
    if size > MAX_BYTES:
        raise ValueError("图片不能超过 50 MB。")
    with Image.open(source) as image:
        _check_image(image)
        image.verify()
    with Image.open(source) as image:
        return _describe_image(source, image, str(image.format), size)


def _image_format(data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise ValueError("参考图不能超过 50 MB。")
    with Image.open(io.BytesIO(data)) as image:
        _check_image(image)
        image_format = str(image.format)
        image.verify()
    return image_format


def read_image_data(path: str) -> tuple[bytes, str]:
    source = Path(path)
    if not source.is_file():
        raise ValueError("图片文件不存在，请重新选择。")
    with source.open("rb") as stream:
        if os.fstat(stream.fileno()).st_size > MAX_BYTES:
            raise ValueError("图片不能超过 50 MB。")
        data = stream.read(MAX_BYTES + 1)
    return data, _image_format(data)


def _store_reference(data: bytes, image_format: str) -> tuple[str, bool]:
    suffix = EXTENSIONS[image_format]
    folder = reference_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (hashlib.sha256(data).hexdigest() + suffix)
    if target.is_file():
        return str(target), False
    handle, staging = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        # Recheck publication under the lock so only one concurrent writer owns rollback.
        with _reference_publish_lock:
            if target.is_file():
                return str(target), False
            os.replace(staging, target)
    finally:
        Path(staging).unlink(missing_ok=True)
    return str(target), True


def store_reference(data: bytes) -> tuple[str, bool]:
    return _store_reference(data, _image_format(data))


def retain_reference(path: str) -> str:
    data, image_format = read_image_data(path)
    return _store_reference(data, image_format)[0]


def _flatten_to_rgb(image):
    if image.mode == "RGB":
        return image
    rgba = image.convert("RGBA")
    flattened = Image.new("RGB", rgba.size, "white")
    flattened.paste(rgba, mask=rgba.getchannel("A"))
    return flattened


def _write_thumbnail(image, path: str):
    thumb_path = get_thumbnail_path(path)
    Path(thumb_path).parent.mkdir(parents=True, exist_ok=True)
    ratio = min(1, 320 / max(image.size))
    if ratio < 1:
        image = image.resize(
            (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
            Image.Resampling.LANCZOS,
            reducing_gap=2.0,
        )
    _flatten_to_rgb(image).save(thumb_path, "JPEG", quality=85, optimize=True)


def create_thumbnail(path: str):
    thumb_path = get_thumbnail_path(path)
    if not thumb_path:
        return
    with Image.open(path) as original:
        image = ImageOps.exif_transpose(original)
        _write_thumbnail(image, path)


def process_image(path: str, operation: str, output_format: str, edge: int, quality: int) -> ImageEditInfo:
    if operation not in {"convert", "resize", "compress"}:
        raise ValueError("请选择图片处理工具。")
    fmt = output_format.upper()
    if fmt == "JPG":
        fmt = "JPEG"
    if fmt not in EXTENSIONS:
        raise ValueError("输出格式必须为 PNG、JPEG 或 WebP。")
    if not 1 <= quality <= 100:
        raise ValueError("品质需要在 1–100 之间。")
    if operation == "resize" and not 64 <= edge <= 8192:
        raise ValueError("最长边需要在 64–8192 像素之间。")
    data, _ = read_image_data(path)
    folder = Path(constants.GENERATIONS_DIR).parent / "edits"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (uuid4().hex + EXTENSIONS[fmt])
    handle, staging = tempfile.mkstemp(dir=folder, suffix=".tmp")
    os.close(handle)
    try:
        with Image.open(io.BytesIO(data)) as original:
            image = ImageOps.exif_transpose(original)
            if operation == "resize":
                image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
            if fmt == "JPEG":
                image = _flatten_to_rgb(image)
            elif image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if _has_alpha(image) else "RGB")
            options: dict = {"optimize": True} if fmt == "PNG" else {"quality": quality}
            if fmt == "PNG":
                options["compress_level"] = 9 if operation == "compress" else 6
            if fmt == "JPEG":
                options["optimize"] = True
            if fmt == "WEBP":
                options["method"] = 6 if operation == "compress" else 4
            if original.info.get("icc_profile") and original.mode in {"RGB", "RGBA", "P"}:
                options["icc_profile"] = original.info["icc_profile"]
            image.save(staging, fmt, **options)
            os.replace(staging, target)
            _write_thumbnail(image, str(target))
            size = target.stat().st_size
            result = _describe_image(target, image, fmt, size)
        return {
            **result,
            "operation": operation,
            "savedPercent": round((1 - result["bytes"] / max(1, len(data))) * 100, 1),
        }
    except BaseException:
        target.unlink(missing_ok=True)
        Path(get_thumbnail_path(str(target))).unlink(missing_ok=True)
        raise
    finally:
        Path(staging).unlink(missing_ok=True)
