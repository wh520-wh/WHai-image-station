from __future__ import annotations

import asyncio
import json
import threading
import uuid
from collections import deque
from datetime import datetime

from src.managers.task_chain_executor import ChainExecutor
from src.models.task_chain import ChainTask, TaskChain


class TaskChainManager:
    _instance = None

    def __init__(self, db, queue_manager):
        self.db = db
        self.queue_manager = queue_manager
        self._chains: dict[str, TaskChain] = {}
        self._executors: dict[str, ChainExecutor] = {}
        self._background_threads: dict[str, threading.Thread] = {}
        self._status_events = deque()
        self._status_events_lock = threading.Lock()
        self._status_callback = None

    @classmethod
    def get_instance(cls, db=None, queue_manager=None):
        if cls._instance is None and db and queue_manager:
            cls._instance = cls(db, queue_manager)
        return cls._instance

    def set_status_callback(self, callback):
        self._status_callback = callback

    def drain_status_events(self) -> list[TaskChain]:
        with self._status_events_lock:
            events = list(self._status_events)
            self._status_events.clear()
        return events

    async def create_chain(self, chain_data: dict) -> str:
        chain_id = chain_data.get("id") or str(uuid.uuid4())
        chain = self._chain_from_data(chain_data, chain_id)
        self._chains[chain_id] = chain
        await self._save_chain(chain)
        return chain_id

    async def start_chain(self, chain_id: str) -> None:
        chain = self._chains.get(chain_id)
        if not chain:
            return
        executor = ChainExecutor(chain, self.queue_manager, self._on_task_status_changed)
        self._executors[chain_id] = executor
        await self._execute_chain(chain_id, chain, executor)

    def start_chain_background(self, chain_id: str) -> bool:
        chain = self._chains.get(chain_id)
        if not chain:
            return False
        if chain_id in self._background_threads and self._background_threads[chain_id].is_alive():
            executor = self._executors.get(chain_id)
            if executor and chain.status == "paused":
                executor.resume()
                chain.status = "running"
                self._notify_status(chain)
            return True

        executor = ChainExecutor(chain, self.queue_manager, self._on_task_status_changed)
        self._executors[chain_id] = executor

        def _runner():
            try:
                asyncio.run(self._execute_chain(chain_id, chain, executor))
            except Exception:
                chain.status = "failed"
                try:
                    asyncio.run(self._save_chain(chain))
                except Exception:
                    pass
                self._notify_status(chain)

        thread = threading.Thread(target=_runner, name=f"task-chain-{chain_id}", daemon=True)
        self._background_threads[chain_id] = thread
        thread.start()
        return True

    async def _execute_chain(self, chain_id: str, chain: TaskChain, executor: ChainExecutor) -> None:
        chain.status = "running"
        self._notify_status(chain)
        await executor.execute()
        chain.status = (
            "idle"
            if executor._stopped
            else ("failed" if any(task.status == "failed" for task in chain.tasks) else "completed")
        )
        await self._save_chain(chain)
        self._notify_status(chain)

    async def pause_chain(self, chain_id: str) -> None:
        if chain_id in self._executors:
            self._executors[chain_id].pause()
            self._chains[chain_id].status = "paused"
            self._notify_status(self._chains[chain_id])

    async def stop_chain(self, chain_id: str) -> None:
        if chain_id in self._executors:
            self._executors[chain_id].stop()
            self._chains[chain_id].status = "idle"
            self._notify_status(self._chains[chain_id])

    def get_chain_status(self, chain_id: str) -> TaskChain | None:
        return self._chains.get(chain_id)

    def get_all_chains(self) -> list[dict]:
        return [chain.to_dict() for chain in self._chains.values()]

    def get_chain(self, chain_id: str) -> dict | None:
        chain = self._chains.get(chain_id)
        return chain.to_dict() if chain else None

    def delete_chain(self, chain_id: str) -> bool:
        removed = self._chains.get(chain_id)
        if not removed:
            return False
        if self.db:
            try:
                from src.config.event_loop import run_async

                run_async(self._delete_chain(chain_id))
            except Exception:
                return False
        self._discard_chain(chain_id)
        return True

    async def delete_chain_async(self, chain_id: str) -> bool:
        if chain_id not in self._chains:
            return False
        await self._delete_chain(chain_id)
        self._discard_chain(chain_id)
        return True

    def _discard_chain(self, chain_id):
        executor = self._executors.get(chain_id)
        if executor and hasattr(executor, "stop"):
            executor.stop()
        self._chains.pop(chain_id, None)
        self._executors.pop(chain_id, None)
        self._background_threads.pop(chain_id, None)

    def _chain_from_data(self, chain_data: dict, chain_id: str) -> TaskChain:
        existing = self._chains.get(chain_id)
        tasks = []
        for i, task_data in enumerate(chain_data.get("tasks", [])):
            params = dict(task_data.get("params") or {})
            if "steps" in task_data and "steps" not in params:
                params["steps"] = task_data["steps"]
            if "guidance" in task_data and "guidance" not in params:
                params["guidance"] = task_data["guidance"]
            tasks.append(
                ChainTask(
                    task_id=task_data.get("task_id") or str(uuid.uuid4()),
                    chain_order=int(task_data.get("chain_order", i)),
                    source_id=task_data.get("source_id", ""),
                    model_config_id=task_data.get("model_config_id", ""),
                    prompt=task_data.get("prompt", ""),
                    negative_prompt=task_data.get("negative_prompt", ""),
                    params=params,
                    status=task_data.get("status", "pending"),
                    trigger_on=task_data.get("trigger_on", "success"),
                    reference_image_path=task_data.get("reference_image_path"),
                )
            )
        created_at = existing.created_at if existing else self._parse_created_at(chain_data.get("created_at"))
        return TaskChain(
            id=chain_id,
            name=chain_data.get("name", "未命名任务链"),
            tasks=tasks,
            created_at=created_at,
            status=chain_data.get("status", existing.status if existing else "idle"),
            failure_mode=chain_data.get("failure_mode", "stop"),
        )

    def _parse_created_at(self, value) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        return datetime.now()

    def _on_task_status_changed(self, task: ChainTask, status: str):
        task.status = status
        for chain in self._chains.values():
            if task in chain.tasks:
                self._notify_status(chain)
                break

    def _notify_status(self, chain: TaskChain):
        if not self._status_callback:
            return
        if threading.current_thread() is threading.main_thread():
            self._status_callback(chain)
            return
        with self._status_events_lock:
            self._status_events.append(chain)

    async def _save_chain(self, chain: TaskChain):
        if not self.db:
            return
        from src.config.database import Database

        if isinstance(self.db, Database) and threading.current_thread() is not threading.main_thread():
            worker_db = Database(self.db.db_path)
            await worker_db.connect()
            try:
                await self._write_chain(worker_db, chain)
            finally:
                await worker_db.close()
        else:
            await self._write_chain(self.db, chain)

    async def _write_chain(self, db, chain):
        data = chain.to_dict()
        await db.execute(
            """
            INSERT OR REPLACE INTO task_chains
            (id, name, created_at, status, failure_mode, tasks_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["name"],
                data["created_at"],
                data["status"],
                data["failure_mode"],
                json.dumps(data["tasks"], ensure_ascii=False),
            ),
        )

    async def _delete_chain(self, chain_id: str):
        if self.db:
            await self.db.execute("DELETE FROM task_chains WHERE id = ?", (chain_id,))

    async def load_chains(self):
        if not self.db:
            return
        rows = await self.db.fetchall(
            """
            SELECT id, name, created_at, status, failure_mode, tasks_json
            FROM task_chains
            ORDER BY created_at ASC, name ASC
            """
        )
        self._chains.clear()
        for row in rows:
            tasks = json.loads(row[5] or "[]")
            chain_data = {
                "id": row[0],
                "name": row[1],
                "created_at": row[2],
                "status": row[3],
                "failure_mode": row[4],
                "tasks": tasks,
            }
            self._chains[row[0]] = self._chain_from_data(chain_data, row[0])
            if self._chains[row[0]].status in ("running", "paused"):
                self._chains[row[0]].status = "idle"
                for task in self._chains[row[0]].tasks:
                    if task.status == "generating":
                        task.status = "pending"
                await self._save_chain(self._chains[row[0]])
