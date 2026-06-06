from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSplitter, QLabel,
    QGraphicsDropShadowEffect, QApplication
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor

import os
from collections import deque

from src.widgets.prompt_panel import PromptPanel
from src.widgets.generation_panel import GenerationPanel
from src.widgets.history_panel import HistoryPanel
from src.widgets.settings_dialog import SettingsDialog
from src.widgets.image_viewer import ImageViewer
from src.widgets.theme import COLORS, SPACING, button_style
from src.widgets.task_chain_editor import TaskChainEditor
from src.managers import QueueManager, PromptManager, HistoryManager
from src.managers.task_chain_manager import TaskChainManager
from src.adapters import get_all_adapters
from src.config.event_loop import run_async


class MainWindow(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.queue_manager = QueueManager.get_instance()
        self.prompt_manager = PromptManager.get_instance()
        self.history_manager = HistoryManager.get_instance()
        self.task_chain_manager = (
            TaskChainManager.get_instance(self.db, self.queue_manager)
            or TaskChainManager(self.db, self.queue_manager)
        )
        self._setup_ui()
        self._connect_signals()

        # Cache for platform config polling to reduce DB queries (Task B3)
        self._cached_sources = []
        self._cached_models = {}
        self._platform_status_dirty = True

        # Loading overlay shown during initial data load
        self.loading_overlay = QLabel("正在加载数据...", self)
        self.loading_overlay.setAlignment(Qt.AlignCenter)
        self.loading_overlay.setStyleSheet(f"""
            QLabel {{
                background: rgba(247, 239, 226, 0.92);
                color: {COLORS['muted']};
                font-size: 16px;
                font-weight: 600;
            }}
        """)
        self.loading_overlay.setVisible(True)
        self.loading_overlay.setGeometry(self.rect())
        QTimer.singleShot(50, self._load_data)
        self._start_queue_polling()

    def _setup_ui(self):
        self.setWindowTitle("imageMaker - 图片生成工具")
        self.setMinimumSize(1200, 700)
        # 检测屏幕尺寸，仅在超大分辨率使用纯色避免重绘延迟
        screen = QApplication.primaryScreen()
        if screen and screen.size().width() > 2560:
            bg = COLORS['background']
        else:
            bg = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {COLORS['sky_soft']}, stop:0.5 {COLORS['panel']}, stop:1 {COLORS['primary_soft']})"
        self.setStyleSheet(f"QWidget {{ background: {bg}; }}")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(8)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self.chain_editor_btn = QPushButton("任务链")
        self.chain_editor_btn.setMinimumSize(72, 34)
        self.chain_editor_btn.setStyleSheet(button_style("ghost"))
        self.chain_editor_btn.setToolTip("打开任务链编辑器（多步骤生成流水线）")
        self.chain_editor_btn.clicked.connect(self._open_task_chain_editor)
        toolbar_layout.addWidget(self.chain_editor_btn)

        toolbar_layout.addStretch()

        self.settings_btn = QPushButton("设置")
        self.settings_btn.setMinimumSize(72, 34)
        self.settings_btn.setStyleSheet(button_style("secondary"))
        self.settings_btn.clicked.connect(self._open_settings)
        toolbar_layout.addWidget(self.settings_btn)
        main_layout.addLayout(toolbar_layout)

        self.prompt_panel = PromptPanel(self.prompt_manager)
        self.prompt_panel.setMinimumWidth(180)

        self.generation_panel = GenerationPanel(self.queue_manager)

        self.history_panel = HistoryPanel(self.history_manager)
        self.history_panel.setMinimumWidth(300)
        self.history_panel.setMaximumWidth(460)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.addWidget(self.prompt_panel)
        self.main_splitter.addWidget(self.generation_panel)
        self.main_splitter.addWidget(self.history_panel)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 3)
        self.main_splitter.setStretchFactor(2, 1)
        self.main_splitter.setSizes([220, 700, 340])
        self.main_splitter.setCollapsible(0, True)
        main_layout.addWidget(self.main_splitter, 1)

        for panel in [self.prompt_panel, self.generation_panel, self.history_panel]:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(8)
            shadow.setOffset(0, 2)
            shadow.setColor(QColor(0, 0, 0, 18))
            panel.setGraphicsEffect(shadow)

        # Bottom status bar
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(*(SPACING['xs'],)*4)

        self.status_source_label = QLabel("")
        self.status_source_label.setStyleSheet(
            f"color: {COLORS['muted']}; font-size: 11px;"
        )
        status_layout.addWidget(self.status_source_label)

        status_layout.addStretch()

        self.status_queue_label = QLabel("")
        self.status_queue_label.setStyleSheet(
            f"color: {COLORS['muted']}; font-size: 11px;"
        )
        status_layout.addWidget(self.status_queue_label)

        main_layout.addLayout(status_layout)

    def _connect_signals(self):
        self.generation_panel.generate_signal.connect(self._on_generate)
        self.generation_panel.add_to_queue_signal.connect(self._on_add_to_queue)
        self.generation_panel.save_template_signal.connect(self._on_save_template)
        self.generation_panel.open_settings_requested.connect(self._open_settings)
        self.prompt_panel.template_used.connect(self.generation_panel.apply_template)
        self.prompt_panel.template_selected.connect(self.generation_panel.apply_template)
        self.prompt_panel.template_deleted.connect(self._on_delete_template)
        self.history_panel.image_selected.connect(self._on_image_selected)
        self.history_panel.reuse_requested.connect(self.generation_panel.apply_template)
        self.history_panel.delete_requested.connect(self._on_delete_history_record)
        self.queue_manager.set_status_callback(self._on_queue_status_changed)
        self.task_chain_manager.set_status_callback(self._on_task_chain_status_changed)
        self.prompt_panel.collapse_changed.connect(self._on_prompt_panel_collapse_changed)


    def _on_prompt_panel_collapse_changed(self, collapsed: bool):
        if collapsed:
            self.prompt_panel.setMaximumWidth(44)
            self.prompt_panel.setMinimumWidth(44)
        else:
            self.prompt_panel.setMaximumWidth(260)
            self.prompt_panel.setMinimumWidth(180)


    def _start_queue_polling(self):
        self.queue_timer = QTimer(self)
        self.queue_timer.setInterval(250)
        self.queue_timer.timeout.connect(self._drain_queue_events)
        self.queue_timer.start()

    def _drain_queue_events(self):
        events = self.queue_manager.drain_status_events()
        for task, status in events:
            self._on_queue_status_changed(task, status)
        for chain in self.task_chain_manager.drain_status_events():
            self._on_task_chain_status_changed(chain)
        if events:
            self._refresh_platform_config_statuses()
            self._update_status_bar()

    def _update_status_bar(self):
        source_text = ""
        queue_text = ""

        try:
            if hasattr(self.generation_panel, "sources") and self.generation_panel.sources:
                current_source_id = getattr(self.generation_panel, "current_source_id", "")
                current_source = next(
                    (
                        source
                        for source in self.generation_panel.sources
                        if source.get("id") == current_source_id
                    ),
                    None,
                )
                active = [source for source in self.generation_panel.sources if source.get("is_active")]
                display_source = current_source or (active[0] if active else None)
                if display_source:
                    name = display_source.get("name", "未知")
                    model_count = len(self.generation_panel.models_by_source.get(
                        display_source.get("id", ""), []
                    ))
                    source_text = f"✓ 来源: {name} · {model_count} 个模型"
                else:
                    source_text = "⚠ 未配置来源 — 请前往设置"
            else:
                source_text = "⚠ 未配置来源 — 请前往设置"

            info = self.queue_manager.get_queue_info()
            queue_text = (
                f"队列 {info['waiting']} · "
                f"生成中 {info['generating']} · "
                f"已完成 {info['completed'] + info['failed']}"
            )
        except Exception:
            pass

        self.status_source_label.setText(source_text)
        self.status_queue_label.setText(queue_text)

    def _load_data(self):
        run_async(self._async_load_data_with_history())

    async def _async_load_data_with_history(self):
        """合并数据加载和历史加载为单个 async 调用，减少主线程阻塞。"""
        await self._async_load_data()
        # load_history 的数据库查询部分合并到此处，避免嵌套 run_until_complete
        if self.history_panel.history_manager:
            try:
                records = await self.history_panel.history_manager.get_history(100)
                self.history_panel.history = deque(records)
            except Exception:
                self.history_panel.history = deque()
        self.history_panel._update_grid()
        self._refresh_diagnostic_history()

    async def _async_load_data(self):
        """异步加载所有数据，不阻塞主线程"""
        try:
            # 获取来源数据
            sources = []
            models_by_source = {}
            if self.db:
                await self.task_chain_manager.load_chains()
                sources = await self.db.get_sources(active_only=True)
                for source in sources:
                    models = await self.db.get_source_models(source["id"], active_only=True)
                    models_by_source[source["id"]] = models

            # 主线程更新 UI
            await self.prompt_panel.load_templates()
            self.generation_panel.refresh_queue()
            self.generation_panel.set_sources(sources, models_by_source)
            self._update_status_bar()

            # 检查平台配置状态
            statuses = {"openai": any(models_by_source.get(s["id"]) for s in sources)}
            messages = {}
            if not statuses["openai"]:
                messages["openai"] = "请先在设置中新增来源和模型，再开始生成。"
            self.generation_panel.set_platform_config_statuses(statuses, messages)
            self.loading_overlay.setVisible(False)
        except Exception as e:
            self.loading_overlay.setText(f"加载失败: {e}")
            self.loading_overlay.setStyleSheet(f"""
                QLabel {{
                    background: rgba(247, 239, 226, 0.92);
                    color: {COLORS['danger']};
                    font-size: 16px;
                    font-weight: 600;
                }}
            """)
            print(f"Failed to load data: {e}")


    def _refresh_platform_config_statuses(self):
        statuses = {"openai": False}
        messages = {}
        if not self.db:
            self.generation_panel.set_platform_config_statuses(statuses)
            return
        try:
            # Only re-query when config has changed (Task B3: cache with dirty flag)
            if self._platform_status_dirty:
                if hasattr(self.db, "migrate_legacy_openai_config"):
                    run_async(self.db.migrate_legacy_openai_config())
                sources = run_async(self.db.get_sources(active_only=True)) if hasattr(self.db, "get_sources") else []
                models_by_source = {}
                for source in sources:
                    models = run_async(self.db.get_source_models(source["id"], active_only=True))
                    models_by_source[source["id"]] = models
                self._cached_sources = sources
                self._cached_models = models_by_source
                self._platform_status_dirty = False
            else:
                sources = self._cached_sources
                models_by_source = self._cached_models

            self.generation_panel.set_sources(sources, models_by_source)
            statuses["openai"] = any(models_by_source.get(s.get("id")) for s in sources)
            if not statuses["openai"]:
                messages["openai"] = "请先在设置中新增来源和模型，再开始生成。"
        except Exception:
            pass
        self.generation_panel.set_platform_config_statuses(statuses, messages)

    def _submit_tasks(self, task_data: dict):
        from src.models.task import GenerationTask
        params = dict(task_data.get("params", {}))
        count = max(1, int(params.pop("n", 1)))
        for _ in range(count):
            self.queue_manager.add_task(GenerationTask(
                platform_id=task_data.get("platform_id", "openai"),
                source_id=task_data.get("source_id", ""),
                model_config_id=task_data.get("model_config_id", ""),
                prompt=task_data["prompt"],
                negative_prompt=task_data.get("negative_prompt", ""),
                params=dict(params),
                reference_image_path=task_data.get("reference_image_path"),
            ))
        self.generation_panel.refresh_queue()
        self._refresh_platform_config_statuses()

    def _on_generate(self, task_data: dict):
        self._submit_tasks(task_data)

    def _on_add_to_queue(self, task_data: dict):
        self._submit_tasks(task_data)

    def _on_save_template(self, template: dict):
        run_async(self.prompt_manager.save_template(template))
        run_async(self.prompt_panel.load_templates())

    def _on_delete_template(self, template_id: int):
        run_async(self.prompt_manager.delete_template(template_id))
        run_async(self.prompt_panel.load_templates())

    def _on_queue_status_changed(self, task, status):
        self.generation_panel.refresh_queue()
        if status == "added":
            self.generation_panel.show_status("\u4efb\u52a1\u5df2\u52a0\u5165\u961f\u5217\u3002", "success")
        elif status == "pending":
            self.generation_panel.show_status("\u4efb\u52a1\u51c6\u5907\u4e2d\uff0c\u6b63\u5728\u8bfb\u53d6\u5e73\u53f0\u914d\u7f6e\u3002", "info")
        elif status == "generating":
            self.generation_panel.show_status("\u6b63\u5728\u751f\u6210\u56fe\u7247\u4e2d\u2026\u8bf7\u7a0d\u5019\u3002", "info")
        elif status == "failed":
            error_display = self._classify_error(task.error)
            self.generation_panel.show_status(error_display, "error")
            self.generation_panel.update_diagnostic(task.params.get("_diagnostic", {}) if isinstance(task.params, dict) else {}, expand=True)
            self._refresh_diagnostic_history()
        elif status == "completed":
            self.generation_panel.show_status("\u751f\u6210\u5b8c\u6210\uff0c\u5df2\u52a0\u5165\u5386\u53f2\u753b\u5eca\u3002", "success")
            self.generation_panel.update_diagnostic(task.params.get("_diagnostic", {}) if isinstance(task.params, dict) else {})
            if task.result_paths:
                from src.config import constants
                name = os.path.basename(task.result_paths[0])
                thumb_name = f"thumb_{os.path.splitext(name)[0]}.jpg"
                self.history_panel.add_record({
                    "task_id": str(task.id),
                    "platform_id": task.platform_id,
                    "source_id": task.source_id,
                    "model_config_id": task.model_config_id,
                    "prompt": task.prompt,
                    "image_path": task.result_paths[0],
                    "thumbnail_path": os.path.join(constants.THUMBNAILS_DIR, thumb_name),
                    "status": task.status,
                    "negative_prompt": task.negative_prompt,
                    "params": task.params,
                    "diagnostic": task.params.get("_diagnostic", {}) if isinstance(task.params, dict) else {},
                })

    def _on_delete_history_record(self, record: dict):
        task_id = record.get("task_id")
        if not task_id:
            return
        run_async(self.history_manager.delete_record(task_id))
        self.history_panel.history = [item for item in self.history_panel.history if item.get("task_id") != task_id]
        self.history_panel._update_grid()

    def _refresh_diagnostic_history(self):
        if not hasattr(self, 'history_panel') or not self.history_panel:
            return
        records = [
            r for r in self.history_panel.history
            if r.get("error") or r.get("diagnostic")
        ]
        self.generation_panel.show_diagnostic_history(list(records)[:8])

    def _on_image_selected(self, record: dict):
        viewer = ImageViewer(record, self)
        viewer.exec()

    def _open_settings(self):
        dialog = SettingsDialog(self.db, self)
        if dialog.exec():
            self._platform_status_dirty = True
            self._refresh_platform_config_statuses()
            self._update_status_bar()

    def _open_task_chain_editor(self):
        editor = TaskChainEditor(
            self.task_chain_manager,
            self.queue_manager,
            parent=self,
            default_source_id=self.generation_panel.current_source_id,
            default_model_config_id=self.generation_panel.current_model_id,
        )
        editor.chain_saved.connect(self._on_chain_saved)
        editor.setWindowFlags(Qt.Dialog)
        editor.setWindowModality(Qt.NonModal)
        editor.resize(800, 600)
        editor.show()
        # 保存引用防止被垃圾回收
        if not hasattr(self, '_open_editors'):
            self._open_editors = []
        self._open_editors.append(editor)

    def _on_chain_saved(self, chain_data: dict):
        """Persist the chain via the task chain manager."""
        run_async(self.task_chain_manager.create_chain(chain_data))

    def _on_chain_started(self, chain_id: str):
        """Start executing a task chain."""
        return self.task_chain_manager.start_chain_background(chain_id)

    def _on_task_chain_status_changed(self, chain):
        for editor in getattr(self, "_open_editors", []):
            if editor and not editor.isHidden():
                editor._refresh_chain_list(getattr(chain, "id", None))

    def _classify_error(self, error_msg: str | None) -> str:
        """根据错误信息特征返回更具体的用户提示。"""
        if not error_msg:
            return "生成失败：请检查配置或网络连接"
        msg_lower = error_msg.lower()
        if any(kw in msg_lower for kw in ("timeout", "timed out", "connect", "refused")):
            return f"网络连接失败：{error_msg}"
        if any(kw in msg_lower for kw in ("401", "403", "unauthorized", "forbidden")):
            return f"鉴权失败，请检查 API Key：{error_msg}"
        if any(kw in msg_lower for kw in ("429", "rate limit", "quota")):
            return f"请求频率超限，请稍后重试：{error_msg}"
        if any(kw in msg_lower for kw in ("500", "502", "503", "server error")):
            return f"服务器错误，请稍后重试：{error_msg}"
        if any(kw in msg_lower for kw in ("resolution", "size", "dimension")):
            return f"图片尺寸参数无效：{error_msg}"
        return f"生成失败：{error_msg}"

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.setGeometry(self.rect())
