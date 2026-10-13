from pathlib import Path

import pytest
from PIL import Image

from src.config import constants
from src.managers import image_assets


@pytest.fixture
def local_images(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "GENERATIONS_DIR", str(tmp_path / "images"))
    monkeypatch.setattr(constants, "THUMBNAILS_DIR", str(tmp_path / "thumbs"))
    return tmp_path


def test_retained_reference_survives_original_deletion_and_deduplicates(local_images):
    original = local_images / "source.png"
    Image.new("RGBA", (32, 24), (10, 90, 45, 100)).save(original)
    pixels = original.read_bytes()
    retained = image_assets.retain_reference(str(original))
    assert retained == image_assets.retain_reference(str(original))
    original.unlink()
    assert Path(retained).read_bytes() == pixels
    assert len(list(image_assets.reference_dir().iterdir())) == 1


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WebP"])
def test_convert_keeps_original_and_handles_transparency(local_images, fmt):
    original = local_images / "alpha.png"
    Image.new("RGBA", (32, 24), (30, 100, 50, 0)).save(original)
    before = original.read_bytes()
    result = image_assets.process_image(str(original), "convert", fmt, 1024, 90)
    assert original.read_bytes() == before
    with Image.open(result["path"]) as image:
        assert image.size == (32, 24)
        assert image.format == fmt.upper()
        if fmt == "JPEG":
            assert min(image.getpixel((0, 0))) >= 250
        else:
            assert image.getpixel((0, 0))[3] == 0
    assert Path(image_assets.get_thumbnail_path(result["path"])).exists()


def test_resize_applies_exif_orientation_and_keeps_aspect(local_images):
    original = local_images / "rotated.jpg"
    image = Image.new("RGB", (256, 128), "green")
    exif = image.getexif()
    exif[274] = 6
    image.save(original, exif=exif)
    info = image_assets.inspect_image(str(original))
    assert (info["width"], info["height"]) == (128, 256)
    result = image_assets.process_image(str(original), "resize", "PNG", 64, 90)
    assert (result["width"], result["height"]) == (32, 64)
    with Image.open(result["path"]) as resized:
        assert resized.getexif().get(274, 1) == 1


def test_resize_does_not_enlarge_small_images(local_images):
    original = local_images / "small.png"
    Image.new("RGB", (32, 24), "green").save(original)
    result = image_assets.process_image(str(original), "resize", "WebP", 1024, 80)
    assert (result["width"], result["height"]) == (32, 24)


def test_failed_processing_leaves_no_partial_output(local_images, monkeypatch):
    original = local_images / "source.png"
    Image.new("RGB", (32, 24), "green").save(original)
    before = original.read_bytes()

    def fail_save(*args, **kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr(Image.Image, "save", fail_save)
    with pytest.raises(OSError, match="disk unavailable"):
        image_assets.process_image(str(original), "compress", "JPEG", 1024, 80)
    assert original.read_bytes() == before
    assert not list((local_images / "edits").iterdir())


@pytest.mark.parametrize("operation,fmt,edge,quality", [("resize", "PNG", 0, 80), ("convert", "TIFF", 1024, 80), ("compress", "WebP", 1024, 0)])
def test_invalid_tool_settings_do_not_create_output(local_images, operation, fmt, edge, quality):
    original = local_images / "source.png"
    Image.new("RGB", (32, 24), "green").save(original)
    with pytest.raises(ValueError):
        image_assets.process_image(str(original), operation, fmt, edge, quality)
    assert not (local_images / "edits").exists()


def test_grayscale_alpha_is_preserved_when_converting(local_images):
    original = local_images / "grayscale-alpha.png"
    Image.new("LA", (32, 24), (120, 50)).save(original)
    result = image_assets.process_image(str(original), "convert", "PNG", 1024, 85)
    with Image.open(result["path"]) as converted:
        assert converted.mode == "RGBA"
        assert converted.getpixel((0, 0)) == (120, 120, 120, 50)


def test_concurrent_reference_storage_has_one_rollback_owner(local_images, monkeypatch):
    import io
    import threading
    from concurrent.futures import ThreadPoolExecutor

    image = io.BytesIO()
    Image.new("RGB", (32, 24), "green").save(image, "PNG")
    barrier = threading.Barrier(2)
    local = threading.local()
    original_is_file = Path.is_file

    def synchronized_check(path):
        exists = original_is_file(path)
        if path.parent == image_assets.reference_dir() and not getattr(local, "checked", False):
            local.checked = True
            barrier.wait(timeout=2)
        return exists

    monkeypatch.setattr(Path, "is_file", synchronized_check)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(image_assets.store_reference, [image.getvalue(), image.getvalue()]))
    assert results[0][0] == results[1][0]
    assert sum(created for _, created in results) == 1
    assert Path(results[0][0]).read_bytes() == image.getvalue()


def test_processed_output_is_not_reopened_for_metadata(local_images, monkeypatch):
    original = local_images / "source.png"
    Image.new("RGB", (128, 96), "green").save(original)
    opened_paths = []
    open_image = Image.open

    def tracked_open(file, *args, **kwargs):
        if isinstance(file, (str, Path)):
            opened_paths.append(Path(file))
        return open_image(file, *args, **kwargs)

    monkeypatch.setattr(Image, "open", tracked_open)
    result = image_assets.process_image(str(original), "resize", "JPEG", 64, 85)
    assert Path(result["path"]) not in opened_paths
    assert (result["width"], result["height"]) == (64, 48)
