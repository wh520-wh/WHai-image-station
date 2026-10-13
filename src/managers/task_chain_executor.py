from __future__ import annotations

import asyncio

from src.models.task_chain import ChainTask, TaskChain


class ChainExecutor:
    def __init__(self, chain: TaskChain, queue_manager, status_callback=None):
        self.chain = chain
        self.queue_manager = queue_manager
        self.status_callback = status_callback
        self._paused = False
        self._stopped = False
        self._loop = None
        self._resume_event: asyncio.Event | None = None
        self._stop_event: asyncio.Event | None = None

    @property
    def stopped(self):
        return self._stopped

    def _signal(self, event):
        if self._loop and event:
            try:
                self._loop.call_soon_threadsafe(event.set)
            except RuntimeError:
                pass

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False
        self._signal(self._resume_event)

    def stop(self):
        self._stopped = True
        self._signal(self._stop_event)
        self._signal(self._resume_event)

    async def execute(self):
        self._loop = asyncio.get_running_loop()
        self._resume_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        for task in self.chain.tasks:
            if self._stopped:
                break

            while self._paused and not self._stopped:
                self._resume_event.clear()
                await self._resume_event.wait()
            if self._stopped:
                break

            task.status = "generating"
            if self.status_callback:
                self.status_callback(task, "generating")

            result = await self._execute_task(task)

            if result == "STOPPED":
                task.status = "skipped"
                break
            if result == "COMPLETED":
                task.status = "completed"
            else:
                task.status = "failed"
                if self.chain.failure_mode == "stop":
                    break

            if self.status_callback:
                self.status_callback(task, task.status)

    async def _execute_task(self, task: ChainTask) -> str:
        """执行单个任务，返回结果状态"""
        try:
            from src.models.task import GenerationTask

            gen_task = GenerationTask(
                platform_id="openai",
                source_id=task.source_id,
                model_config_id=task.model_config_id,
                prompt=task.prompt,
                negative_prompt=task.negative_prompt,
                params=dict(task.params),
                reference_image_path=task.reference_image_path,
            )
            self.queue_manager.add_task(gen_task)
            assert self._stop_event
            completed = asyncio.create_task(self.queue_manager.wait_for_task(gen_task))
            stopped = asyncio.create_task(self._stop_event.wait())
            try:
                await asyncio.wait({completed, stopped}, return_when=asyncio.FIRST_COMPLETED)
                if self._stopped:
                    self.queue_manager.cancel_task(str(gen_task.id))
                    return "STOPPED"
                return (await completed).upper()
            finally:
                completed.cancel()
                stopped.cancel()
                await asyncio.gather(completed, stopped, return_exceptions=True)
        except Exception:
            return "FAILED"
