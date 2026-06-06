import asyncio

from src.managers.queue_manager import QueueManager
from src.models.task import GenerationTask


class MissingConfigDb:
    async def get_platform_config(self, platform_id):
        return None


def test_process_task_fails_fast_when_platform_config_missing():
    async def scenario():
        manager = QueueManager()
        await manager.initialize(MissingConfigDb())
        events = []
        manager.set_status_callback(lambda task, status: events.append(status))
        task = GenerationTask(platform_id="openai", prompt="hello")

        await manager._process_task(task)

        assert task.status == "FAILED"
        assert "配置" in task.error
        assert events[-1] == "failed"

    asyncio.run(scenario())


class WorkingDb:
    def __init__(self):
        self.saved = []

    async def get_source(self, source_id):
        return {
            "id": source_id,
            "name": "OpenAI",
            "interface_type": "openai_images",
            "auth_preset": "openai",
            "api_base_url": "https://example.test/v1",
            "api_key_encrypted": None,
            "custom_headers": "{}",
            "proxy": None,
            "is_active": 1,
            "response_format": "openai",
        }

    async def get_source_model(self, model_id):
        return {
            "id": model_id,
            "source_id": "src_test",
            "display_name": "gpt-image-1",
            "model_id": "gpt-image-1",
            "default_size": "1024x1024",
            "default_quality": "standard",
            "default_n": 1,
            "sort_order": 0,
            "is_active": 1,
        }

    async def save_generation_history(self, record):
        self.saved.append(record)


class FakeResult:
    success = True
    image_paths = []
    error = None
    raw_response = {}


class FakeAdapter:
    async def generate(self, task, config):
        return FakeResult()


class SlowFakeAdapter:
    async def generate(self, task, config):
        await asyncio.sleep(0.2)
        return FakeResult()


def test_started_queue_processes_tasks_after_start_loop_returns(monkeypatch):
    import time
    import src.managers.queue_manager as queue_module

    monkeypatch.setattr(queue_module, "get_adapter", lambda platform_id: FakeAdapter())

    async def scenario():
        manager = QueueManager()
        db = WorkingDb()
        await manager.initialize(db)
        await manager.start()
        return manager, db

    manager, db = asyncio.run(scenario())
    task = GenerationTask(platform_id="openai", source_id="src_test", model_config_id="mdl_test", prompt="hello")
    manager.add_task(task)
    deadline = time.time() + 3
    while time.time() < deadline and task.status != "COMPLETED":
        time.sleep(0.05)

    asyncio.run(manager.stop())

    assert task.status == "COMPLETED"
    assert db.saved[-1]["status"] == "COMPLETED"


def test_task_snapshots_include_generating_task_prompt():
    manager = QueueManager()
    task = GenerationTask(platform_id="openai", prompt="正在生成的蝴蝶")
    task.status = "GENERATING"

    manager._in_flight_tasks[str(task.id)] = task

    snapshots = manager.get_task_snapshots()

    assert snapshots[0]["status"] == "GENERATING"
    assert snapshots[0]["prompt"] == "正在生成的蝴蝶"
    assert snapshots[0]["task_id"] == str(task.id)


def test_started_queue_snapshots_show_current_generating_prompt(monkeypatch):
    import time
    import src.managers.queue_manager as queue_module

    monkeypatch.setattr(queue_module, "get_adapter", lambda platform_id: SlowFakeAdapter())

    async def scenario():
        manager = QueueManager()
        await manager.initialize(WorkingDb())
        await manager.start()
        return manager

    manager = asyncio.run(scenario())
    task = GenerationTask(
        platform_id="openai",
        source_id="src_test",
        model_config_id="mdl_test",
        prompt="真实后台正在生成的提示词",
    )
    manager.add_task(task)

    deadline = time.time() + 3
    snapshots = []
    while time.time() < deadline:
        snapshots = manager.get_task_snapshots()
        if snapshots and snapshots[0]["status"] == "GENERATING":
            break
        time.sleep(0.05)

    asyncio.run(manager.stop())

    assert snapshots[0]["status"] == "GENERATING"
    assert snapshots[0]["prompt"] == "真实后台正在生成的提示词"


def test_finished_tasks_remain_visible_until_clear_completed(monkeypatch):
    import time
    import src.managers.queue_manager as queue_module

    monkeypatch.setattr(queue_module, "get_adapter", lambda platform_id: FakeAdapter())

    async def scenario():
        manager = QueueManager()
        await manager.initialize(WorkingDb())
        await manager.start()
        return manager

    manager = asyncio.run(scenario())
    task = GenerationTask(
        platform_id="openai",
        source_id="src_test",
        model_config_id="mdl_test",
        prompt="完成后仍可见",
    )
    manager.add_task(task)

    deadline = time.time() + 3
    while time.time() < deadline and task.status != "COMPLETED":
        time.sleep(0.05)

    info = manager.get_queue_info()
    snapshots = manager.get_task_snapshots()
    manager.clear_completed()
    cleared = manager.get_queue_info()

    asyncio.run(manager.stop())

    assert info["completed"] == 1
    assert snapshots[0]["status"] == "COMPLETED"
    assert snapshots[0]["prompt"] == "完成后仍可见"
    assert cleared["completed"] == 0



def test_background_queue_can_use_real_sqlite_database(tmp_path, monkeypatch):
    import time
    import src.managers.queue_manager as queue_module
    from src.config.database import Database

    monkeypatch.setattr(queue_module, "get_adapter", lambda platform_id: FakeAdapter())

    async def setup():
        db = Database(str(tmp_path / "queue.db"))
        await db.connect()
        await db.save_source({
            "id": "src_test",
            "name": "OpenAI",
            "api_base_url": "https://example.test/v1",
            "api_key_encrypted": None,
            "custom_headers": "{}",
            "proxy": None,
            "is_active": 1,
        })
        await db.save_source_model({
            "id": "mdl_test",
            "source_id": "src_test",
            "display_name": "gpt-image-1",
            "model_id": "gpt-image-1",
            "default_size": "1024x1024",
            "default_quality": "standard",
            "default_n": 1,
            "sort_order": 0,
            "is_active": 1,
        })
        manager = QueueManager()
        await manager.initialize(db)
        await manager.start()
        return manager, db

    manager, db = asyncio.run(setup())
    task = GenerationTask(platform_id="openai", source_id="src_test", model_config_id="mdl_test", prompt="hello")
    manager.add_task(task)

    deadline = time.time() + 3
    while time.time() < deadline and task.status != "COMPLETED":
        time.sleep(0.05)

    async def teardown():
        await manager.stop()
        history = await db.get_generation_history(10)
        await db.close()
        return history

    history = asyncio.run(teardown())
    assert task.status == "COMPLETED"
    assert history[0]["task_id"] == str(task.id)
    assert history[0]["status"] == "COMPLETED"
