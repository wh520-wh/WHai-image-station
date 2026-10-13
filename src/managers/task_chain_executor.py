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

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop(self):
        self._stopped = True

    async def execute(self):
        for task in self.chain.tasks:
            if self._stopped:
                break

            while self._paused and not self._stopped:
                await asyncio.sleep(0.5)
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

            while gen_task.status.upper() in {"WAITING", "PENDING", "GENERATING"}:
                if self._stopped:
                    self.queue_manager.cancel_task(str(gen_task.id))
                    return "STOPPED"
                await asyncio.sleep(0.5)

            return gen_task.status.upper()
        except Exception:
            return "FAILED"
