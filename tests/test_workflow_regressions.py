import asyncio
from datetime import datetime

import pytest

from src.managers.queue_manager import QueueManager
from src.models.task import GenerationTask
from src.widgets.generation_panel import GenerationPanel
from src.widgets.history_panel import HistoryPanel
from src.widgets.settings_dialog import SettingsDialog


@pytest.mark.asyncio
async def test_waiting_tasks_remain_visible_and_cancellable_while_worker_is_busy():
    manager = QueueManager()
    manager.max_concurrent = 1
    manager._running = True
    release = asyncio.Event()

    async def process(task):
        task.status = "GENERATING"
        await release.wait()
        task.status = "COMPLETED"

    manager._process_task = process
    tasks = [GenerationTask(prompt=str(i)) for i in range(5)]
    for task in tasks:
        manager.add_task(task)
    worker = asyncio.create_task(manager._async_thread_main())
    try:
        await asyncio.sleep(0.05)
        assert manager.get_queue_info()["waiting"] == 4
        assert len(manager.get_task_snapshots(20)) == 5
        assert manager.cancel_task(str(tasks[-1].id))
        assert tasks[-1].status == "CANCELLED"
    finally:
        manager._running = False
        release.set()
        await worker


def test_queue_card_updates_after_task_status_changes(qapp):
    manager = QueueManager()
    panel = GenerationPanel(manager)
    task = GenerationTask(prompt="test")
    manager.add_task(task)
    panel.refresh_queue()
    task.status = "COMPLETED"
    panel.refresh_queue()
    assert panel.queue_container.itemAt(0).widget().task["status"] == "COMPLETED"


def test_same_source_refresh_preserves_user_parameters(qapp):
    panel = GenerationPanel(QueueManager())
    sources = [{"id": "source", "name": "Test", "interface_type": "openai_images"}]
    models = {"source": [{"id": "model", "model_id": "gpt-image-1", "default_quality": "auto"}]}
    panel.set_sources(sources, models)
    panel.size_combo.setEditText("1536x1024")
    panel.quality_combo.setEditText("high")
    panel.set_sources(sources, models)
    assert panel.size_combo.currentText() == "1536x1024"
    assert panel.quality_combo.currentText() == "high"


def test_history_accepts_database_iso_dates(qapp):
    panel = HistoryPanel(None)
    assert panel._record_date({"created_at": "2026-10-12T09:00:00"}) == datetime(2026, 10, 12, 9)


def test_data_management_creates_real_initialized_managers(qapp):
    dialog = SettingsDialog(None)
    manager = dialog._get_migration_manager()
    assert manager.history_manager._db is None
    assert manager.prompt_manager._db is None


@pytest.mark.asyncio
async def test_template_preserves_source_and_model_binding(temp_db_path):
    from src.config.database import Database

    db = Database(temp_db_path)
    await db.connect()
    try:
        await db.save_prompt_template(
            {
                "name": "Test",
                "prompt": "test",
                "source_id": "source",
                "model_config_id": "model",
            }
        )
        saved = (await db.get_prompt_templates())[0]
        assert saved["source_id"] == "source"
        assert saved["model_config_id"] == "model"
    finally:
        await db.close()
