from __future__ import annotations
import os, zipfile, json
from typing import Awaitable, Callable
from src.models.batch_result import BatchResult


class BatchOpsManager:
    def __init__(self, history_manager, db, generations_dir: str):
        self.history_manager = history_manager
        self.db = db
        self.generations_dir = generations_dir

    async def _batch_execute(
        self,
        record_ids: list[str],
        operation: Callable[[str], Awaitable[None]],
        error_prefix: str,
    ) -> BatchResult:
        success_count = 0
        failed_count = 0
        errors: list[str] = []
        for record_id in record_ids:
            try:
                await operation(record_id)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"{error_prefix} {record_id}: {str(e)}")
        return BatchResult(success_count, failed_count, errors)

    async def delete_records(self, record_ids: list[str]) -> BatchResult:
        async def op(rid: str) -> None:
            await self.history_manager.delete_record(rid)
        return await self._batch_execute(record_ids, op, "Failed to delete")

    async def move_records(self, record_ids: list[str], category: str) -> BatchResult:
        async def op(rid: str) -> None:
            await self.db.update_history_category(rid, category)
        return await self._batch_execute(record_ids, op, "Failed to move")

    async def add_tags(self, record_ids: list[str], tags: list[str]) -> BatchResult:
        async def op(rid: str) -> None:
            await self.db.update_history_tags(rid, tags)
        return await self._batch_execute(record_ids, op, "Failed to add tags to")

    async def export_records(self, record_ids: list[str], output_path: str) -> str:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            manifest = {"items": []}
            for record_id in record_ids:
                record = await self.history_manager.get_record(record_id)
                if not record:
                    continue
                image_path = record.get("image_path")
                if image_path and os.path.exists(image_path):
                    fname = f"images/{os.path.basename(image_path)}"
                    zf.write(image_path, fname)
                manifest["items"].append({
                    "task_id": record.get("task_id"),
                    "prompt": record.get("prompt"),
                    "platform": record.get("platform_id"),
                    "model": record.get("model_config_id"),
                    "created_at": record.get("created_at"),
                    "image_file": f"images/{os.path.basename(image_path)}" if image_path else None,
                })
            manifest["total_items"] = len(manifest["items"])
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        return output_path
