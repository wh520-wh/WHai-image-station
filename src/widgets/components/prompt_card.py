from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from src.widgets.theme import COLORS, app_font, apply_card_style, button_style, label_style


class PromptCard(QFrame):
    clicked = Signal(dict)
    use_template = Signal(dict)
    delete_template = Signal(int)

    def __init__(self, template: dict, parent=None):
        super().__init__(parent)
        self.template = template
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        apply_card_style(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_layout = QHBoxLayout()
        self.name_label = QLabel()
        self.name_label.setFont(app_font(12, QFont.Weight.Bold))
        self.name_label.setStyleSheet(label_style("section"))
        title_layout.addWidget(self.name_label)
        title_layout.addStretch()

        self.delete_btn = QPushButton("×")
        self.delete_btn.setFixedSize(24, 24)
        self.delete_btn.setToolTip("删除模板")
        self.delete_btn.setStyleSheet(button_style("danger_ghost") + "QPushButton { padding: 0; font-size: 16px; }")
        self.delete_btn.clicked.connect(lambda: self.delete_template.emit(self.template.get("id", 0)))
        title_layout.addWidget(self.delete_btn)
        layout.addLayout(title_layout)

        self.prompt_preview = QLabel()
        self.prompt_preview.setWordWrap(True)
        self.prompt_preview.setStyleSheet(label_style("muted"))
        self.prompt_preview.setMaximumHeight(44)
        layout.addWidget(self.prompt_preview)

        self.use_btn = QPushButton("使用")
        self.use_btn.setFixedHeight(32)
        self.use_btn.setStyleSheet(button_style("primary"))
        self.use_btn.clicked.connect(lambda: self.use_template.emit(self.template))
        layout.addWidget(self.use_btn)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mousePressEvent = lambda event: self.clicked.emit(self.template)

    def _load_data(self):
        self.name_label.setText(self.template.get("name", "未命名"))
        prompt = self.template.get("prompt", "") or "空模板，可点击后填写 Prompt"
        self.prompt_preview.setText(prompt[:88] + "..." if len(prompt) > 88 else prompt)


class TaskCard(QFrame):
    cancel_signal = Signal(str)
    _task_id: str | None = None

    def __init__(self, task: dict, parent=None):
        super().__init__(parent)
        self.task = dict(task)
        self.setMinimumSize(210, 118)
        self.setProperty("imageMakerTaskCard", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        row = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setFont(app_font(11, QFont.Weight.DemiBold))
        row.addWidget(self.status_label)
        row.addStretch()
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet(button_style("ghost"))
        self.cancel_btn.clicked.connect(
            lambda: self.cancel_signal.emit(str(self.task.get("task_id") or self.task.get("id", "")))
        )
        row.addWidget(self.cancel_btn)
        layout.addLayout(row)
        self.platform_label = QLabel()
        self.platform_label.setStyleSheet(label_style("muted"))
        layout.addWidget(self.platform_label)
        self.prompt_label = QLabel()
        self.prompt_label.setWordWrap(True)
        self.prompt_label.setMinimumHeight(32)
        self.prompt_label.setStyleSheet(label_style("body"))
        layout.addWidget(self.prompt_label)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(f"color: {COLORS['danger']}; font-size: 11px;")
        layout.addWidget(self.error_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ border: none; background: {COLORS['border']}; }} QProgressBar::chunk {{ background: {COLORS['primary']}; }}"
        )
        layout.addWidget(self.progress_bar)
        self.update_task(task)

    def _get_status_color(self, status: str) -> str:
        return {
            "GENERATING": COLORS["info"],
            "COMPLETED": COLORS["success"],
            "FAILED": COLORS["danger"],
            "PENDING": COLORS["warning"],
        }.get(status, COLORS["subtle"])

    def _get_status_text(self, status: str) -> str:
        return {
            "WAITING": "等待中",
            "PENDING": "准备中",
            "GENERATING": "生成中",
            "COMPLETED": "已完成",
            "FAILED": "失败",
            "CANCELLED": "已取消",
        }.get(status, status)

    def update_task(self, task: dict):
        self.task = dict(task)
        status = task.get("status", "WAITING")
        color = self._get_status_color(status)
        self.setStyleSheet(
            f'QFrame[imageMakerTaskCard="true"] {{ background: {COLORS["panel"]}; border: 1px solid {COLORS["border"]}; border-left: 3px solid {color}; border-radius: 8px; }}'
        )
        self.status_label.setText(self._get_status_text(status))
        self.status_label.setStyleSheet(f"color: {color}; background: transparent;")
        self.cancel_btn.setVisible(status == "WAITING")
        self.platform_label.setText(task.get("platform_id", ""))
        prompt = task.get("prompt", "")
        self.prompt_label.setText(prompt[:100] + ("…" if len(prompt) > 100 else ""))
        error = task.get("error") or ""
        self.error_label.setText(error[:160])
        self.error_label.setToolTip(error)
        self.error_label.setVisible(status == "FAILED" and bool(error))
        self.progress_bar.setVisible(status == "GENERATING")

    def update_status(self, status: str):
        self.update_task({**self.task, "status": status})
