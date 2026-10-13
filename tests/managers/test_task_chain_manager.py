import asyncio

from src.config.database import Database
from src.managers.task_chain_manager import TaskChainManager


class DummyQueueManager:
    pass


def make_manager():
    return TaskChainManager(db=None, queue_manager=DummyQueueManager())


def test_get_all_chains_returns_dicts_for_editor_compatibility():
    manager = make_manager()
    chain_data = {
        "name": "test chain",
        "tasks": [
            {
                "prompt": "forest cabin",
                "negative_prompt": "low quality",
                "params": {"size": "1024x1024"},
            }
        ],
    }

    chain_id = asyncio.run(manager.create_chain(chain_data))

    chains = manager.get_all_chains()

    assert len(chains) == 1
    assert chains[0]["id"] == chain_id
    assert chains[0]["name"] == "test chain"
    assert chains[0]["tasks"][0]["prompt"] == "forest cabin"


def test_get_chain_returns_single_chain_dict_or_none():
    manager = make_manager()

    chain_id = asyncio.run(manager.create_chain({"name": "single chain", "tasks": []}))

    chain = manager.get_chain(chain_id)

    assert chain is not None
    assert chain["id"] == chain_id
    assert chain["name"] == "single chain"
    assert manager.get_chain("missing") is None


def test_delete_chain_removes_chain_and_executor_if_present():
    manager = make_manager()

    chain_id = asyncio.run(manager.create_chain({"name": "delete me", "tasks": []}))
    manager._executors[chain_id] = object()

    assert manager.delete_chain(chain_id) is True
    assert manager.get_chain(chain_id) is None
    assert chain_id not in manager._executors
    assert manager.delete_chain(chain_id) is False


def test_delete_chain_stops_executor_before_removing_chain():
    class StoppableExecutor:
        def __init__(self):
            self.stopped = False

        def stop(self):
            self.stopped = True

    manager = make_manager()
    chain_id = asyncio.run(manager.create_chain({"name": "running", "tasks": []}))
    executor = StoppableExecutor()
    manager._executors[chain_id] = executor

    assert manager.delete_chain(chain_id) is True
    assert executor.stopped is True


def test_delete_chain_keeps_memory_when_database_delete_fails():
    class FailingDb:
        async def execute(self, sql, params=None):
            raise RuntimeError("database unavailable")

    manager = make_manager()
    chain_id = asyncio.run(manager.create_chain({"name": "keep me", "tasks": []}))
    manager.db = FailingDb()

    assert manager.delete_chain(chain_id) is False
    assert manager.get_chain(chain_id)["name"] == "keep me"


def test_create_chain_updates_existing_id_instead_of_duplicating():
    manager = make_manager()

    chain_id = asyncio.run(manager.create_chain({"id": "chain-1", "name": "first", "tasks": []}))
    updated_id = asyncio.run(manager.create_chain({"id": chain_id, "name": "updated", "tasks": []}))

    chains = manager.get_all_chains()
    assert updated_id == chain_id
    assert len(chains) == 1
    assert chains[0]["name"] == "updated"


def test_failed_chain_save_preserves_existing_in_memory_configuration():
    class FailingDb:
        async def execute(self, *args):
            raise RuntimeError("database unavailable")

    async def scenario():
        manager = make_manager()
        await manager.create_chain({"id": "existing", "name": "saved", "tasks": []})
        manager.db = FailingDb()
        try:
            await manager.create_chain({"id": "existing", "name": "unsaved", "tasks": []})
        except RuntimeError:
            pass
        else:
            raise AssertionError("save should fail")
        assert manager.get_chain("existing")["name"] == "saved"

    asyncio.run(scenario())


def test_start_chain_background_returns_without_running_inline():
    manager = make_manager()
    chain_id = asyncio.run(manager.create_chain({"name": "background", "tasks": []}))

    assert manager.start_chain_background(chain_id) is True
    assert chain_id in manager._executors
    assert manager.start_chain_background("missing") is False


def test_start_chain_background_marks_chain_failed_when_runner_crashes():
    manager = make_manager()
    chain_id = asyncio.run(manager.create_chain({"name": "crashy", "tasks": []}))

    async def crashing_execute(chain_id, chain, executor):
        chain.status = "running"
        raise RuntimeError("boom")

    manager._execute_chain = crashing_execute

    assert manager.start_chain_background(chain_id) is True
    manager._background_threads[chain_id].join(timeout=1)

    assert manager.get_chain(chain_id)["status"] == "failed"


def test_start_chain_background_persists_failed_status_when_runner_crashes():
    class RecordingDb:
        def __init__(self):
            self.saved_statuses = []

        async def execute(self, sql, params=None):
            self.saved_statuses.append(params[3])

    manager = make_manager()
    chain_id = asyncio.run(manager.create_chain({"name": "crashy", "tasks": []}))
    manager.db = RecordingDb()

    async def crashing_execute(chain_id, chain, executor):
        chain.status = "running"
        raise RuntimeError("boom")

    manager._execute_chain = crashing_execute

    assert manager.start_chain_background(chain_id) is True
    manager._background_threads[chain_id].join(timeout=1)

    assert manager.db.saved_statuses[-1] == "failed"


def test_task_chains_are_saved_and_loaded_from_database(tmp_path):
    async def scenario():
        db_path = tmp_path / "chains.sqlite"
        db = Database(str(db_path))
        await db.connect()
        manager = TaskChainManager(db=db, queue_manager=DummyQueueManager())
        chain_id = await manager.create_chain({
            "name": "persisted",
            "tasks": [{"prompt": "prompt", "source_id": "src", "model_config_id": "model"}],
        })
        await db.close()

        db2 = Database(str(db_path))
        await db2.connect()
        reloaded = TaskChainManager(db=db2, queue_manager=DummyQueueManager())
        await reloaded.load_chains()
        chain = reloaded.get_chain(chain_id)
        await db2.close()
        return chain

    chain = asyncio.run(scenario())

    assert chain is not None
    assert chain["name"] == "persisted"
    assert chain["tasks"][0]["source_id"] == "src"
    assert chain["tasks"][0]["model_config_id"] == "model"
