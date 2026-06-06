from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont

from src.widgets.theme import COLORS, RADIUS, app_font, apply_card_style, button_style, label_style


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
        self.name_label.setFont(app_font(12, QFont.Bold))
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

        self.setCursor(Qt.PointingHandCursor)
        self.mousePressEvent = lambda event: self.clicked.emit(self.template)

    def _load_data(self):
        self.name_label.setText(self.template.get("name", "未命名"))
        prompt = self.template.get("prompt", "") or "空模板，可点击后填写 Prompt"
        self.prompt_preview.setText(prompt[:88] + "..." if len(prompt) > 88 else prompt)


class TaskCard(QFrame):
    cancel_signal = Signal(str)

    def __init__(self, task: dict, parent=None):
        super().__init__(parent)
        self.task = task
        self._setup_ui()

    def _setup_ui(self):
        status = self.task.get("status", "WAITING")
        color = self._get_status_color(status)
        soft_color = self._get_status_soft_color(status)
        self.setMinimumSize(210, 118)
        self.setProperty("imageMakerTaskCard", True)

        self.setStyleSheet(f"""
            QFrame[imageMakerTaskCard="true"] {{
                background: {soft_color};
                border: 1px solid {color};
                border-radius: 12px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(9)

        status_layout = QHBoxLayout()
        self.status_label = QLabel(self._get_status_text(status))
        self.status_label.setFont(app_font(10, QFont.Bold))
        self.status_label.setStyleSheet(f"color: {color};")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        if status == "WAITING":
            self.cancel_btn = QPushButton("×")
            self.cancel_btn.setFixedSize(20, 20)
            self.cancel_btn.setStyleSheet(button_style("danger_ghost") + "QPushButton { padding: 0; }")
            self.cancel_btn.clicked.connect(lambda: self.cancel_signal.emit(str(self.task.get("id", ""))))
            status_layout.addWidget(self.cancel_btn)
        layout.addLayout(status_layout)

        platform = self.task.get("platform_id", "")
        if platform:
            platform_label = QLabel(platform)
            platform_label.setStyleSheet(f"color: {COLORS['subtle']}; font-size: 10px;")
            platform_label.setMinimumHeight(16)
            layout.addWidget(platform_label)

        prompt = self.task.get("prompt", "")
        self.prompt_label = QLabel(prompt[:60] + "..." if len(prompt) > 60 else prompt)
        self.prompt_label.setWordWrap(True)
        self.prompt_label.setStyleSheet(f"color: {COLORS['muted']}; font-size: 11px;")
        self.prompt_label.setMinimumHeight(32)
        self.prompt_label.setMaximumHeight(46)
        layout.addWidget(self.prompt_label)

        if status == "FAILED" and self.task.get("error"):
            error = self.task.get("error", "")
            error_label = QLabel(error[:52] + "..." if len(error) > 52 else error)
            error_label.setWordWrap(True)
            error_label.setToolTip(error)
            error_label.setStyleSheet(f"color: {COLORS['danger']}; font-size: 10px;")
            error_label.setMaximumHeight(32)
            layout.addWidget(error_label)

        if status == "GENERATING":
            self.progress_bar = QFrame()
            self.progress_bar.setProperty("imageMakerProgressTrack", True)
            self.progress_bar.setFixedHeight(5)
            self.progress_bar.setStyleSheet(f"""
                QFrame[imageMakerProgressTrack="true"] {{
                    background: {COLORS['border']};
                    border: none;
                    border-radius: {RADIUS['compact']}px;
                }}
            """)
            inner = QFrame(self.progress_bar)
            inner.setProperty("imageMakerProgressFill", True)
            inner.setFixedHeight(5)
            inner.setStyleSheet(f"""
                QFrame[imageMakerProgressFill="true"] {{
                    background: {color};
                    border: none;
                    border-radius: {RADIUS['compact']}px;
                }}
            """)
            # Use QPropertyAnimation for indeterminate progress bar width
            self._progress_anim = QPropertyAnimation(inner, b"minimumWidth")
            self._progress_anim.setDuration(1500)
            self._progress_anim.setStartValue(0)
            self._progress_anim.setEndValue(210)
            self._progress_anim.setLoopCount(-1)  # Infinite loop
            self._progress_anim.setEasingCurve(QEasingCurve.InOutSine)
            self._progress_anim.start()
            inner.setMinimumWidth(0)
            inner.setMaximumWidth(210)
            layout.addWidget(self.progress_bar)

    def _get_status_color(self, status: str) -> str:
        colors = {
            "WAITING": COLORS["subtle"],
            "PENDING": COLORS["warning"],
            "GENERATING": COLORS["info"],
            "COMPLETED": COLORS["success"],
            "FAILED": COLORS["danger"],
        }
        return colors.get(status, COLORS["subtle"])

    def _get_status_soft_color(self, status: str) -> str:
        colors = {
            "WAITING": COLORS["panel_alt"],
            "PENDING": COLORS["warning_soft"],
            "GENERATING": COLORS["info_soft"],
            "COMPLETED": COLORS["success_soft"],
            "FAILED": COLORS["danger_soft"],
        }
        return colors.get(status, COLORS["panel_alt"])

    def _get_status_text(self, status: str) -> str:
        texts = {
            "WAITING": "等待中",
            "PENDING": "待处理",
            "GENERATING": "生成中",
            "COMPLETED": "完成",
            "FAILED": "失败",
        }
        return texts.get(status, status)

    def update_status(self, status: str):
        self.task["status"] = status
        while self.layout() and self.layout().count():
            item = self.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._setup_ui()
