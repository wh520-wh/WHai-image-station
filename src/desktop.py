"""Qt Quick presentation bridge. Network and persistence stay in the Python services."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication, QImage
from PySide6.QtWidgets import QFileDialog

from src.config import constants, encryption
from src.config.database import Database
from src.config.event_loop import schedule_async
from src.config.providers import (
    INTERFACE_LABELS,
    PROVIDER_PRESETS,
    RETIRED_MODELS,
    adapter_id,
    make_preset,
    model_capabilities,
)
from src.config.utils import parse_headers, safe_int
from src.managers.batch_ops_manager import BatchOpsManager
from src.managers.history_manager import HistoryManager
from src.managers.migration_manager import ExportOptions, ImportOptions, MigrationManager
from src.managers.prompt_manager import PromptManager
from src.managers.queue_manager import QueueManager
from src.managers.task_chain_manager import TaskChainManager
from src.models.task import GenerationTask


class RecordModel(QAbstractListModel):
    """Incremental gallery model; delegates and images exist only around the viewport."""

    ItemRole = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.records: list[dict] = []

    def roleNames(self):
        return {self.ItemRole: b"record"}

    def rowCount(self, parent=None):
        parent = parent or QModelIndex()
        return 0 if parent.isValid() else len(self.records)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == self.ItemRole and 0 <= index.row() < len(self.records):
            return self.records[index.row()]
        return None

    def replace(self, records):
        self.beginResetModel()
        self.records = records
        self.endResetModel()

    def append(self, records):
        if not records:
            return
        start = len(self.records)
        self.beginInsertRows(QModelIndex(), start, start + len(records) - 1)
        self.records.extend(records)
        self.endInsertRows()


def file_url(path):
    return QUrl.fromLocalFile(str(path)).toString() if path else ""


def valid_dimensions(value):
    parts = str(value).replace("×", "x").lower().split("x")
    return len(parts) == 2 and all(part.isdigit() and int(part) > 0 for part in parts)


def system_reduced_motion():
    if os.name == "nt":
        import ctypes

        enabled = ctypes.c_int(1)
        if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
            return not bool(enabled.value)
    return False


class StudioBridge(QObject):
    stateChanged = Signal()
    message = Signal(str, bool)
    navigate = Signal(str)
    viewerRequested = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db: Database | None = None
        self.queue = QueueManager.get_instance()
        self.chains: TaskChainManager | None = None
        self.gallery = RecordModel(self)
        self._sources: list[dict] = []
        self._models: list[dict] = []
        self._query = ""
        self._filter = ""
        self._gallery_revision = 0
        self._state = {
            "ready": False,
            "loadingText": "正在打开工作台…",
            "busy": False,
            "galleryLoading": False,
            "sources": [],
            "models": [],
            "activeSources": [],
            "activeModels": [],
            "tasks": [],
            "prompts": [],
            "chains": [],
            "sourceId": "",
            "modelId": "",
            "caps": model_capabilities("openai_images", "gpt-image-2"),
            "draft": {
                "prompt": "",
                "negative_prompt": "",
                "size": "1024x1024",
                "quality": "auto",
                "n": 1,
                "seed": "",
                "output_format": "png",
                "transparent": False,
                "reference": "",
            },
            "presets": [
                {"id": key, **{k: v for k, v in value.items() if k != "models"}}
                for key, value in PROVIDER_PRESETS.items()
            ],
            "interfaces": [{"id": key, "name": value} for key, value in INTERFACE_LABELS.items()],
            "galleryTotal": 0,
            "galleryHasMore": False,
            "selected": [],
            "activeCount": 0,
            "reducedMotion": system_reduced_motion(),
            "dark": False,
            "concurrent": constants.DEFAULT_CONCURRENT,
            "version": constants.APP_VERSION,
            "dataPath": str(Path(constants.DEFAULT_DB_PATH).parent),
            "imagePath": constants.GENERATIONS_DIR,
        }
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._drain_events)

    @Property(dict, notify=stateChanged)
    def state(self):
        return self._state

    @Property(QObject, constant=True)
    def galleryModel(self):
        return self.gallery

    def update(self, **values):
        self._state.update(values)
        self.stateChanged.emit()

    def launch(self, operation, success=None, busy=False):
        if busy and self._state["busy"]:
            operation.close()
            return
        if busy:
            self.update(busy=True)

        def done(value):
            if busy:
                self.update(busy=False)
            if success:
                success(value)

        def failed(error):
            if busy:
                self.update(busy=False)
            self.message.emit(str(error), True)

        schedule_async(operation, on_success=done, on_error=failed)

    async def initialize(self, db: Database):
        self.db = db
        self.update(loadingText="正在整理来源与作品…")
        # Presets contain no credentials and never make a network request.
        if not await db.get_sources():
            async with db.transaction():
                for key in ("openai", "gemini", "bfl", "minimax"):
                    source, models = make_preset(key, "src_" + uuid4().hex)
                    await db.save_source(source)
                    for model in models:
                        await db.save_source_model(model)
        # Preserve custom relays and old records, but retire unsupported official defaults.
        for source in await db.get_sources():
            if QUrl(source["api_base_url"]).host() != "api.openai.com":
                continue
            models = await db.get_source_models(source["id"])
            retired = [model for model in models if model["model_id"] in RETIRED_MODELS and model["is_active"]]
            if retired:
                async with db.transaction():
                    for model in retired:
                        await db.save_source_model(dict(model, is_active=0))
                    if not any(m["is_active"] and m["model_id"] not in RETIRED_MODELS for m in models):
                        _, replacements = make_preset("openai", source["id"])
                        for model in replacements:
                            model["id"] = "mdl_" + uuid4().hex
                            await db.save_source_model(model)
        self.chains = TaskChainManager(db, self.queue)
        self.chains.set_status_callback(lambda _: self.refresh_chains())
        await self.chains.load_chains()
        await self.reload_sources()
        self.selectSource(await db.get_pref("last_source"))
        self.selectModel(await db.get_pref("last_model"))
        await self.reload_prompts()
        await self.load_gallery()
        self.refresh_chains()
        motion = await db.get_pref("reduced_motion", "system")
        concurrent = max(1, min(4, safe_int(await db.get_pref("concurrent"), constants.DEFAULT_CONCURRENT)))
        self.queue.max_concurrent = concurrent
        self.update(
            ready=True,
            dark=await db.get_pref("theme", "light") == "dark",
            reducedMotion=system_reduced_motion() if motion == "system" else motion == "true",
            concurrent=concurrent,
        )
        self._timer.start()

    async def reload_sources(self):
        assert self.db
        self._sources = await self.db.get_sources()
        self._models = await self.db.get_source_models()
        safe = []
        for source in self._sources:
            item = {k: v for k, v in source.items() if k != "api_key_encrypted"}
            item["has_key"] = bool(source.get("api_key_encrypted"))
            safe.append(item)
        self.update(sources=safe, models=self._models, activeSources=[s for s in safe if s["is_active"]])
        self.selectSource(self._state["sourceId"])

    @Slot(str)
    def selectSource(self, source_id):
        active = self._state["activeSources"]
        fallback = next((s for s in active if s["interface_type"] == "openai_images"), active[0] if active else {})
        source_id = source_id if any(s["id"] == source_id for s in active) else fallback.get("id", "")
        models = [m for m in self._models if m["source_id"] == source_id and m["is_active"]]
        self.update(sourceId=source_id, activeModels=models)
        source = next((s for s in self._sources if s["id"] == source_id), {})
        self.update(
            sourceConfigured=bool(
                source.get("api_key_encrypted")
                or source.get("auth_preset") == "none"
                or parse_headers(source.get("custom_headers"))
            )
        )
        self.selectModel(self._state["modelId"])

    @Slot()
    def configureSource(self):
        self.update(editSourceId=self._state["sourceId"])
        self.navigate.emit("sources")

    @Slot(str)
    def selectModel(self, model_id):
        models = self._state["activeModels"]
        model = next((m for m in models if m["id"] == model_id), models[0] if models else None)
        changed = (model["id"] if model else "") != self._state["modelId"]
        source = next((s for s in self._sources if s["id"] == self._state["sourceId"]), {})
        caps = model_capabilities(source.get("interface_type", "openai_images"), model["model_id"] if model else "")
        draft = dict(self._state["draft"])
        if changed and model:
            draft.update(size=model["default_size"], quality=model["default_quality"], n=model["default_n"])
        if draft["size"] not in caps["sizes"] and not (caps["custom_size"] and valid_dimensions(draft["size"])):
            draft["size"] = caps["sizes"][0]
        if draft["quality"] not in caps["qualities"]:
            draft["quality"] = caps["qualities"][0]
        if safe_int(draft["n"], 1) not in caps["counts"]:
            draft["n"] = caps["counts"][0]
        else:
            draft["n"] = safe_int(draft["n"], 1)
        self.update(modelId=model["id"] if model else "", caps=caps, draft=draft)

    @Slot(str, "QVariant")
    def setDraft(self, key, value):
        if key in self._state["draft"]:
            draft = dict(self._state["draft"])
            draft[key] = value
            self.update(draft=draft)

    def task_from_draft(self, prompt=None):
        source = next((s for s in self._sources if s["id"] == self._state["sourceId"]), None)
        model = next((m for m in self._models if m["id"] == self._state["modelId"]), None)
        draft = self._state["draft"]
        if not source or not model:
            raise ValueError("请先添加来源，并至少启用一个模型。")
        if (
            not source.get("api_key_encrypted")
            and source["auth_preset"] != "none"
            and not parse_headers(source.get("custom_headers"))
        ):
            raise ValueError("这个来源还没有密钥。请在「来源」中填写后保存。")
        text = (prompt if prompt is not None else draft["prompt"]).strip()
        if not text:
            raise ValueError("先写下你想生成的画面。")
        if model["model_id"] in RETIRED_MODELS and QUrl(source["api_base_url"]).host() == "api.openai.com":
            raise ValueError("这个官方模型已退役，请选择 GPT Image 模型。")
        caps = self._state["caps"]
        if caps["custom_size"] and not valid_dimensions(draft["size"]):
            raise ValueError("尺寸请填写正整数宽高，例如 1280x768。")
        params = {"size": draft["size"], "quality": draft["quality"], "n": int(draft["n"])}
        params["size"] = str(params["size"]).replace("×", "x").lower()
        if caps["seed"] and str(draft["seed"]).strip():
            params["seed"] = int(draft["seed"])
        if caps["format"]:
            params["output_format"] = draft["output_format"]
            if draft["transparent"]:
                if draft["output_format"] == "jpeg":
                    raise ValueError("透明背景请选择 PNG 或 WebP。")
                params["background"] = "transparent"
        return GenerationTask(
            platform_id=adapter_id(source["interface_type"]),
            source_id=source["id"],
            model_config_id=model["id"],
            prompt=text,
            params=params,
            negative_prompt=draft["negative_prompt"] if caps["negative"] else "",
            reference_image_path=draft["reference"] if caps["reference"] else None,
        )

    @Slot()
    def generate(self):
        try:
            task = self.task_from_draft()
            self.queue.add_task(task)
            self.refresh_tasks()
            self.message.emit("已加入队列，可以继续编辑下一张。", False)
        except (ValueError, TypeError) as error:
            self.message.emit(str(error), True)

    @Slot(str)
    def cancelTask(self, task_id):
        self.queue.cancel_task(task_id)
        self.refresh_tasks()

    def refresh_tasks(self):
        tasks = self.queue.get_task_snapshots(100)
        items = []
        for task in tasks:
            item = dict(task)
            item.pop("id", None)
            item["params"] = {k: v for k, v in item["params"].items() if not k.startswith("_")}
            items.append(item)
        self.update(tasks=items, activeCount=sum(t["status"] in ("WAITING", "PENDING", "GENERATING") for t in items))

    def _drain_events(self):
        events = self.queue.drain_status_events()
        if events:
            self.refresh_tasks()
            if any(event in ("completed", "failed") for _, event in events):
                self.launch(self.load_gallery())
            for task, event in events:
                if task.params.get("_persistence_error"):
                    self.message.emit("图片已处理，但历史记录保存失败：" + str(task.params["_persistence_error"]), True)
                elif event == "failed":
                    self.message.emit(task.error or "生成失败，请在作品详情查看诊断。", True)
        if self.chains and self.chains.drain_status_events():
            self.refresh_chains()

    @Slot()
    def chooseReference(self):
        path, _ = QFileDialog.getOpenFileName(None, "选择参考图", "", "图片 (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.setDraft("reference", path)

    @Slot(str)
    def addPreset(self, preset_id):
        async def add():
            assert self.db
            source, models = make_preset(preset_id, "src_" + uuid4().hex)
            async with self.db.transaction():
                await self.db.save_source(source)
                for model in models:
                    await self.db.save_source_model(model)
            await self.reload_sources()
            return source["id"]

        def added(source_id):
            self.update(editSourceId=source_id)
            self.message.emit("来源已添加，请填写密钥后保存。", False)

        self.launch(add(), added, busy=True)

    @Slot("QVariantMap", "QVariantList", str)
    def saveSource(self, source, models, key):
        async def save():
            assert self.db
            if not source.get("name", "").strip():
                raise ValueError("请输入来源名称。")
            url = QUrl(source.get("api_base_url", ""))
            if url.scheme() not in ("https", "http") or not url.host():
                raise ValueError("请输入完整的 HTTP 或 HTTPS 地址。")
            raw_headers = source.get("custom_headers") or "{}"
            try:
                decoded = json.loads(raw_headers) if isinstance(raw_headers, str) else raw_headers
            except json.JSONDecodeError as error:
                raise ValueError("自定义请求头不是有效的 JSON 对象。") from error
            if not isinstance(decoded, dict) or any(not isinstance(value, str) for value in decoded.values()):
                raise ValueError("请求头需为 JSON 对象，键和值都使用字符串。")
            headers = parse_headers(decoded)
            saved = {k: v for k, v in source.items() if k != "has_key"}
            saved["custom_headers"] = json.dumps(headers)
            if key.strip():
                saved["api_key_encrypted"] = encryption.encrypt(key.strip())
            existing = {m["id"] for m in await self.db.get_source_models(source["id"])}
            keep = set()
            async with self.db.transaction():
                await self.db.save_source(saved)
                for i, item in enumerate(models):
                    model_id = item.get("model_id", "").strip()
                    if not model_id:
                        raise ValueError("模型 ID 不能为空；不需要的行请先移除。")
                    caps = model_capabilities(source["interface_type"], model_id)
                    model = dict(
                        item,
                        id=item.get("id") or "mdl_" + uuid4().hex,
                        source_id=source["id"],
                        display_name=item.get("display_name") or model_id,
                        model_id=model_id,
                        sort_order=i,
                        default_size=item.get("default_size") or caps["sizes"][0],
                        default_quality=item.get("default_quality") or caps["qualities"][0],
                        default_n=item.get("default_n", 1),
                        is_active=item.get("is_active", 1),
                        reference_image_enabled=caps["reference"],
                    )
                    await self.db.save_source_model(model)
                    keep.add(model["id"])
                for removed in existing - keep:
                    await self.db.delete_source_model(removed)
            await self.reload_sources()

        self.launch(save(), lambda _: self.message.emit("来源与模型已保存。", False), busy=True)

    @Slot(str)
    def deleteSource(self, source_id):
        async def delete():
            assert self.db
            async with self.db.transaction():
                await self.db.delete_source(source_id)
            await self.reload_sources()

        self.launch(delete(), busy=True)

    async def reload_prompts(self):
        assert self.db
        self.update(prompts=await self.db.get_prompt_templates())

    @Slot(str, str)
    def savePrompt(self, name, category):
        async def save():
            assert self.db
            draft = self._state["draft"]
            if not name.strip() or not draft["prompt"].strip():
                raise ValueError("模板需要名称和提示词，请先在创作页填写画面。")
            await self.db.save_prompt_template(
                {
                    "name": name.strip(),
                    "prompt": draft["prompt"],
                    "negative_prompt": draft["negative_prompt"],
                    "category": category,
                    "source_id": self._state["sourceId"],
                    "model_config_id": self._state["modelId"],
                    "params": {k: v for k, v in draft.items() if k not in ("prompt", "reference", "negative_prompt")},
                }
            )
            await self.reload_prompts()

        self.launch(save(), lambda _: self.message.emit("模板已保存，包含当前来源和参数。", False))

    @Slot(int)
    def deletePrompt(self, template_id):
        async def delete():
            assert self.db
            await self.db.delete_prompt_template(template_id)
            await self.reload_prompts()

        self.launch(delete())

    @Slot("QVariantMap")
    def usePrompt(self, template):
        self.selectSource(template.get("source_id", ""))
        self.selectModel(template.get("model_config_id", ""))
        draft = dict(self._state["draft"])
        draft.update(
            prompt=template.get("prompt", ""),
            negative_prompt=template.get("negative_prompt") or "",
            seed="",
            reference="",
            transparent=False,
            output_format="png",
        )
        params = template.get("params") or {}
        for key in draft:
            if key in params and key not in ("prompt", "negative_prompt", "reference"):
                draft[key] = params[key]
        if params.get("background") == "transparent":
            draft["transparent"] = True
        self.update(draft=draft)
        self.selectModel(self._state["modelId"])
        self.navigate.emit("create")

    async def load_gallery(self, append=False):
        assert self.db
        self._gallery_revision += 1
        revision = self._gallery_revision
        self.update(galleryLoading=True)
        try:
            rows, total = await self.db.search_history(
                self._query, self._filter, 60, len(self.gallery.records) if append else 0
            )
            if revision != self._gallery_revision:
                return
            for row in rows:
                row["thumbnailUrl"] = file_url(row.get("thumbnail_path") or row.get("image_path"))
                row["imageUrl"] = file_url(row.get("image_path"))
                row["images"] = [file_url(p) for p in row.get("result_paths", [])]
                row["dateText"] = (row.get("created_at") or "").replace("T", " ")[:16]
                row["modelText"] = next(
                    (m["display_name"] for m in self._models if m["id"] == row.get("model_config_id")),
                    row.get("platform_id") or "",
                )
            self.gallery.append(rows) if append else self.gallery.replace(rows)
            self.update(galleryTotal=total, galleryHasMore=len(self.gallery.records) < total)
            if not append and not self._query and not self._filter:
                self.update(latest=next((row for row in rows if row.get("image_path")), {}))
        finally:
            if revision == self._gallery_revision:
                self.update(galleryLoading=False)

    @Slot(str, str)
    def searchGallery(self, query, status):
        self._query, self._filter = query, status
        self.launch(self.load_gallery())

    @Slot()
    def moreGallery(self):
        if not self._state["galleryLoading"] and self._state["galleryHasMore"]:
            self.launch(self.load_gallery(True))

    @Slot(str)
    def toggleSelection(self, task_id):
        selected = list(self._state["selected"])
        selected.remove(task_id) if task_id in selected else selected.append(task_id)
        self.update(selected=selected)

    @Slot()
    def clearSelection(self):
        self.update(selected=[])

    @Slot("QVariantMap")
    def viewRecord(self, record):
        self.viewerRequested.emit(record)

    @Slot("QVariantMap")
    def reuseRecord(self, record):
        self.usePrompt(record)

    @Slot(str, str)
    def batchAction(self, action, value):
        ids = list(self._state["selected"])
        if not ids:
            return
        path = ""
        if action == "export":
            path, _ = QFileDialog.getSaveFileName(None, "导出作品", "作品.zip", "ZIP (*.zip)")
            if not path:
                return

        async def run():
            assert self.db
            batch = BatchOpsManager(HistoryManager(self.db), self.db, constants.GENERATIONS_DIR)
            if action == "delete":
                result = await batch.delete_records(ids)
            elif action == "category":
                result = await batch.move_records(ids, value)
            elif action == "tags":
                result = await batch.add_tags(ids, [t.strip() for t in value.split(",") if t.strip()])
            else:
                await batch.export_records(ids, path)
                result = None
            if result and result.failed_count:
                raise ValueError("部分操作失败：" + "; ".join(result.errors))
            self.clearSelection()
            await self.load_gallery()

        self.launch(run(), lambda _: self.message.emit("作品操作完成。", False), busy=True)

    def refresh_chains(self):
        if self.chains:
            self.update(chains=self.chains.get_all_chains())

    @Slot(str, str, str)
    def saveChain(self, chain_id, name, prompts):
        async def save():
            assert self.chains
            if not name.strip():
                raise ValueError("请输入流程名称。")
            lines = [line.strip() for line in prompts.splitlines() if line.strip()]
            if not lines:
                raise ValueError("每行填写一个提示词，至少添加一步。")
            existing = self.chains.get_chain(chain_id) if chain_id else None
            if existing and existing["status"] in ("running", "paused"):
                raise ValueError("先停止流程，再修改步骤。")
            tasks = []
            for i, line in enumerate(lines):
                # Creating a workflow requires a model, but does not require a key until it starts.
                if not self._state["modelId"]:
                    raise ValueError("请先在创作页选择来源和模型。")
                tasks.append(
                    {
                        "chain_order": i,
                        "prompt": line,
                        "source_id": self._state["sourceId"],
                        "model_config_id": self._state["modelId"],
                        "params": {k: self._state["draft"][k] for k in ("size", "quality", "n")},
                    }
                )
            await self.chains.create_chain({"id": chain_id, "name": name.strip(), "tasks": tasks, "status": "idle"})
            self.refresh_chains()

        self.launch(save(), lambda _: self.message.emit("流程已保存。", False))

    @Slot(str, str)
    def chainAction(self, chain_id, action):
        if not self.chains:
            return
        if action == "start":
            chain = self.chains.get_chain(chain_id)
            for task in (chain or {}).get("tasks", []):
                source = next((s for s in self._sources if s["id"] == task["source_id"]), {})
                if not source.get("is_active") or not any(
                    m["id"] == task["model_config_id"] and m["source_id"] == source.get("id") and m["is_active"]
                    for m in self._models
                ):
                    self.message.emit("流程的来源或模型已停用，请先编辑流程。", True)
                    return
                if not (
                    source.get("api_key_encrypted")
                    or source.get("auth_preset") == "none"
                    or parse_headers(source.get("custom_headers"))
                ):
                    self.message.emit("流程的来源还没有配置密钥，请先在「来源」保存配置。", True)
                    return
            self.chains.start_chain_background(chain_id)
            self.refresh_chains()
        elif action in ("pause", "stop"):
            operation = self.chains.pause_chain(chain_id) if action == "pause" else self.chains.stop_chain(chain_id)
            self.launch(operation, lambda _: self.refresh_chains())
        elif action == "delete":
            self.launch(self.chains.delete_chain_async(chain_id), lambda _: self.refresh_chains(), busy=True)

    @Slot(bool, bool, int)
    def savePreferences(self, dark, reduced, concurrent):
        async def save():
            assert self.db
            concurrent_limit = max(1, min(4, concurrent))
            self.queue.max_concurrent = concurrent_limit
            self.update(dark=dark, reducedMotion=reduced, concurrent=concurrent_limit)
            async with self.db.transaction():
                await self.db.set_pref("theme", "dark" if dark else "light")
                await self.db.set_pref("reduced_motion", "true" if reduced else "false")
                await self.db.set_pref("concurrent", str(concurrent_limit))

        self.launch(save())

    @Slot(str, str, bool)
    def backup(self, action, password, include_keys):
        if action == "import" and (
            self._state["activeCount"] or any(c["status"] in ("running", "paused") for c in self._state["chains"])
        ):
            self.message.emit("请先完成或停止当前任务和流程，再导入备份。", True)
            return
        if include_keys and len(password) < 8:
            self.message.emit("包含密钥时，备份密码至少需要 8 位。", True)
            return
        if action == "export":
            path, _ = QFileDialog.getSaveFileName(None, "备份工作台", "WHai.imbackup", "工作台备份 (*.imbackup)")
        else:
            path, _ = QFileDialog.getOpenFileName(None, "导入工作台备份", "", "工作台备份 (*.imbackup)")
        if not path:
            return

        async def run():
            assert self.db
            manager = MigrationManager(self.db, HistoryManager(self.db), PromptManager(self.db))
            if action == "export":
                await manager.export(path, ExportOptions(include_keys=include_keys, key_password=password or None))
            else:
                await manager.import_data(path, ImportOptions(include_keys=include_keys, key_password=password or None))
                await self.reload_sources()
                await self.reload_prompts()
                await self.load_gallery()
                if self.chains:
                    await self.chains.load_chains()
                    self.refresh_chains()

        self.launch(
            run(),
            lambda _: self.message.emit(
                "备份已导出。" if action == "export" else "备份已导入，重名配置保留现有内容。", False
            ),
            busy=True,
        )

    @Slot(str)
    def openPath(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @Slot(str)
    def openLink(self, url):
        if QUrl(url).scheme() in ("https", "http"):
            QDesktopServices.openUrl(QUrl(url))

    @Slot(str)
    def copyText(self, text):
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            self.message.emit("已复制。", False)

    @Slot(str)
    def saveImage(self, path):
        original = Path(path)
        suffix = original.suffix or ".png"
        target, _ = QFileDialog.getSaveFileName(
            None, "图片另存为", original.name, f"{suffix[1:].upper()} 图片 (*{suffix})"
        )
        if not target:
            return
        destination = Path(target)
        if destination.suffix.lower() != suffix.lower():
            destination = destination.with_suffix(suffix)

        async def save():
            await asyncio.to_thread(shutil.copy2, original, destination)

        self.launch(save(), lambda _: self.message.emit("图片已另存。", False), busy=True)

    @Slot(str)
    def copyImage(self, path):
        async def decode():
            image = await asyncio.to_thread(QImage, path)
            if image.isNull():
                raise ValueError("图片无法读取，请确认本地文件仍然存在。")
            return image

        def copied(image):
            clipboard = QGuiApplication.clipboard()
            if clipboard:
                clipboard.setImage(image)
                self.message.emit("图片已复制。", False)

        self.launch(decode(), copied)

    async def shutdown(self):
        self._timer.stop()
        if self.db:
            await self.db.set_pref("last_source", self._state["sourceId"])
            await self.db.set_pref("last_model", self._state["modelId"])
        if self.chains:
            for chain in self.chains.get_all_chains():
                await self.chains.stop_chain(chain["id"])
            threads = list(self.chains._background_threads.values())
            for thread in threads:
                if thread.is_alive():
                    await asyncio.to_thread(thread.join, 2)
