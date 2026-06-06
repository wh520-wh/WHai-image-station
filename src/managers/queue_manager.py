import asyncio
import json
import threading
from datetime import datetime
from collections import deque
from typing import Optional, Callable

import os

from src.models.task import GenerationTask
from src.models.platform_config import PlatformConfig
from src.adapters import get_adapter
from src.config import constants, database
from src.config.encryption import decrypt


class QueueManager:
    _instance: Optional["QueueManager"] = None

    def __init__(self):
        self.tasks: deque[GenerationTask] = deque()
        self.max_concurrent = constants.DEFAULT_CONCURRENT
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._wake_event = threading.Event()
        self._tasks_lock = threading.Lock()
        self._events_lock = threading.Lock()
        self._status_events: deque[tuple[GenerationTask, str]] = deque(maxlen=500)
        self._status_callback: Optional[Callable] = None
        self._db: Optional[database.Database] = None
        self._worker_db: Optional[database.Database] = None
        self._generating_count = 0
        self._generating_lock = threading.Lock()
        self._in_flight_tasks: dict[str, GenerationTask] = {}
        self._finished_tasks: deque[GenerationTask] = deque(maxlen=50)

    @classmethod
    def get_instance(cls) -> "QueueManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self, db: database.Database):
        self._db = db

    def set_status_callback(self, callback: Callable):
        self._status_callback = callback

    def add_task(self, task: GenerationTask) -> str:
        task.status = "WAITING"
        with self._tasks_lock:
            self.tasks.append(task)
        self._notify(task, "added")
        self._wake_event.set()
        return str(task.id)

    async def start(self):
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._thread_main,
            name="imageMaker-queue-worker",
            daemon=True,
        )
        self._worker_thread.start()

    async def stop(self):
        self._running = False
        self._wake_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2)
        self._worker_thread = None

    def drain_status_events(self) -> list[tuple[GenerationTask, str]]:
        with self._events_lock:
            events = list(self._status_events)
            self._status_events.clear()
        return events

    def _thread_main(self):
        asyncio.run(self._async_thread_main())

    async def _async_thread_main(self):
        # Create a dedicated DB connection for this worker thread's event loop.
        # Only needed when the main DB is a real Database (not a mock) — use
        # the same path so the worker reads/writes the same data file.
        if self._db and hasattr(self._db, "db_path"):
            self._worker_db = database.Database(self._db.db_path)
            await self._worker_db.connect()

        try:
            semaphore = asyncio.Semaphore(self.max_concurrent)
            in_flight: set[asyncio.Task] = set()
            while self._running:
                task = self._pop_next_task()
                if task is None:
                    await asyncio.sleep(0.5)
                    in_flight = {t for t in in_flight if not t.done()}
                    continue
                t = asyncio.create_task(self._process_task_with_semaphore(task, semaphore))
                in_flight.add(t)
            if in_flight:
                await asyncio.gather(*in_flight, return_exceptions=True)
        finally:
            if self._worker_db:
                await self._worker_db.close()
                self._worker_db = None

    def _pop_next_task(self) -> Optional[GenerationTask]:
        with self._tasks_lock:
            if not self.tasks:
                return None
            return self.tasks.popleft()

    async def _process_task(self, task: GenerationTask):
        task.status = "PENDING"
        task.started_at = datetime.now()
        self._notify(task, "pending")

        try:
            config = await self._load_platform_config(task)
            if not config:
                return

            adapter = get_adapter(task.platform_id)
            if not adapter:
                await self._fail_task(task, f"未找到平台适配器: {task.platform_id}")
                return

            task.status = "GENERATING"
            self._notify(task, "generating")

            result = await adapter.generate(task, config)
            if result.success:
                task.status = "COMPLETED"
                task.result_paths = result.image_paths
                task.completed_at = datetime.now()
            else:
                task.status = "FAILED"
                task.error = result.error or "生成失败"
            task.params["_diagnostic"] = (result.raw_response or {}).get("diagnostic", {})

            await self._save_history(task)
            self._notify(task, "completed" if task.status == "COMPLETED" else "failed")
        except Exception as exc:
            await self._fail_task(task, f"任务执行异常: {exc}")

    async def _process_task_with_semaphore(self, task: GenerationTask, semaphore: asyncio.Semaphore):
        async with semaphore:
            with self._generating_lock:
                self._generating_count += 1
                self._in_flight_tasks[str(task.id)] = task
            try:
                await self._process_task(task)
            finally:
                with self._generating_lock:
                    if task.status in ("COMPLETED", "FAILED"):
                        self._finished_tasks.appendleft(task)
                    self._generating_count -= 1
                    self._in_flight_tasks.pop(str(task.id), None)

    async def _load_platform_config(self, task: GenerationTask) -> Optional[PlatformConfig]:
        db = self._worker_db or self._db
        if not db:
            await self._fail_task(task, "数据库未初始化，无法读取平台配置")
            return None

        if not task.source_id or not task.model_config_id:
            await self._fail_task(task, "任务缺少来源或模型配置，请重新提交任务。")
            return None
        config_data = await self._load_source_model_config(task)
        if not config_data:
            await self._fail_task(task, "来源或模型配置不存在，请先在设置中配置。")
            return None

        try:
            api_key_encrypted = config_data.get("api_key_encrypted")
            api_key = decrypt(api_key_encrypted) if api_key_encrypted else ""
            custom_headers = self._parse_headers(config_data.get("custom_headers"))
        except Exception as exc:
            await self._fail_task(task, f"平台配置读取失败，请重新保存配置: {exc}")
            return None

        return PlatformConfig(
            id=config_data["id"],
            name=config_data["name"],
            api_base_url=config_data["api_base_url"],
            api_key=api_key,
            custom_headers=custom_headers,
            model_name=config_data.get("model_name", ""),
            source_id=config_data.get("source_id", task.source_id),
            model_config_id=config_data.get("model_config_id", task.model_config_id),
            source_name=config_data.get("source_name", config_data.get("name", "")),
            model_display_name=config_data.get("model_display_name", config_data.get("model_name", "")),
            auth_preset=config_data.get("auth_preset", "openai"),
            interface_type=config_data.get("interface_type", "openai_images"),
            response_format=config_data.get("response_format", "openai"),
            proxy=config_data.get("proxy"),
            is_active=bool(config_data.get("is_active", 1)),
        )

    async def _load_source_model_config(self, task: GenerationTask) -> Optional[dict]:
        db = self._worker_db or self._db
        source = await db.get_source(task.source_id)
        model = await db.get_source_model(task.model_config_id)
        if not source or not model:
            return None
        interface_type = source.get("interface_type", "openai_images")
        runtime_id = "custom" if interface_type == "custom" else "openai"
        return {
            "id": runtime_id,
            "name": source["name"],
            "api_base_url": source["api_base_url"],
            "api_key_encrypted": source.get("api_key_encrypted"),
            "custom_headers": source.get("custom_headers"),
            "proxy": source.get("proxy"),
            "is_active": source.get("is_active", 1),
            "model_name": model["model_id"],
            "source_id": source["id"],
            "model_config_id": model["id"],
            "source_name": source["name"],
            "model_display_name": model["display_name"],
            "auth_preset": source.get("auth_preset", "openai"),
            "interface_type": source.get("interface_type", "openai_images"),
            "response_format": source.get("response_format", "openai"),
        }

    def _parse_headers(self, raw_headers) -> dict[str, str]:
        if not raw_headers:
            return {}
        if isinstance(raw_headers, dict):
            return {str(key): str(value) for key, value in raw_headers.items()}
        parsed = json.loads(raw_headers)
        if not isinstance(parsed, dict):
            return {}
        return {str(key): str(value) for key, value in parsed.items()}

    async def _fail_task(self, task: GenerationTask, error: str):
        task.status = "FAILED"
        task.error = error
        task.completed_at = datetime.now()
        await self._save_history(task)
        self._notify(task, "failed")

    async def _save_history(self, task: GenerationTask):
        db = self._worker_db or self._db
        if not db or not hasattr(db, "save_generation_history"):
            return
        # image_path 保持存第一张（兼容性）
        image_path = task.result_paths[0] if task.result_paths else None
        # result_paths_json 存完整列表
        result_paths_json = task.result_paths
        diagnostic = task.params.get("_diagnostic", {}) if isinstance(task.params, dict) else {}
        params = dict(task.params or {})
        params.pop("_diagnostic", None)
        try:
            await db.save_generation_history({
                "task_id": str(task.id),
                "platform_id": task.platform_id,
                "source_id": task.source_id,
                "model_config_id": task.model_config_id,
                "prompt": task.prompt,
                "negative_prompt": task.negative_prompt,
                "params": params,
                "image_path": image_path,
                "thumbnail_path": self._get_thumbnail_path(image_path),
                "result_paths_json": result_paths_json,
                "status": task.status,
                "error": task.error,
                "request_url": diagnostic.get("request_url"),
                "request_payload": diagnostic.get("payload", {}),
                "response_summary": diagnostic.get("response_summary"),
                "diagnostic": diagnostic,
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            })
        except Exception:
            return

    def _notify(self, task: GenerationTask, status: str):
        if threading.current_thread() is threading.main_thread():
            if self._status_callback:
                self._status_callback(task, status)
            return
        with self._events_lock:
            self._status_events.append((task, status))

    def _get_thumbnail_path(self, image_path: str) -> Optional[str]:
        if not image_path:
            return None
        name = os.path.basename(image_path)
        thumb_name = f"thumb_{os.path.splitext(name)[0]}.jpg"
        return os.path.join(constants.THUMBNAILS_DIR, thumb_name)

    def get_queue_info(self) -> dict:
        with self._tasks_lock:
            queued_tasks = list(self.tasks)
        waiting = completed = failed = 0
        for task in queued_tasks:
            if task.status == "WAITING":     waiting += 1
            elif task.status == "COMPLETED": completed += 1
            elif task.status == "FAILED":    failed += 1
        with self._generating_lock:
            generating = self._generating_count
            completed += sum(1 for task in self._finished_tasks if task.status == "COMPLETED")
            failed += sum(1 for task in self._finished_tasks if task.status == "FAILED")
        return {
            "total": len(queued_tasks),
            "waiting": waiting,
            "generating": generating,
            "completed": completed,
            "failed": failed,
        }

    def get_task_snapshots(self, limit: int = 5) -> list[dict]:
        with self._tasks_lock:
            queued_tasks = list(self.tasks)
        with self._generating_lock:
            in_flight_tasks = list(self._in_flight_tasks.values())
            finished_tasks = list(self._finished_tasks)
        return [task.to_dict() for task in (in_flight_tasks + queued_tasks + finished_tasks)[:limit]]

    def cancel_task(self, task_id: str) -> bool:
        with self._tasks_lock:
            for task in list(self.tasks):
                if str(task.id) == task_id and task.status == "WAITING":
                    self.tasks.remove(task)
                    self._notify(task, "cancelled")
                    return True
        return False

    def clear_completed(self):
        with self._tasks_lock:
            self.tasks = deque(task for task in self.tasks if task.status not in ("COMPLETED", "FAILED"))
        with self._generating_lock:
            self._finished_tasks.clear()
