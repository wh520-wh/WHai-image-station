from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from src.config import constants, database
from src.config.utils import get_thumbnail_path

if TYPE_CHECKING:
    from src.managers.image_assets import ImageInfo

LOCAL_EDIT_PLATFORM = "local_image"
LOCAL_EDIT_LABELS = {"convert": "格式转换", "resize": "尺寸调整", "compress": "图片压缩"}


class HistoryManager:
    _instance: HistoryManager | None = None

    def __init__(self, db: database.Database | None = None):
        self._db = db

    @classmethod
    def get_instance(cls) -> HistoryManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self, db: database.Database):
        self._db = db

    async def get_history(self, limit: int = 100, offset: int = 0) -> list[dict]:
        if not self._db:
            return []
        return await self._db.get_generation_history(limit, offset)

    async def get_record(self, task_id: str) -> dict | None:
        if not self._db:
            return None
        return await self._db.get_history_by_task_id(task_id)

    async def save_record(self, record: dict):
        if self._db:
            await self._db.save_generation_history(record)

    @staticmethod
    def is_local_edit(record: dict) -> bool:
        return record.get("platform_id") in {LOCAL_EDIT_PLATFORM, "本地图片工具"}

    async def save_local_edit(self, source: ImageInfo, result: ImageInfo, options: dict):
        if not self._db:
            raise RuntimeError("作品库尚未初始化。")
        now = datetime.now().isoformat()
        await self.save_record(
            {
                "task_id": uuid4().hex,
                "platform_id": LOCAL_EDIT_PLATFORM,
                "prompt": LOCAL_EDIT_LABELS[options["operation"]] + " · " + source["name"],
                "params": dict(options),
                "image_path": result["path"],
                "thumbnail_path": get_thumbnail_path(result["path"]),
                "result_paths_json": [result["path"]],
                "status": "COMPLETED", "created_at": now, "completed_at": now,
                "category": "本地处理",
            }
        )

    async def update_status(self, task_id: str, status: str, **kwargs):
        if self._db:
            await self._db.update_history_status(task_id, status, **kwargs)

    def get_default_save_path(self) -> str:
        os.makedirs(constants.GENERATIONS_DIR, exist_ok=True)
        return constants.GENERATIONS_DIR

    async def delete_record(self, task_id: str):
        """删除历史记录和对应的图片文件。文件删除失败不影响数据库记录清理。"""
        if not self._db:
            return
        record = await self.get_record(task_id)
        if record:
            paths = set(record.get("result_paths") or [])
            if record.get("image_path"):
                paths.add(record["image_path"])
            if record.get("thumbnail_path"):
                paths.add(record["thumbnail_path"])
            paths.update(
                get_thumbnail_path(path) for path in list(paths) if path and path != record.get("thumbnail_path")
            )
            for path in paths:
                if path and os.path.exists(path) and not os.path.isdir(path):
                    try:
                        os.remove(path)
                    except (PermissionError, OSError) as e:
                        print(f"[history_manager] Failed to remove {path}: {e}")
            await self._db.delete_generation_history(task_id)
