import asyncio
import threading

from src.managers.queue_manager import QueueManager
from src.models.task import GenerationTask
from tests.test_queue_manager_stability import FakeAdapter, WorkingDb


def make_task(prompt="test"):
    return GenerationTask(source_id="src_test", model_config_id="mdl_test", prompt=prompt)


def test_idle_worker_sleeps_until_submission_and_result_is_persisted(monkeypatch):
    monkeypatch.setattr("src.managers.queue_manager.get_adapter", lambda _: FakeAdapter())

    async def scenario():
        queue = QueueManager()
        db = WorkingDb()
        await queue.initialize(db)
        scans = []
        pop = queue._pop_next_task

        def counted_pop():
            scans.append(True)
            return pop()

        queue._pop_next_task = counted_pop
        notified = threading.Event()
        queue.set_event_callback(notified.set)
        await queue.start()
        try:
            await asyncio.sleep(0.15)
            initial = len(scans)
            await asyncio.sleep(0.15)
            assert len(scans) == initial == 1
            task = make_task()
            queue.add_task(task)
            assert await asyncio.wait_for(queue.wait_for_task(task), 2) == "COMPLETED"
            assert db.saved[-1]["status"] == "COMPLETED"
            assert notified.is_set()
            events = queue.drain_status_events()
            added = next(snapshot for snapshot, status in events if status == "added")
            assert added.status == "WAITING"  # Later transitions do not change an earlier snapshot.
        finally:
            await queue.stop()
        assert queue._worker_thread is None

    asyncio.run(scenario())


def test_stopping_one_waiter_does_not_cancel_generation_and_waiting_tasks_cancel_on_shutdown(monkeypatch):
    gate = threading.Event()
    started = threading.Event()

    class Controlled(FakeAdapter):
        async def generate(self, task, config):
            started.set()
            await asyncio.to_thread(gate.wait, 2)
            return await super().generate(task, config)

    monkeypatch.setattr("src.managers.queue_manager.get_adapter", lambda _: Controlled())

    async def scenario():
        queue = QueueManager()
        queue.max_concurrent = 1
        await queue.initialize(WorkingDb())
        await queue.start()
        first = make_task("first")
        queue.add_task(first)
        assert await asyncio.to_thread(started.wait, 2)
        observer = asyncio.create_task(queue.wait_for_task(first))
        await asyncio.sleep(0)
        observer.cancel()
        await asyncio.gather(observer, return_exceptions=True)
        assert not first._completion.cancelled()
        gate.set()
        assert await asyncio.wait_for(queue.wait_for_task(first), 2) == "COMPLETED"
        await queue.stop()
        assert not queue._active_jobs

    asyncio.run(scenario())


def test_shutdown_cancels_waiting_tasks_without_submitting_them(monkeypatch):
    gate = threading.Event()
    started = threading.Event()
    submitted = []

    class Controlled(FakeAdapter):
        async def generate(self, task, config):
            submitted.append(task.prompt)
            started.set()
            await asyncio.to_thread(gate.wait, 2)
            return await super().generate(task, config)

    monkeypatch.setattr("src.managers.queue_manager.get_adapter", lambda _: Controlled())

    async def scenario():
        queue = QueueManager()
        queue.max_concurrent = 1
        await queue.initialize(WorkingDb())
        await queue.start()
        first, waiting = make_task("first"), make_task("waiting")
        queue.add_task(first)
        queue.add_task(waiting)
        assert await asyncio.to_thread(started.wait, 2)
        stopped = asyncio.create_task(queue.stop())
        await asyncio.sleep(0)
        assert await queue.wait_for_task(waiting) == "CANCELLED"
        gate.set()
        await asyncio.wait_for(stopped, 3)
        assert submitted == ["first"]
        assert queue._worker_thread is None

    asyncio.run(scenario())
