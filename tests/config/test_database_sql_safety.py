import pytest
from src.config.database import Database


@pytest.fixture
async def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    database = Database(db_path=db_path)
    await database.connect()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_update_history_status_rejects_unknown_columns(db):
    with pytest.raises(ValueError, match="Disallowed column"):
        await db.update_history_status("task_1", "FAILED", malicious_key="value")


@pytest.mark.asyncio
async def test_update_history_status_accepts_known_columns(db):
    await db.save_generation_history({
        "task_id": "task_1",
        "prompt": "test",
        "status": "WAITING",
    })
    await db.update_history_status("task_1", "FAILED", error="boom")
    record = await db.get_history_by_task_id("task_1")
    assert record["status"] == "FAILED"
    assert record["error"] == "boom"
