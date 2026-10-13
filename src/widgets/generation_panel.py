import json
import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.adapters import get_all_adapters
from src.adapters.errors import Diagnostic
from src.config.providers import adapter_id, model_capabilities
from src.widgets.components.diagnostic_card import DiagnosticCard
from src.widgets.components.prompt_card import TaskCard
from src.widgets.theme import (
    COLORS,
    app_font,
    apply_card_style,
    button_style,
    input_style,
    label_style,
    scroll_area_style,
)


def normalize_size_value(size_text: str) -> str:
    return size_text.replace("×", "x").replace("≠", "x").replace("?", "x")


class GenerationPanel(QWidget):
    generate_signal = Signal(dict)
    add_to_queue_signal = Signal(dict)
    save_template_signal = Signal(dict)
    open_settings_requested = Signal()

    def __init__(self, queue_manager, parent=None):
        super().__init__(parent)
        self.queue_manager = queue_manager
        self.current_platform = "openai"
        self.sources: list[dict] = []
        self.models_by_source: dict[str, list[dict]] = {}
        self.current_source_id = ""
        self.current_model_id = ""
        self.last_diagnostic: Diagnostic | None = None
        self.adapters = {}
        self.reference_image_path = None
        self.platform_configured: dict[str, bool] = {}
        self.platform_config_messages: dict[str, str] = {}
        self._param_labels = {}
        self._setup_ui()
        self._load_adapters()
        self._install_shortcuts()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(scroll_area_style())

        self.content_widget = QWidget()
        self.content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        main_layout = QVBoxLayout(self.content_widget)
        main_layout.setContentsMargins(0, 0, 8, 0)
        main_layout.setSpacing(12)
        self.scroll_area.setWidget(self.content_widget)
        outer_layout.addWidget(self.scroll_area)

        header_layout = QHBoxLayout()
        heading = QLabel("创作工作台")
        heading.setFont(app_font(13, QFont.Weight.Bold))
        heading.setStyleSheet(label_style("section"))
        header_layout.addWidget(heading)
        header_layout.addStretch()
        self.prompt_count_label = QLabel("0 字")
        self.prompt_count_label.setStyleSheet(label_style("muted"))
        header_layout.addWidget(self.prompt_count_label)
        main_layout.addLayout(header_layout)

        self.config_hint_frame = QFrame()
        self.config_hint_frame.setProperty("imageMakerConfigHint", True)
        self.config_hint_frame.setStyleSheet(f"""
            QFrame[imageMakerConfigHint="true"] {{
                background: {COLORS["warning_soft"]};
                border: 1px solid {COLORS["border_strong"]};
                border-radius: 12px;
            }}
        """)
        hint_layout = QHBoxLayout(self.config_hint_frame)
        hint_layout.setContentsMargins(16, 12, 16, 12)
        self.config_hint_label = QLabel("请先完成当前平台配置，再开始生成。")
        self.config_hint_label.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px; font-weight: 600;")
        hint_layout.addWidget(self.config_hint_label)
        hint_layout.addStretch()
        self.open_settings_btn = QPushButton("打开设置")
        self.open_settings_btn.setStyleSheet(button_style("secondary"))
        self.open_settings_btn.clicked.connect(self.open_settings_requested.emit)
        hint_layout.addWidget(self.open_settings_btn)
        self.hint_status_stack = QFrame()
        self.hint_status_stack.setProperty("imageMakerTransparentFrame", True)
        self.hint_status_stack.setStyleSheet(
            'QFrame[imageMakerTransparentFrame="true"] { background: transparent; border: none; }'
        )
        hint_status_layout = QVBoxLayout(self.hint_status_stack)
        hint_status_layout.setContentsMargins(0, 0, 0, 0)
        hint_status_layout.setSpacing(0)
        hint_status_layout.addWidget(self.config_hint_frame)
        main_layout.addWidget(self.hint_status_stack)

        self.status_frame = QFrame()
        self.status_frame.setVisible(False)
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(16, 8, 16, 8)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        status_layout.addWidget(self.status_label)
        self.copy_status_btn = QPushButton("复制")
        self.copy_status_btn.setStyleSheet(button_style("ghost"))
        self.copy_status_btn.clicked.connect(self._copy_status_message)
        status_layout.addWidget(self.copy_status_btn)

        self.close_status_btn = QPushButton("×")
        self.close_status_btn.setFixedSize(24, 24)
        self.close_status_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS["muted"]};
                border: none;
                font-size: 18px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{
                color: {COLORS["text"]};
            }}
        """)
        self.close_status_btn.clicked.connect(lambda: self.status_frame.setVisible(False))
        status_layout.addWidget(self.close_status_btn)
        hint_status_layout.addWidget(self.status_frame)

        selector_frame = QFrame()
        apply_card_style(selector_frame, COLORS["panel_alt"])
        selector_layout = QVBoxLayout(selector_frame)
        selector_layout.setContentsMargins(16, 12, 16, 12)
        selector_layout.setSpacing(10)
        self.selector_control_layout = QHBoxLayout()
        self.selector_control_layout.setSpacing(12)
        self.selector_action_layout = QHBoxLayout()
        self.selector_action_layout.setSpacing(10)
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(180)
        self.source_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.source_combo.setStyleSheet(input_style())
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self._add_param_widget(self.selector_control_layout, "来源", self.source_combo)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(190)
        self.model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.model_combo.setStyleSheet(input_style())
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        self._add_param_widget(self.selector_control_layout, "模型", self.model_combo)
        selector_layout.addLayout(self.selector_control_layout)
        self.selector_action_layout.addStretch()
        self.manage_sources_btn = QPushButton("管理来源")
        self.manage_sources_btn.setStyleSheet(button_style("secondary"))
        self.manage_sources_btn.clicked.connect(self.open_settings_requested.emit)
        self.selector_action_layout.addWidget(self.manage_sources_btn)
        self.diagnostic_toggle_btn = QPushButton("请求诊断")
        self.diagnostic_toggle_btn.setStyleSheet(button_style("secondary"))
        self.diagnostic_toggle_btn.clicked.connect(self._toggle_diagnostic_panel)
        self.selector_action_layout.addWidget(self.diagnostic_toggle_btn)
        selector_layout.addLayout(self.selector_action_layout)
        main_layout.addWidget(selector_frame)

        prompt_frame = QFrame()
        apply_card_style(prompt_frame)
        prompt_layout = QHBoxLayout(prompt_frame)
        prompt_layout.setContentsMargins(16, 16, 16, 16)
        prompt_layout.setSpacing(16)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)
        left_label = QLabel("Prompt")
        left_label.setStyleSheet(label_style("section"))
        left_layout.addWidget(left_label)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("描述你想生成的画面，例如：清晨森林里的玻璃小屋，柔和自然光，电影感")
        self.prompt_edit.setStyleSheet(input_style())
        self.prompt_edit.setMinimumHeight(128)
        self.prompt_edit.textChanged.connect(self._update_prompt_count)
        left_layout.addWidget(self.prompt_edit)
        prompt_layout.addLayout(left_layout, 1)

        self.negative_container = QWidget()
        right_layout = QVBoxLayout(self.negative_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_label = QLabel("Negative Prompt")
        right_label.setStyleSheet(label_style("section"))
        right_layout.addWidget(right_label)
        self.negative_edit = QTextEdit()
        self.negative_edit.setPlaceholderText("填写不希望出现的内容，例如：低清晰度、变形、噪点、文字水印")
        self.negative_edit.setStyleSheet(input_style())
        self.negative_edit.setMinimumHeight(128)
        right_layout.addWidget(self.negative_edit)
        prompt_layout.addWidget(self.negative_container, 1)
        main_layout.addWidget(prompt_frame, 2)

        params_frame = QFrame()
        apply_card_style(params_frame, COLORS["panel_alt"])
        params_layout = QVBoxLayout(params_frame)
        params_layout.setContentsMargins(16, 16, 16, 16)
        params_layout.setSpacing(12)
        self.primary_params_layout = QHBoxLayout()
        self.primary_params_layout.setSpacing(16)
        self.secondary_params_layout = QHBoxLayout()
        self.secondary_params_layout.setSpacing(16)

        self.size_combo = QComboBox()
        self.size_combo.setEditable(True)
        self.size_combo.addItems(["1024×1024", "1792×1024", "1024×1792"])
        size_editor = QLineEdit()
        size_editor.setPlaceholderText("如 1536x1024")
        self.size_combo.setLineEdit(size_editor)
        self.size_combo.setMinimumWidth(90)
        self.size_combo.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.size_combo.setStyleSheet(input_style())
        self._add_param_widget(self.primary_params_layout, "尺寸", self.size_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.setEditable(True)
        self.quality_combo.addItems(["standard", "hd", "low", "medium", "high", "auto"])
        self.quality_combo.setMinimumWidth(90)
        self.quality_combo.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.quality_combo.setStyleSheet(input_style())
        self._add_param_widget(self.primary_params_layout, "质量", self.quality_combo)

        self.count_combo = QComboBox()
        self.count_combo.addItems(["1", "2", "4", "8"])
        self.count_combo.setMinimumWidth(60)
        self.count_combo.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.count_combo.setStyleSheet(input_style())
        self._add_param_widget(self.primary_params_layout, "数量", self.count_combo)

        self.seed_input = QComboBox()
        self.seed_input.setEditable(True)
        seed_editor = QLineEdit()
        seed_editor.setPlaceholderText("随机")
        self.seed_input.setLineEdit(seed_editor)
        self.seed_input.setMinimumWidth(80)
        self.seed_input.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.seed_input.setStyleSheet(input_style())
        self._add_param_widget(self.secondary_params_layout, "Seed", self.seed_input)
        self.primary_params_layout.addStretch()

        self.advanced_btn = QPushButton("+ 高级参数")
        self.advanced_btn.setStyleSheet(button_style("secondary"))
        self.advanced_btn.setCheckable(True)
        self.secondary_params_layout.addWidget(self.advanced_btn)
        self.secondary_params_layout.addStretch()
        params_layout.addLayout(self.primary_params_layout)
        params_layout.addLayout(self.secondary_params_layout)
        main_layout.addWidget(params_frame)
        self.advanced_frame = QFrame()
        apply_card_style(self.advanced_frame, COLORS["panel_alt"])
        advanced_layout = QHBoxLayout(self.advanced_frame)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["png", "jpeg", "webp"])
        self.format_combo.setStyleSheet(input_style())
        self._add_param_widget(advanced_layout, "输出格式", self.format_combo)
        self.transparent_check = QCheckBox("透明背景")
        self.transparent_check.setToolTip("透明背景需要 PNG 或 WebP；服务商可能限制可用模型")
        advanced_layout.addWidget(self.transparent_check)
        self.advanced_frame.setVisible(False)
        self.advanced_btn.toggled.connect(self.advanced_frame.setVisible)
        main_layout.addWidget(self.advanced_frame)

        actions_frame = QFrame()
        apply_card_style(actions_frame)
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(16, 16, 16, 16)
        actions_layout.setSpacing(12)

        self.image_btn = QPushButton("选择参考图")
        self.image_btn.setStyleSheet(button_style("secondary"))
        self.image_btn.setToolTip("选择一张参考图片用于图生图")
        self.image_btn.clicked.connect(self._select_reference_image)
        actions_layout.addWidget(self.image_btn)

        self.clear_image_btn = QPushButton("移除参考图")
        self.clear_image_btn.setStyleSheet(button_style("ghost"))
        self.clear_image_btn.clicked.connect(self._clear_reference_image)
        self.clear_image_btn.setVisible(False)
        actions_layout.addWidget(self.clear_image_btn)

        self.save_template_btn = QPushButton("保存模板")
        self.save_template_btn.setStyleSheet(button_style("secondary"))
        self.save_template_btn.setToolTip("将当前提示词和参数保存为模板 (Ctrl+S)")
        self.save_template_btn.setShortcut(QKeySequence("Ctrl+S"))
        self.save_template_btn.clicked.connect(self._save_current_template)
        actions_layout.addWidget(self.save_template_btn)
        actions_layout.addStretch()

        self.queue_btn = QPushButton("加入队列")
        self.queue_btn.setMinimumHeight(38)
        self.queue_btn.setToolTip("将生成任务加入队列，稍后批量执行")
        self.queue_btn.setStyleSheet(button_style("secondary"))
        self.queue_btn.clicked.connect(self._add_to_queue)
        actions_layout.addWidget(self.queue_btn)

        self.generate_btn = QPushButton("立即生成")
        self.generate_btn.setMinimumHeight(40)
        self.generate_btn.setToolTip("立即提交生成任务 (Ctrl+Return)")
        self.generate_btn.setStyleSheet(button_style("primary"))
        self.generate_btn.setShortcut(QKeySequence("Ctrl+Return"))
        self.generate_btn.clicked.connect(self._generate)
        actions_layout.addWidget(self.generate_btn)
        main_layout.addWidget(actions_frame)

        self.diagnostic_frame = QFrame()
        self.diagnostic_frame.setVisible(False)
        apply_card_style(self.diagnostic_frame, COLORS["panel_alt"])
        diagnostic_layout = QVBoxLayout(self.diagnostic_frame)
        diagnostic_layout.setContentsMargins(16, 12, 16, 12)
        diagnostic_header = QHBoxLayout()
        diagnostic_title = QLabel("请求诊断")
        diagnostic_title.setStyleSheet(label_style("section"))
        diagnostic_header.addWidget(diagnostic_title)
        diagnostic_header.addStretch()
        diagnostic_layout.addLayout(diagnostic_header)
        self.diagnostic_card_frame: DiagnosticCard | None = None
        self.diagnostic_card_container = QVBoxLayout()
        self.diagnostic_card_container.setContentsMargins(0, 0, 0, 0)
        diagnostic_layout.addLayout(self.diagnostic_card_container)
        self.diagnostic_history_container = QWidget()
        self.diagnostic_history_layout = QVBoxLayout(self.diagnostic_history_container)
        self.diagnostic_history_layout.setContentsMargins(0, 0, 0, 0)
        self.diagnostic_history_layout.setSpacing(8)
        diagnostic_layout.addWidget(self.diagnostic_history_container)
        self.diagnostic_history_container.setVisible(False)
        main_layout.addWidget(self.diagnostic_frame)

        queue_frame = QFrame()
        apply_card_style(queue_frame)
        queue_layout = QVBoxLayout(queue_frame)
        queue_layout.setContentsMargins(16, 16, 16, 16)
        queue_layout.setSpacing(12)

        queue_header = QHBoxLayout()
        queue_label = QLabel("生成队列")
        queue_label.setFont(app_font(12, QFont.Weight.Bold))
        queue_label.setStyleSheet(label_style("section"))
        queue_header.addWidget(queue_label)
        self.queue_count_label = QLabel("(0)")
        self.queue_count_label.setStyleSheet(f"color: {COLORS['primary_text']}; font-size: 12px; font-weight: 700;")
        queue_header.addWidget(self.queue_count_label)
        queue_header.addStretch()

        clear_btn = QPushButton("清空已完成")
        clear_btn.setStyleSheet(button_style("ghost"))
        clear_btn.clicked.connect(self._clear_completed)
        queue_header.addWidget(clear_btn)
        queue_layout.addLayout(queue_header)

        self.queue_container = QVBoxLayout()
        self.queue_container.setSpacing(10)
        queue_layout.addLayout(self.queue_container)
        self.queue_empty_label = QLabel("队列为空，输入提示词后可立即生成或加入队列。")
        self.queue_empty_label.setStyleSheet(label_style("muted"))
        queue_layout.addWidget(self.queue_empty_label)
        main_layout.addWidget(queue_frame)

    def show_status(self, message: str, kind: str = "info"):
        styles = {
            "info": (COLORS["info_soft"], COLORS["info"], COLORS["border_strong"]),
            "success": (COLORS["success_soft"], COLORS["success"], COLORS["border_strong"]),
            "warning": (COLORS["warning_soft"], COLORS["warning"], COLORS["border_strong"]),
            "error": (COLORS["danger_soft"], COLORS["danger"], COLORS["border_strong"]),
        }
        background, color, border = styles.get(kind, styles["info"])
        self.status_frame.setProperty("imageMakerStatusFrame", True)
        self.status_frame.setStyleSheet(f"""
            QFrame[imageMakerStatusFrame="true"] {{
                background: {background};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")
        self.status_label.setText(message)
        self._update_config_state_ui()
        self.status_label.setVisible(True)
        self.copy_status_btn.setVisible(True)

        # 根据消息类型设置不同自动隐藏时间
        if kind in ("success", "info"):
            hide_ms = 8000  # 8 秒
        elif kind == "warning":
            hide_ms = 10000  # 10 秒
        else:  # error
            hide_ms = 0  # 不自动隐藏，需手动关闭

        # 清除旧 timer
        if hasattr(self, "_hide_timer") and self._hide_timer:
            self._hide_timer.stop()

        if hide_ms > 0:
            self._hide_timer = QTimer.singleShot(hide_ms, lambda: self.status_frame.setVisible(False))

    def _copy_status_message(self):
        QApplication.clipboard().setText(self.status_label.text())

    def _install_shortcuts(self):
        shortcut = QShortcut(QKeySequence("Ctrl+Enter"), self)
        shortcut.activated.connect(self._generate)

    def _add_param_widget(self, layout, label, widget):
        v_layout = QVBoxLayout()
        v_layout.setSpacing(8)
        lbl = QLabel(label)
        self._param_labels[widget] = lbl
        lbl.setStyleSheet(label_style("muted"))
        v_layout.addWidget(lbl)
        v_layout.addWidget(widget)
        layout.addLayout(v_layout)

    def _load_adapters(self):
        for adapter in get_all_adapters():
            self.adapters[adapter.platform_id] = adapter
        self.current_platform = "openai"
        self._update_config_state_ui()

    def _on_platform_changed(self, index):
        self._update_config_state_ui()

    def set_sources(self, sources: list[dict], models_by_source: dict[str, list[dict]]):
        if sources == self.sources and models_by_source == self.models_by_source:
            return
        previous_source = self.current_source_id
        previous_model = self.current_model_id
        self.sources = sources
        self.models_by_source = models_by_source
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for source in sources:
            self.source_combo.addItem(source.get("name", "未命名来源"), source.get("id"))
        source_index = self.source_combo.findData(previous_source)
        self.source_combo.setCurrentIndex(source_index if source_index >= 0 else (0 if sources else -1))
        self.source_combo.blockSignals(False)
        self._on_source_changed(self.source_combo.currentIndex(), preferred_model_id=previous_model)
        self._update_config_state_ui()

    def _on_source_changed(self, index: int, preferred_model_id: str = ""):
        self.current_source_id = self.source_combo.itemData(index) or ""
        source = next((item for item in self.sources if item.get("id") == self.current_source_id), {})
        self.current_platform = adapter_id(source.get("interface_type", "openai_images"))
        models = self.models_by_source.get(self.current_source_id, [])
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for model in models:
            self.model_combo.addItem(
                str(model.get("display_name") or model.get("model_id") or "Model"), model.get("id")
            )
        model_index = self.model_combo.findData(preferred_model_id)
        self.model_combo.setCurrentIndex(model_index if model_index >= 0 else (0 if models else -1))
        self.model_combo.blockSignals(False)
        self._on_model_changed(self.model_combo.currentIndex())

    def _on_model_changed(self, index: int):
        self.current_model_id = self.model_combo.itemData(index) or ""
        model = self._current_model()
        if model:
            source = next((item for item in self.sources if item.get("id") == self.current_source_id), {})
            caps = model_capabilities(source.get("interface_type", "openai_images"), model.get("model_id", ""))
            self.size_combo.clear()
            self.size_combo.addItems(caps["sizes"])
            self.quality_combo.clear()
            self.quality_combo.addItems(caps["qualities"])
            self.seed_input.setEnabled(caps["seed"])
            self.negative_edit.setEnabled(caps["negative"])
            self.negative_container.setVisible(caps["negative"])
            self._param_labels[self.size_combo].setText(caps["size_label"])
            self._param_labels[self.quality_combo].setText(caps["quality_label"])
            self.quality_combo.setEnabled(len(caps["qualities"]) > 1)
            self.format_combo.setEnabled(caps["format"])
            self.transparent_check.setEnabled(caps["format"])
            self.advanced_btn.setVisible(caps["format"])
            self.advanced_frame.setVisible(caps["format"] and self.advanced_btn.isChecked())
            self.image_btn.setEnabled(caps["reference"])
            self.image_btn.setToolTip(
                "选择参考图，生成时会发送给所选服务商" if caps["reference"] else "当前接口不支持参考图"
            )
            self.negative_edit.setPlaceholderText(
                "排除不希望出现的内容" if caps["negative"] else "当前模型不支持独立反向提示词，请在主提示词中描述限制"
            )
            self.size_combo.setEditText(model.get("default_size") or caps["sizes"][0])
            quality = model.get("default_quality") or caps["qualities"][0]
            if str(model.get("model_id", "")).startswith("gpt-image-"):
                quality = {"standard": "auto", "hd": "high"}.get(quality, quality)
            self.quality_combo.setEditText(str(quality))
            count_index = self.count_combo.findText(str(model.get("default_n", 1)))
            if count_index >= 0:
                self.count_combo.setCurrentIndex(count_index)
        self._update_config_state_ui()

    def _current_model(self) -> dict | None:
        for model in self.models_by_source.get(self.current_source_id, []):
            if model.get("id") == self.current_model_id:
                return model
        return None

    def set_platform_configured(self, platform_id: str, configured: bool):
        self.platform_configured[platform_id] = configured
        if configured:
            self.platform_config_messages.pop(platform_id, None)
        self._update_config_state_ui()

    def set_platform_config_statuses(self, statuses: dict[str, bool], messages: dict[str, str] | None = None):
        self.platform_configured.update(statuses)
        if messages is not None:
            self.platform_config_messages = messages
        self._update_config_state_ui()

    def _is_current_platform_configured(self) -> bool:
        return bool(self.current_source_id and self.current_model_id)

    def _update_config_state_ui(self):
        configured = self._is_current_platform_configured()
        self.config_hint_frame.setVisible(not configured)
        if hasattr(self, "status_frame"):
            self.status_frame.setVisible(configured and bool(self.status_label.text()))
        self.config_hint_label.setText(self._current_config_hint())
        self.generate_btn.setEnabled(configured)
        self.queue_btn.setEnabled(configured)

    def _current_config_hint(self, include_settings_action: bool = False) -> str:
        message = self.platform_config_messages.get(
            self.current_platform,
            "请先在设置中新增来源和模型，再开始生成。",
        )
        if include_settings_action:
            message += "可点击右侧“打开设置”。"
        return message

    def _update_prompt_count(self):
        length = len(self.prompt_edit.toPlainText().strip())
        self.prompt_count_label.setText(f"{length} 字")

    def _select_reference_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择参考图片", "", "图片文件 (*.png *.jpg *.jpeg *.webp)")
        if file_path:
            self.reference_image_path = file_path
            self._update_reference_image_ui()

    def _update_reference_image_ui(self):
        if self.reference_image_path:
            filename = os.path.basename(self.reference_image_path)
            self.image_btn.setText(filename)
            self.image_btn.setToolTip(self.reference_image_path)
            self.clear_image_btn.setVisible(True)
            self.show_status(f"\u5df2\u9009\u62e9\u53c2\u8003\u56fe\uff1a{filename}", "success")
        else:
            self.image_btn.setText("选择参考图")
            self.image_btn.setToolTip("")
            self.clear_image_btn.setVisible(False)

    def _clear_reference_image(self):
        self.reference_image_path = None
        self._update_reference_image_ui()
        self.show_status("\u5df2\u79fb\u9664\u53c2\u8003\u56fe", "info")

    def _get_params(self) -> dict:
        size_text = self.size_combo.currentText()
        size = normalize_size_value(size_text)
        params = {
            "size": size,
            "quality": self.quality_combo.currentText().strip() or "standard",
            "n": int(self.count_combo.currentText()),
        }
        if self.seed_input.isEnabled() and self.seed_input.currentText():
            params["seed"] = self.seed_input.currentText()
        if hasattr(self, "format_combo") and self.format_combo.isEnabled():
            params["output_format"] = self.format_combo.currentText()
            params["background"] = "transparent" if self.transparent_check.isChecked() else "auto"
        return params

    def _build_task_data(self) -> dict:
        return {
            "platform_id": self.current_platform,
            "source_id": self.current_source_id,
            "model_config_id": self.current_model_id,
            "prompt": self.prompt_edit.toPlainText().strip(),
            "negative_prompt": self.negative_edit.toPlainText().strip(),
            "params": self._get_params(),
            "reference_image_path": self.reference_image_path,
        }

    def _can_submit(self, show_message: bool = True) -> bool:
        if not self._is_current_platform_configured():
            self._update_config_state_ui()
            self.config_hint_label.setText(self._current_config_hint(include_settings_action=True))
            return False
        if not self.prompt_edit.toPlainText().strip():
            if show_message:
                QMessageBox.warning(self, "\u63d0\u793a", "\u8bf7\u8f93\u5165 Prompt")
            return False
        return True

    def _add_to_queue(self):
        if not self._can_submit():
            return False
        self.queue_btn.setEnabled(False)
        self.queue_btn.setText("已加入…")
        self.add_to_queue_signal.emit(self._build_task_data())
        self.show_status("已加入队列", "success")
        return True

    def _generate(self):
        if not self._can_submit():
            return False
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("\u751f\u6210\u4e2d\u2026")
        self.queue_btn.setEnabled(False)
        self.generate_signal.emit(self._build_task_data())
        self.show_status(
            "\u5df2\u63d0\u4ea4\u751f\u6210\u4efb\u52a1\uff0c\u8bf7\u7559\u610f\u961f\u5217\u72b6\u6001\u3002",
            "success",
        )
        return True

    def _save_current_template(self):
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入 Prompt 后再保存模板")
            return False
        default_name = prompt[:18] + ("..." if len(prompt) > 18 else "")
        name, ok = QInputDialog.getText(self, "保存模板", "模板名称", text=default_name)
        if not ok:
            return False
        category, ok = QInputDialog.getText(self, "保存模板", "分类", text="默认")
        if not ok:
            return False
        template = {
            "id": 0,
            "name": name.strip() or default_name,
            "prompt": prompt,
            "negative_prompt": self.negative_edit.toPlainText().strip(),
            "platform_id": self.current_platform,
            "source_id": self.current_source_id,
            "model_config_id": self.current_model_id,
            "params": self._get_params(),
            "category": category.strip() or "默认",
            "tags": "",
        }
        self.save_template_signal.emit(template)
        QMessageBox.information(self, "提示", "模板已保存")
        return True

    def apply_template(self, template: dict):
        source_id = template.get("source_id")
        if source_id:
            source_index = self.source_combo.findData(source_id)
            if source_index < 0:
                self.show_status("原来源已禁用或删除，请先选择可用的来源和模型。", "warning")
            else:
                self.source_combo.setCurrentIndex(source_index)
                model_index = self.model_combo.findData(template.get("model_config_id"))
                if model_index >= 0:
                    self.model_combo.setCurrentIndex(model_index)
        self.prompt_edit.setPlainText(template.get("prompt", ""))
        self.negative_edit.setPlainText(template.get("negative_prompt", ""))
        params = dict(template.get("params") or {})
        params.pop("_diagnostic", None)
        if params.get("size"):
            target = params["size"].replace("x", "×")
            index = self.size_combo.findText(target)
            if index >= 0:
                self.size_combo.setCurrentIndex(index)
            else:
                self.size_combo.setEditText(str(params["size"]))
        if params.get("quality"):
            index = self.quality_combo.findText(str(params["quality"]))
            if index >= 0:
                self.quality_combo.setCurrentIndex(index)
            else:
                self.quality_combo.setEditText(str(params["quality"]))
        if params.get("n"):
            index = self.count_combo.findText(str(params["n"]))
            if index >= 0:
                self.count_combo.setCurrentIndex(index)
        if params.get("seed"):
            self.seed_input.setEditText(str(params["seed"]))
        self.show_status("\u6a21\u677f\u5185\u5bb9\u5df2\u586b\u5165\u751f\u6210\u533a\u3002", "success")

    def update_diagnostic(self, diagnostic: Diagnostic | dict | None, expand: bool = False):
        if isinstance(diagnostic, dict):
            self.last_diagnostic = Diagnostic.from_dict(diagnostic) if diagnostic else None
        else:
            self.last_diagnostic = diagnostic
        self._render_diagnostic_card()
        if self.last_diagnostic is None:
            self.diagnostic_frame.setVisible(False)
            return
        if expand:
            self.diagnostic_frame.setVisible(True)

    def _render_diagnostic_card(self):
        if self.diagnostic_card_frame is not None:
            self.diagnostic_card_frame.setParent(None)
            self.diagnostic_card_frame.deleteLater()
            self.diagnostic_card_frame = None
        if self.last_diagnostic is None:
            return
        self.diagnostic_card_frame = DiagnosticCard(self.last_diagnostic, parent=self.diagnostic_frame)
        self.diagnostic_card_container.addWidget(self.diagnostic_card_frame)

    def _toggle_diagnostic_panel(self):
        self.diagnostic_frame.setVisible(not self.diagnostic_frame.isVisible())

    def show_diagnostic_history(self, records: list[dict]):
        """显示历史诊断记录列表，最多 8 条。"""
        while self.diagnostic_history_layout.count():
            item = self.diagnostic_history_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()

        if not records:
            self.diagnostic_history_container.setVisible(False)
            return

        for record in records[:8]:
            diag_obj = Diagnostic.from_dict(record.get("diagnostic") or record)
            card = DiagnosticCard(diag_obj, parent=self.diagnostic_history_container)
            self.diagnostic_history_layout.addWidget(card)

        self.diagnostic_history_layout.addStretch()
        self.diagnostic_history_container.setVisible(True)

    def _copy_single_diagnostic(self, record: dict):
        QApplication.clipboard().setText(
            json.dumps(Diagnostic.from_dict(record.get("diagnostic") or record).to_dict(), ensure_ascii=False, indent=2)
        )

    def _clear_completed(self):
        self.queue_manager.clear_completed()
        self._update_queue_display()

    def refresh_queue(self):
        self._update_queue_display()
        # 恢复按钮状态
        info = self.queue_manager.get_queue_info()
        if info["generating"] == 0 and info["waiting"] == 0:
            configured = self._is_current_platform_configured()
            self.generate_btn.setEnabled(configured)
            self.generate_btn.setText("立即生成")
            self.queue_btn.setEnabled(configured)
            self.queue_btn.setText("加入队列")

    def _update_queue_display(self):
        info = self.queue_manager.get_queue_info()
        active_count = info["waiting"] + info["generating"]
        self.queue_count_label.setText(f"({active_count})")

        if hasattr(self.queue_manager, "get_task_snapshots"):
            task_dicts = self.queue_manager.get_task_snapshots(5)
        else:
            task_dicts = []

        # 获取当前队列中已有的 task_id 集合
        existing_ids = {}
        for i in range(self.queue_container.count()):
            item = self.queue_container.itemAt(i)
            w = item.widget() if item else None
            if w and hasattr(w, "_task_id"):
                existing_ids[getattr(w, "_task_id", "")] = w

        new_ids = {t.get("task_id") for t in task_dicts}

        # 移除不在新列表中的卡片
        for tid in list(existing_ids.keys()):
            if tid not in new_ids:
                w = existing_ids.pop(tid)
                self.queue_container.removeWidget(w)
                w.deleteLater()

        # 隐藏 stretch (最后一个 item)，添加新卡片后重新添加 stretch
        for i in range(self.queue_container.count()):
            item = self.queue_container.itemAt(i)
            if item and item.spacerItem():
                self.queue_container.takeAt(i)
                break

        # 添加新卡片
        for task in task_dicts[:5]:
            tid = task.get("task_id")
            if tid not in existing_ids:
                card = TaskCard(task)
                card.setMinimumWidth(0)
                card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                card._task_id = tid
                card.cancel_signal.connect(self._cancel_task)
                self.queue_container.addWidget(card)
            else:
                existing_ids[tid].update_task(task)

        # 重新添加 stretch
        self.queue_container.addStretch()

        self.queue_empty_label.setVisible(not task_dicts)

    def _cancel_task(self, task_id: str):
        self.queue_manager.cancel_task(task_id)
        self._update_queue_display()
