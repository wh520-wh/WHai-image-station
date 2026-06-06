from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PromptTemplate:
    id: int = 0
    name: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    platform_id: Optional[str] = None
    params: dict = field(default_factory=dict)
    category: str = ""
    tags: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "platform_id": self.platform_id,
            "params": self.params,
            "category": self.category,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PromptTemplate":
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            prompt=data.get("prompt", ""),
            negative_prompt=data.get("negative_prompt", ""),
            platform_id=data.get("platform_id"),
            params=data.get("params", {}),
            category=data.get("category", ""),
            tags=data.get("tags", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
        )