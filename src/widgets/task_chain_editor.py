"""TaskChainEditor widget for creating and editing task chains."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.widgets.theme import app_font, apply_card_style, button_style, input_style, label_style


class TaskChainEditor(QWidget):
    """UI widget for creating and editing task chains."""

    chain_saved = Signal(dict)
    chain_started = Signal(str)

    def __init__(
        self,
        task_chain_manager,
        queue_manager,
        parent=None,
        default_source_id: str = "",
        default_model_config_id: str = "",
    ):
        super().__init__(parent)
        self.task_chain_manager = task_chain_manager
        self.queue_manager = queue_manager
        self.default_source_id = default_source_id
        self.default_model_config_id = default_model_config_id
        self._current_chain_id = None
        self._task_widgets = []
        self._setup_ui()
        self._refresh_chain_list()
        self._update_action_state()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        left_panel = QFrame()
        apply_card_style(left_panel)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        title = QLabel("任务链")
        title.setFont(app_font(14, QFont.Bold))
        title.setStyleSheet(label_style("section"))
        left_layout.addWidget(title)

        self.chain_list = QListWidget()
        self.chain_list.itemClicked.connect(self._on_chain_selected)
        left_layout.addWidget(self.chain_list)

        btn_layout = QHBoxLayout()
        self.new_btn = QPushButton("+ 新建")
        self.new_btn.setStyleSheet(button_style("primary"))
        self.new_btn.clicked.connect(self._on_new_chain)
        btn_layout.addWidget(self.new_btn)

        self.delete_chain_btn = QPushButton("删除")
        self.delete_chain_btn.setStyleSheet(button_style("secondary"))
        self.delete_chain_btn.clicked.connect(self._on_delete_chain)
        btn_layout.addWidget(self.delete_chain_btn)
        left_layout.addLayout(btn_layout)

        main_layout.addWidget(left_panel, 1)

        right_panel = QFrame()
        apply_card_style(right_panel)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        self.chain_name_input = QLineEdit()
        self.chain_name_input.setPlaceholderText("任务链名称")
        self.chain_name_input.setStyleSheet(input_style())
        right_layout.addWidget(self.chain_name_input)

        self.context_hint_label = QLabel()
        self.context_hint_label.setWordWrap(True)
        self.context_hint_label.setStyleSheet(label_style("muted"))
        right_layout.addWidget(self.context_hint_label)
        self._set_context_hint(self._default_context_text())

        self.task_scroll = QScrollArea()
        self.task_scroll.setWidgetResizable(True)
        self.task_scroll.setStyleSheet("border: none; background: transparent;")
        self.task_container = QWidget()
        self.task_container.setStyleSheet("background: transparent;")
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(8)
        self.task_layout.addStretch()
        self.task_scroll.setWidget(self.task_container)
        right_layout.addWidget(self.task_scroll, 1)

        self.add_task_btn = QPushButton("+ 添加任务")
        self.add_task_btn.setStyleSheet(button_style("secondary"))
        self.add_task_btn.clicked.connect(self._on_add_task)
        right_layout.addWidget(self.add_task_btn)

        action_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存任务链")
        self.save_btn.setStyleSheet(button_style("primary"))
        self.save_btn.clicked.connect(self._on_save_chain)
        action_layout.addWidget(self.save_btn)

        self.start_btn = QPushButton("启动")
        self.start_btn.setStyleSheet(button_style("success"))
        self.start_btn.clicked.connect(self._on_start_chain)
        action_layout.addWidget(self.start_btn)
        right_layout.addLayout(action_layout)

        main_layout.addWidget(right_panel, 3)

    def _default_context_text(self) -> str:
        if self.default_source_id and self.default_model_config_id:
            return "新任务会使用打开编辑器时创作工作台选中的来源和模型。"
        return "请先在创作工作台选择来源和模型，再新建可执行任务链。"

    def _set_context_hint(self, text: str):
        self.context_hint_label.setText(text)

    def _refresh_chain_list(self, select_chain_id: str | None = None):
        self.chain_list.clear()
        chains = self.task_chain_manager.get_all_chains()
        for chain in chains:
            item = QListWidgetItem(chain.get("name", "未命名"))
            item.setData(Qt.UserRole, chain.get("id"))
            self.chain_list.addItem(item)
        if select_chain_id:
            self._select_chain_item(select_chain_id)

    def _select_chain_item(self, chain_id: str):
        for row in range(self.chain_list.count()):
            item = self.chain_list.item(row)
            if item.data(Qt.UserRole) == chain_id:
                self.chain_list.setCurrentItem(item)
                return

    def _on_new_chain(self):
        self._current_chain_id = None
        self.chain_name_input.clear()
        self._clear_task_widgets()
        self._add_task_widget()
        self._set_context_hint(self._default_context_text())
        self._update_action_state()

    def _on_delete_chain(self):
        if not self._current_chain_id:
            self._set_context_hint("请先选择要删除的任务链。")
            return
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定删除当前任务链吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.task_chain_manager.delete_chain(self._current_chain_id)
        self._current_chain_id = None
        self.chain_name_input.clear()
        self._clear_task_widgets()
        self._refresh_chain_list()
        self._set_context_hint("任务链已删除。")
        self._update_action_state()

    def _on_chain_selected(self, item):
        chain_id = item.data(Qt.UserRole)
        chain = self.task_chain_manager.get_chain(chain_id)
        if not chain:
            return
        self._current_chain_id = chain_id
        self.chain_name_input.setText(chain.get("name", ""))
        self._clear_task_widgets()
        tasks = chain.get("tasks", [])
        if not tasks:
            self._add_task_widget()
        else:
            for task in tasks:
                self._add_task_widget(task)
        self._set_context_hint(f"已选择：{chain.get('name', '未命名')}")
        self._update_action_state()

    def _on_add_task(self):
        self._add_task_widget()
        self.task_scroll.verticalScrollBar().setValue(
            self.task_scroll.verticalScrollBar().maximum()
        )

    def _add_task_widget(self, task_data=None):
        task_widget = TaskItemWidget(
            task_data,
            default_source_id=self.default_source_id,
            default_model_config_id=self.default_model_config_id,
        )
        task_widget.remove_requested.connect(lambda: self._on_remove_task(task_widget))
        self._task_widgets.append(task_widget)
        self.task_layout.insertWidget(self.task_layout.count() - 1, task_widget)

    def _on_remove_task(self, task_widget):
        if task_widget in self._task_widgets:
            self._task_widgets.remove(task_widget)
            task_widget.deleteLater()

    def _clear_task_widgets(self):
        for widget in self._task_widgets:
            widget.deleteLater()
        self._task_widgets.clear()

    def _on_save_chain(self):
        tasks = self._collect_tasks()
        if not tasks:
            self._set_context_hint("请至少填写一个任务提示词后再保存。")
            return
        if not self._current_chain_id:
            self._current_chain_id = str(uuid4())
        name = self.chain_name_input.text().strip() or "未命名任务链"
        chain_data = {
            "id": self._current_chain_id,
            "name": name,
            "tasks": tasks,
        }
        self.chain_saved.emit(chain_data)
        self._refresh_chain_list(self._current_chain_id)
        self._set_context_hint(f"已保存：{name}")
        self._update_action_state()

    def _on_start_chain(self):
        if not self._current_chain_id:
            self._set_context_hint("请先选择要启动的任务链。")
            return
        started = self.task_chain_manager.start_chain_background(self._current_chain_id)
        if not started:
            self._set_context_hint("任务链启动失败，请重新选择任务链后再试。")
            return
        self.chain_started.emit(self._current_chain_id)
        self._set_context_hint("任务链已提交后台执行。")

    def _collect_tasks(self):
        tasks = []
        for widget in self._task_widgets:
            task_data = widget.get_data()
            if task_data:
                tasks.append(task_data)
        return tasks

    def _update_action_state(self):
        selected = self._current_chain_id is not None
        self.start_btn.setEnabled(selected)
        self.delete_chain_btn.setEnabled(selected)


class TaskItemWidget(QFrame):
    """Individual task editing widget."""

    remove_requested = Signal()

    def __init__(
        self,
        task_data=None,
        parent=None,
        default_source_id: str = "",
        default_model_config_id: str = "",
    ):
        super().__init__(parent)
        self.task_data = task_data or {}
        self.source_id = default_source_id
        self.model_config_id = default_model_config_id
        self.params = dict(self.task_data.get("params") or {})
        self._setup_ui()
        if task_data:
            self._populate_from_data(task_data)

    def _setup_ui(self):
        apply_card_style(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        title_label = QLabel("任务")
        title_label.setFont(app_font(12, QFont.Bold))
        title_label.setStyleSheet(label_style("section"))
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        remove_btn = QPushButton("×")
        remove_btn.setStyleSheet(button_style("danger_ghost"))
        remove_btn.setFixedSize(24, 24)
        remove_btn.clicked.connect(lambda: self.remove_requested.emit())
        header_layout.addWidget(remove_btn)
        layout.addLayout(header_layout)

        self.context_label = QLabel(self._context_text())
        self.context_label.setWordWrap(True)
        self.context_label.setStyleSheet(label_style("muted"))
        layout.addWidget(self.context_label)

        type_layout = QHBoxLayout()
        type_label = QLabel("类型:")
        type_label.setFixedWidth(50)
        type_layout.addWidget(type_label)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["prompt", "image_variation", "inpainting", "upscale"])
        self.type_combo.setStyleSheet(input_style())
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("输入提示词...")
        self.prompt_edit.setMinimumHeight(60)
        self.prompt_edit.setStyleSheet(input_style())
        layout.addWidget(self.prompt_edit)

        params_layout = QFormLayout()
        params_layout.setLabelAlignment(Qt.AlignRight)

        self.neg_prompt = QLineEdit()
        self.neg_prompt.setPlaceholderText("反向提示词")
        self.neg_prompt.setStyleSheet(input_style())

        self.steps = QLineEdit()
        self.steps.setPlaceholderText("步数")
        self.steps.setText(str(self.params.get("steps", 30)))
        self.steps.setStyleSheet(input_style())

        self.guidance = QLineEdit()
        self.guidance.setPlaceholderText("引导强度")
        self.guidance.setText(str(self.params.get("guidance", 7.5)))
        self.guidance.setStyleSheet(input_style())

        params_layout.addRow("反向:", self.neg_prompt)
        params_layout.addRow("步数:", self.steps)
        params_layout.addRow("引导:", self.guidance)
        layout.addLayout(params_layout)

    def _context_text(self) -> str:
        if self.source_id and self.model_config_id:
            return "使用当前来源/模型配置执行。"
        return "缺少来源/模型：请从创作工作台选择来源和模型后再新建任务。"

    def _populate_from_data(self, data):
        type_map = {
            "prompt": 0,
            "image_variation": 1,
            "inpainting": 2,
            "upscale": 3,
        }
        task_type = data.get("type", "prompt")
        self.type_combo.setCurrentIndex(type_map.get(task_type, 0))
        self.source_id = data.get("source_id") or self.source_id
        self.model_config_id = data.get("model_config_id") or self.model_config_id
        self.params = dict(data.get("params") or self.params)
        self.prompt_edit.setPlainText(data.get("prompt", ""))
        self.neg_prompt.setText(data.get("negative_prompt", ""))
        self.steps.setText(str(self.params.get("steps", data.get("steps", 30))))
        self.guidance.setText(str(self.params.get("guidance", data.get("guidance", 7.5))))
        self.context_label.setText(self._context_text())

    def get_data(self):
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            return None
        params = dict(self.params)
        params["steps"] = self._int_value(self.steps.text(), 30)
        params["guidance"] = self._float_value(self.guidance.text(), 7.5)
        return {
            "type": self.type_combo.currentText(),
            "source_id": self.source_id,
            "model_config_id": self.model_config_id,
            "prompt": prompt,
            "negative_prompt": self.neg_prompt.text().strip(),
            "params": params,
        }

    def _int_value(self, value: str, default: int) -> int:
        return int(value) if value.strip().isdigit() else default

    def _float_value(self, value: str, default: float) -> float:
        try:
            return float(value)
        except ValueError:
            return default
