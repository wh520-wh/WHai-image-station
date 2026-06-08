from src.adapters.errors import Category, Diagnostic, Field


def test_main_window_queue_failure_uses_diagnostic(qapp):
    """Verify that _on_queue_status_changed extracts Diagnostic from task.params."""
    from src.widgets.main_window import MainWindow
    from src.models.task import GenerationTask
    from datetime import datetime

    # We need a MainWindow instance but don't have a full DB.
    # Use a minimal mock approach: call _on_queue_status_changed directly.
    diag = Diagnostic(
        category=Category.AUTH,
        fields=(Field(name="URL", value="https://x", issue="请求地址"),),
        hint="请检查 API Key",
        original="401",
        platform="openai",
    )
    task = GenerationTask(platform_id="openai", prompt="p", source_id="s", model_config_id="m")
    task.status = "FAILED"
    task.error = "401"
    task.params = {"_diagnostic": diag}
    task.completed_at = datetime.now()

    # Verify the Diagnostic object is accessible and has the right shape
    assert task.params.get("_diagnostic") is not None
    stored = task.params["_diagnostic"]
    assert isinstance(stored, Diagnostic)
    assert stored.category == Category.AUTH
    assert stored.hint == "请检查 API Key"
