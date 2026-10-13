import asyncio

from src.managers.task_chain_executor import ChainExecutor
from src.models.task_chain import ChainTask, TaskChain


class CompletingQueueManager:
    def add_task(self, task):
        async def complete_task():
            await asyncio.sleep(0)
            task.status = "COMPLETED"

        self.completion = asyncio.create_task(complete_task())
        return str(task.id)

    async def wait_for_task(self, task):
        await self.completion
        return task.status


class FailingQueueManager:
    def add_task(self, task):
        async def fail_task():
            await asyncio.sleep(0)
            task.status = "FAILED"

        self.completion = asyncio.create_task(fail_task())
        return str(task.id)

    async def wait_for_task(self, task):
        await self.completion
        return task.status


def test_execute_treats_uppercase_queue_statuses_as_success():
    chain = TaskChain(
        id="chain",
        name="chain",
        tasks=[ChainTask(task_id="task-1", chain_order=0, prompt="prompt")],
    )
    executor = ChainExecutor(chain, CompletingQueueManager())

    asyncio.run(executor.execute())

    assert chain.tasks[0].status == "completed"


def test_failure_mode_stop_stops_after_first_failed_task():
    chain = TaskChain(
        id="chain",
        name="chain",
        failure_mode="stop",
        tasks=[
            ChainTask(task_id="task-1", chain_order=0, prompt="first"),
            ChainTask(task_id="task-2", chain_order=1, prompt="second"),
        ],
    )
    executor = ChainExecutor(chain, FailingQueueManager())

    asyncio.run(executor.execute())

    assert chain.tasks[0].status == "failed"
    assert chain.tasks[1].status == "pending"


def test_failure_mode_skip_continues_after_failed_task():
    chain = TaskChain(
        id="chain",
        name="chain",
        failure_mode="skip",
        tasks=[
            ChainTask(task_id="task-1", chain_order=0, prompt="first"),
            ChainTask(task_id="task-2", chain_order=1, prompt="second"),
        ],
    )
    executor = ChainExecutor(chain, FailingQueueManager())

    asyncio.run(executor.execute())

    assert chain.tasks[0].status == "failed"
    assert chain.tasks[1].status == "failed"
