from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class HistoryRecord:
    id: int = 0
    task_id: str = ""
    platform_id: str = ""
    source_id: str = ""
    model_config_id: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    params: dict = field(default_factory=dict)
    image_path: str = ""
    thumbnail_path: str = ""
    seed: str = ""
    status: str = ""
    error: str | None = None
    request_url: str = ""
    request_payload: dict = field(default_factory=dict)
    response_summary: str = ""
    diagnostic: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "platform_id": self.platform_id,
            "source_id": self.source_id,
            "model_config_id": self.model_config_id,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "params": self.params,
            "image_path": self.image_path,
            "thumbnail_path": self.thumbnail_path,
            "seed": self.seed,
            "status": self.status,
            "error": self.error,
            "request_url": self.request_url,
            "request_payload": self.request_payload,
            "response_summary": self.response_summary,
            "diagnostic": self.diagnostic,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryRecord":
        return cls(
            id=data.get("id", 0),
            task_id=data.get("task_id", ""),
            platform_id=data.get("platform_id", ""),
            source_id=data.get("source_id", ""),
            model_config_id=data.get("model_config_id", ""),
            prompt=data.get("prompt", ""),
            negative_prompt=data.get("negative_prompt", ""),
            params=data.get("params", {}),
            image_path=data.get("image_path", ""),
            thumbnail_path=data.get("thumbnail_path", ""),
            seed=data.get("seed", ""),
            status=data.get("status", ""),
            error=data.get("error"),
            request_url=data.get("request_url", ""),
            request_payload=data.get("request_payload", {}),
            response_summary=data.get("response_summary", ""),
            diagnostic=data.get("diagnostic", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )
