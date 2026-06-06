import asyncio
import json
import os
import sys

from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv)

from src.config.database import Database
from src.managers.queue_manager import QueueManager
from src.models.task import GenerationTask
from datetime import datetime


def test_worker_db_is_separate_from_main_db(tmp_path):
    """Worker thread creates its own DB connection, separate from main thread's."""
    db_path = str(tmp_path / "data.db")

    async def scenario():
        # Main thread DB
        main_db = Database(db_path)
        await main_db.connect()

        # Init QueueManager normally
        qm = QueueManager()
        await qm.initialize(main_db)

        # Start the manager, let it run briefly
        await qm.start()

        # Give worker a moment to create its connection
        await asyncio.sleep(0.2)

        # Worker should have its own DB
        assert qm._worker_db is not None
        assert id(qm._worker_db) != id(qm._db)

        # Worker DB should use the same path as main DB
        assert qm._worker_db.db_path == db_path

        await qm.stop()
        await main_db.close()

    asyncio.run(scenario())


def test_save_history_writes_to_worker_db(tmp_path):
    """_save_history writes to the worker DB, and data is readable from main DB."""
    db_path = str(tmp_path / "data.db")

    async def scenario():
        main_db = Database(db_path)
        await main_db.connect()

        qm = QueueManager()
        await qm.initialize(main_db)

        # Manually create & connect worker DB since we're not starting the worker thread
        qm._worker_db = Database(db_path)
        await qm._worker_db.connect()

        # Simulate a completed task
        task = GenerationTask(
            platform_id="openai",
            source_id="src_test",
            model_config_id="mdl_test",
            prompt="a test prompt",
            negative_prompt="",
            params={"size": "1024x1024"},
        )
        task.status = "COMPLETED"
        task.result_paths = [str(tmp_path / "generations" / "test_image.png")]
        task.created_at = datetime.now()
        task.completed_at = datetime.now()

        # Create the image file so thumbnail path resolves
        os.makedirs(str(tmp_path / "generations"), exist_ok=True)
        with open(task.result_paths[0], "wb") as f:
            f.write(b"fake image data")

        # Call _save_history directly
        await qm._save_history(task)

        # Verify history was written by reading from main DB
        history = await main_db.get_generation_history(100)
        matching = [r for r in history if r["task_id"] == str(task.id)]
        assert len(matching) == 1
        assert matching[0]["prompt"] == "a test prompt"
        assert matching[0]["status"] == "COMPLETED"

        await qm._worker_db.close()
        await main_db.close()

    asyncio.run(scenario())
