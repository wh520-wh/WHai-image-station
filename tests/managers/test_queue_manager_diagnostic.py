import asyncio
from unittest.mock import AsyncMock

from src.adapters.errors import Category, Diagnostic, Field
from src.models.task import GenerationTask
from src.managers.queue_manager import QueueManager


def _make_fake_config():
    return type("Cfg", (), {
        "api_base_url": "https://x",
        "api_key": "k",
        "auth_preset": "openai",
        "interface_type": "openai_images",
        "model_name": "dall-e-3",
        "response_format": "openai",
        "source_id": "s",
        "model_config_id": "m",
        "source_name": "n",
        "model_display_name": "d",
        "is_active": True,
    })()


def test_process_task_stores_diagnostic_object(monkeypatch):
    """_process_task stores a Diagnostic instance (not dict) in params['_diagnostic']."""
    from src.adapters import init_adapters
    init_adapters()
    qm = QueueManager()
    task = GenerationTask(
        platform_id="openai",
        prompt="x",
        params={"n": 1},
        source_id="s",
        model_config_id="m",
    )
    fake_diag = Diagnostic(
        category=Category.AUTH,
        fields=(
            Field(name="URL", value="https://api.example.com/v1/images/generations", issue="请求地址"),
            Field(name="HTTP status", value="401", issue="响应状态码"),
        ),
        original="401",
        hint="请检查 API Key",
        platform="openai",
    )
    fake_result = type("R", (), {
        "success": False,
        "error": "401",
        "image_paths": [],
        "raw_response": {"diagnostic": fake_diag},
    })()

    class _FakeAdapter:
        async def generate(self, t, c):
            return fake_result

    monkeypatch.setattr("src.managers.queue_manager.get_adapter", lambda platform_id: _FakeAdapter())

    async def fake_load(task):
        return _make_fake_config()

    async def fake_save(task):
        return None

    monkeypatch.setattr(qm, "_load_platform_config", fake_load)
    monkeypatch.setattr(qm, "_save_history", fake_save)

    asyncio.run(qm._process_task(task))
    assert task.status == "FAILED"
    stored = task.params.get("_diagnostic")
    assert isinstance(stored, Diagnostic)
    assert stored.category == Category.AUTH
    assert stored.original == "401"


def test_save_history_serializes_diagnostic_object():
    """_save_history must serialize a Diagnostic instance without raising AttributeError."""
    qm = QueueManager()
    mock_db = AsyncMock()
    qm._db = mock_db

    fake_diag = Diagnostic(
        category=Category.AUTH,
        fields=(
            Field(name="URL", value="https://api.example.com/v1/images/generations", issue="请求地址"),
            Field(name="HTTP status", value="401", issue="响应状态码"),
            Field(name="payload.prompt", value="a cat", issue="请求参数"),
        ),
        original="401 Unauthorized",
        hint="请检查 API Key",
        platform="openai",
    )
    task = GenerationTask(
        platform_id="openai",
        prompt="x",
        params={"_diagnostic": fake_diag, "n": 1},
        source_id="s",
        model_config_id="m",
    )
    task.status = "FAILED"
    task.error = "401"

    asyncio.run(qm._save_history(task))

    # Verify save_generation_history was called
    mock_db.save_generation_history.assert_awaited_once()
    call_args = mock_db.save_generation_history.call_args[0][0]

    # diagnostic column gets the to_dict() form
    assert call_args["diagnostic"]["category"] == "auth"
    assert call_args["diagnostic"]["original"] == "401 Unauthorized"

    # Legacy columns are populated from the Diagnostic fields
    assert call_args["request_url"] == "https://api.example.com/v1/images/generations"
    assert call_args["request_payload"] == {"prompt": "a cat"}
    assert "[auth]" in call_args["response_summary"]

    # _diagnostic stripped from params before DB write
    assert "_diagnostic" not in call_args["params"]


def test_save_history_handles_legacy_dict_diagnostic():
    """_save_history must handle legacy dict diagnostics without breaking."""
    qm = QueueManager()
    mock_db = AsyncMock()
    qm._db = mock_db

    legacy_diag = {
        "request_url": "https://api.example.com/v1",
        "payload": {"prompt": "test"},
        "response_summary": "error occurred",
    }
    task = GenerationTask(
        platform_id="openai",
        prompt="x",
        params={"_diagnostic": legacy_diag, "n": 1},
        source_id="s",
        model_config_id="m",
    )
    task.status = "FAILED"

    asyncio.run(qm._save_history(task))

    mock_db.save_generation_history.assert_awaited_once()
    call_args = mock_db.save_generation_history.call_args[0][0]
    assert call_args["request_url"] == "https://api.example.com/v1"
    assert call_args["request_payload"] == {"prompt": "test"}


def test_save_history_handles_no_diagnostic():
    """_save_history must handle tasks with no diagnostic at all."""
    qm = QueueManager()
    mock_db = AsyncMock()
    qm._db = mock_db

    task = GenerationTask(
        platform_id="openai",
        prompt="x",
        params={"n": 1},
        source_id="s",
        model_config_id="m",
    )
    task.status = "COMPLETED"

    asyncio.run(qm._save_history(task))

    mock_db.save_generation_history.assert_awaited_once()
    call_args = mock_db.save_generation_history.call_args[0][0]
    assert call_args["diagnostic"] == {}
    assert call_args["request_url"] is None
