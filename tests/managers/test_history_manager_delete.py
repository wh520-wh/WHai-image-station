import os
import pytest
from src.managers.history_manager import HistoryManager


class FakeDb:
    def __init__(self, history):
        self._history = history
        self.deleted = []
    async def get_generation_history(self, limit=100, offset=0):
        return self._history
    async def get_history_by_task_id(self, task_id):
        for r in self._history:
            if r["task_id"] == task_id:
                return r
        return None
    async def delete_generation_history(self, task_id):
        self.deleted.append(task_id)
        self._history = [r for r in self._history if r["task_id"] != task_id]


@pytest.mark.asyncio
async def test_delete_record_handles_permission_error(tmp_path):
    record = {
        "task_id": "t1",
        "image_path": str(tmp_path / "image.png"),
        "thumbnail_path": str(tmp_path / "thumb.jpg"),
        "result_paths": [str(tmp_path / "image.png")],
    }
    (tmp_path / "image.png").write_bytes(b"x")
    (tmp_path / "thumb.jpg").write_bytes(b"y")
    db = FakeDb([record])
    mgr = HistoryManager()
    await mgr.initialize(db)
    # 把 thumbnail_path 改成目录，模拟删除失败
    record["thumbnail_path"] = str(tmp_path)
    await mgr.delete_record("t1")  # 不应抛异常
    assert db.deleted == ["t1"]  # DB 记录仍然被删除


@pytest.mark.asyncio
async def test_delete_record_missing_file_does_not_raise(tmp_path):
    record = {
        "task_id": "t2",
        "image_path": str(tmp_path / "nonexistent.png"),
        "thumbnail_path": None,
        "result_paths": [],
    }
    db = FakeDb([record])
    mgr = HistoryManager()
    await mgr.initialize(db)
    await mgr.delete_record("t2")  # 不应抛异常
    assert db.deleted == ["t2"]
