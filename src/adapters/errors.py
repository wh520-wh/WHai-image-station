from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = ["Category", "Field", "Diagnostic", "AdapterError"]


class Category(str, Enum):
    AUTH = "auth"
    RATE_LIMIT = "rate"
    NETWORK = "network"
    SERVER = "server"
    BAD_REQUEST = "bad_req"
    CONTENT = "content"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Field:
    name: str
    value: str
    issue: str
    redact: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": "***" if self.redact else self.value,
            "issue": self.issue,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "Field":
        if not isinstance(d, dict):
            return cls(name="(unknown)", value="(empty)", issue=str(d)[:200])
        return cls(
            name=str(d.get("name", "(unnamed)")),
            value=str(d.get("value", "")),
            issue=str(d.get("issue", "")),
            redact=bool(d.get("redact", False)),
        )


@dataclass(frozen=True)
class Diagnostic:
    category: Category
    fields: tuple[Field, ...] = ()
    hint: str | None = None
    original: str = ""
    platform: str = ""
    source_id: str = ""

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "fields": [f.to_dict() for f in self.fields],
            "hint": self.hint,
            "original": self.original,
            "platform": self.platform,
            "source_id": self.source_id,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "Diagnostic":
        if not isinstance(d, dict):
            # Non-dict path: unknown shape → aggressive cap.
            return cls(
                category=Category.UNKNOWN,
                original=str(d)[:2000] if d is not None else "",
            )
        try:
            category = Category(d["category"]) if "category" in d else Category.UNKNOWN
        except (ValueError, TypeError):
            category = Category.UNKNOWN
        raw_fields = d.get("fields") or []
        fields: list[Field] = []
        if isinstance(raw_fields, list):
            for item in raw_fields:
                if isinstance(item, Field):
                    fields.append(item)
                elif isinstance(item, dict):
                    fields.append(Field.from_dict(item))
        legacy_message = d.get("message") or d.get("error")
        original = d.get("original") or (str(legacy_message) if legacy_message else "")
        hint_value = d.get("hint")
        hint = str(hint_value) if hint_value is not None else None
        return cls(
            category=category,
            fields=tuple(fields),
            hint=hint,
            original=str(original)[:8000],
            platform=str(d.get("platform", "")),
            source_id=str(d.get("source_id", "")),
        )


class AdapterError(Exception):
    def __init__(self, message: str, diagnostic: Diagnostic):
        super().__init__(message)
        self.diagnostic = diagnostic

    def __str__(self) -> str:
        return f"[{self.diagnostic.category.value}] {self.diagnostic.original or super().__str__()}"
