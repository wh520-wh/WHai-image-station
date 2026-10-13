from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

# NOTE: task.params['_diagnostic'] holds a Diagnostic object (src.adapters.errors.Diagnostic)
# in live tasks, or a dict in legacy history records. Adapters and QueueManager populate it.


@dataclass
class GenerationTask:
    id: UUID = field(default_factory=uuid4)
    platform_id: str = ""
    source_id: str = ""
    model_config_id: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    params: "dict[str, Any]" = field(default_factory=dict)
    reference_image_path: str | None = None
    status: str = "WAITING"
    result_paths: list = field(default_factory=list)
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": str(self.id),
            "platform_id": self.platform_id,
            "source_id": self.source_id,
            "model_config_id": self.model_config_id,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "params": self.params,
            "reference_image_path": self.reference_image_path,
            "status": self.status,
            "result_paths": self.result_paths,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GenerationTask":
        return cls(
            id=UUID(data["id"]) if isinstance(data["id"], str) else data["id"],
            platform_id=data.get("platform_id", ""),
            source_id=data.get("source_id", ""),
            model_config_id=data.get("model_config_id", ""),
            prompt=data.get("prompt", ""),
            negative_prompt=data.get("negative_prompt", ""),
            params=data.get("params", {}),
            reference_image_path=data.get("reference_image_path"),
            status=data.get("status", "WAITING"),
            result_paths=data.get("result_paths", []),
            error=data.get("error"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )
