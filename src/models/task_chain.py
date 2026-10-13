from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChainTask:
    task_id: str
    chain_order: int
    source_id: str = ""
    model_config_id: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    params: dict = field(default_factory=dict)
    status: str = "pending"  # pending, generating, completed, failed, skipped
    trigger_on: str = "success"  # success, failure, any
    reference_image_path: str | None = None


@dataclass
class TaskChain:
    id: str = ""
    name: str = ""
    tasks: list[ChainTask] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "idle"  # idle, running, paused, completed, failed
    failure_mode: str = "stop"  # stop, skip

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "chain_order": t.chain_order,
                    "source_id": t.source_id,
                    "model_config_id": t.model_config_id,
                    "prompt": t.prompt,
                    "negative_prompt": t.negative_prompt,
                    "params": t.params,
                    "status": t.status,
                    "trigger_on": t.trigger_on,
                    "reference_image_path": t.reference_image_path,
                }
                for t in self.tasks
            ],
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "failure_mode": self.failure_mode,
        }

    @property
    def completed_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == "completed")

    @property
    def total_count(self) -> int:
        return len(self.tasks)

    def get_status_text(self) -> str:
        if self.status == "idle":
            return f"空闲 ({self.completed_count}/{self.total_count})"
        elif self.status == "running":
            return f"运行中 ({self.completed_count}/{self.total_count})"
        return f"{self.status}"
