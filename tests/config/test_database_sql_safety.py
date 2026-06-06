import pytest
from src.config.database import Database, ALLOWED_UPDATE_COLUMNS


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
async def test_update_history_status_rejects_sql_injection_key(db):
    """A SQL-injection-shaped key must be rejected by the whitelist guard."""
    injection_key = "status; DROP TABLE generation_history; --"
    assert injection_key not in ALLOWED_UPDATE_COLUMNS
    with pytest.raises(ValueError, match="Disallowed column"):
        await db.update_history_status(
            "task_1", "FAILED", **{injection_key: "pwned"}
        )


@pytest.mark.asyncio
async def test_update_history_status_does_not_drop_table(db):
    """Pin the table-exists invariant: even if the guard were ever bypassed,
    parameterization (or in a future regression, f-string interpolation) must
    not drop the table. This catches a regression immediately."""
    await db.save_generation_history({
        "task_id": "task_1",
        "prompt": "test",
        "status": "WAITING",
    })
    with pytest.raises(ValueError):
        await db.update_history_status(
            "task_1",
            "FAILED",
            **{"status; DROP TABLE generation_history; --": "x"},
        )
    cursor = await db._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='generation_history'"
    )
    row = await cursor.fetchone()
    assert row is not None, "generation_history table was dropped by injection attempt"
    record = await db.get_history_by_task_id("task_1")
    assert record is not None


# Columns whose values are JSON-decoded by _row_to_history and therefore
# need a raw-DB round-trip instead of the parsed record dict.
_JSON_COLUMNS = {"diagnostic", "result_paths_json"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "column,value",
    [
        ("status", "FAILED"),
        ("error", "boom"),
        ("image_path", "/tmp/a.png"),
        ("thumbnail_path", "/tmp/a_thumb.png"),
        ("completed_at", "2026-06-06T00:00:00"),
        ("result_paths_json", '["/tmp/a.png"]'),
        ("diagnostic", '{"ok": true}'),
        ("response_summary", "ok"),
    ],
)
async def test_update_history_status_accepts_known_columns(db, column, value):
    assert column in ALLOWED_UPDATE_COLUMNS, (
        f"parametrize column {column!r} must be a whitelisted column"
    )
    await db.save_generation_history({
        "task_id": "task_1",
        "prompt": "test",
        "status": "WAITING",
    })

    if column == "status":
        # `status` is the positional arg. Passing it again as a kwarg collides
        # with Python's argument binding, which is itself a guard against the
        # `SET status = ?, status = ?, ...` footgun in the generated SQL.
        with pytest.raises(TypeError):
            await db.update_history_status("task_1", value, **{column: value})
        return

    await db.update_history_status("task_1", "FAILED", **{column: value})

    if column in _JSON_COLUMNS:
        # Compare the raw stored value, not the JSON-decoded record dict.
        cursor = await db._conn.execute(
            f"SELECT {column} FROM generation_history WHERE task_id = ?",
            ("task_1",),
        )
        row = await cursor.fetchone()
        assert row[0] == value
    else:
        record = await db.get_history_by_task_id("task_1")
        assert record["status"] == "FAILED"
        assert record[column] == value
