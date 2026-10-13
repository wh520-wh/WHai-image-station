"""Shared utility functions used across config, managers, and widgets."""

from __future__ import annotations

import json
import os
from typing import Any

from src.config import constants


def parse_headers(raw_headers: Any) -> dict[str, str]:
    """Parse headers from dict, JSON string, or None into a plain str→str dict.

    Returns empty dict for any invalid input (None, empty, non-JSON, non-dict JSON).
    """
    if not raw_headers:
        return {}
    if isinstance(raw_headers, dict):
        return {str(key): str(value) for key, value in raw_headers.items()}
    try:
        parsed = json.loads(raw_headers)
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}


def safe_int(value: Any, default: int = 0) -> int:
    """Convert value to int, returning default on any conversion failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_thumbnail_path(image_path: str) -> str:
    """Return the expected thumbnail path for a given image path.

    Returns empty string if image_path is empty.
    """
    if not image_path:
        return ""
    name = os.path.basename(image_path)
    thumb_name = f"thumb_{os.path.splitext(name)[0]}.jpg"
    return os.path.join(constants.THUMBNAILS_DIR, thumb_name)
