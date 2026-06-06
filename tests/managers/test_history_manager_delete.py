import os
import pytest
from unittest.mock import patch
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
async def test_delete_record_skips_directory_paths(tmp_path):
    """当 thumbnail_path 指向目录时，os.path.isdir 为 True，os.remove 不会被调用，
    但 DB 记录仍应被删除。该测试验证的是 isdir 守卫，而不是异常处理路径。"""
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
    # 把 thumbnail_path 改成目录，触发 isdir 守卫短路
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


@pytest.mark.asyncio
async def test_delete_record_continues_when_os_remove_raises(tmp_path):
    """When os.remove raises PermissionError, the DB record should still be deleted."""
    record = {
        "task_id": "t3",
        "image_path": str(tmp_path / "image.png"),
        "thumbnail_path": None,
        "result_paths": [],
    }
    (tmp_path / "image.png").write_bytes(b"x")
    db = FakeDb([record])
    mgr = HistoryManager()
    await mgr.initialize(db)

    with patch("os.remove", side_effect=PermissionError("Access denied")):
        await mgr.delete_record("t3")  # 不应抛异常

    assert db.deleted == ["t3"]  # DB 记录仍被删除
