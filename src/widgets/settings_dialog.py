from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QHeaderView,
    QSizePolicy, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

import json

from src.adapters import get_adapter
from src.config import constants, encryption
from src.models.platform_config import PlatformConfig
from src.widgets.theme import COLORS, RADIUS, SPACING, app_font, apply_card_style, button_style, input_style, label_style, tab_style


AUTH_PRESET_LABELS = {
    "openai": "OpenAI / xAI / Cohere（Authorization: Bearer）",
    "anthropic": "Anthropic Claude（x-api-key）",
    "gemini": "Google Gemini（x-goog-api-key）",
    "xai": "xAI Grok（Authorization: Bearer）",
    "cohere": "Cohere（Authorization: Bearer）",
    "custom": "自定义 / Custom（Authorization: Bearer）",
}

RESPONSE_FORMAT_LABELS = {
    "openai": "OpenAI 标准（data[].url）",
    "minimax": "MiniMax（data.image_urls）",
    "auto": "自动检测",
}


class SettingsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.sources: list[dict] = []
        self.models_by_source: dict[str, list[dict]] = {}
        self.current_source_id: str | None = None
        self._setup_ui()
        self._load_saved_configs()

    def _setup_ui(self):
        self.setWindowTitle("来源与模型管理")
        self.setMinimumSize(900, 640)
        self.resize(1080, 780)
        self.setStyleSheet(f"background: {COLORS['background']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING['xl'], SPACING['xl'], SPACING['xl'], SPACING['lg'])
        root.setSpacing(16)

        title = QLabel("来源与模型")
        title.setFont(app_font(17, QFont.Bold))
        title.setStyleSheet(label_style("title"))
        root.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            tab_style().replace(
                "QTabWidget::pane {",
                f"QTabWidget::pane {{ background: {COLORS['panel']}; border: 1px solid {COLORS['border']}; border-radius: {RADIUS['control']}px; padding: {SPACING['lg']}px;"
            )
        )
        root.addWidget(self.tabs, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
                color: {COLORS['primary']};
                background: {COLORS['primary_soft']};
            }}
        """)
        button_box.accepted.connect(self._save)
        button_box.rejected.connect(self.reject)
        root.addWidget(button_box)

        self.source_tab = QWidget()
        self.tabs.addTab(self.source_tab, "来源与模型")
        self._setup_source_tab()

        self.data_tab = QWidget()
        self.tabs.addTab(self.data_tab, "数据管理")
        self._setup_data_tab()

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(label_style("muted"))
        return label

    def _setup_source_tab(self):
        """Setup the sources & models tab content"""
        body = QHBoxLayout(self.source_tab)
        body.setSpacing(SPACING['md'])
        body.setContentsMargins(0, 0, 0, 0)

        left = QFrame()
        self.source_left_panel = left
        left.setMinimumWidth(220)
        left.setMaximumWidth(360)
        apply_card_style(left, COLORS["panel_alt"])
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)
        left_title = QLabel("来源")
        left_title.setStyleSheet(label_style("section"))
        left_layout.addWidget(left_title)
        self.source_list = QListWidget()
        self.source_list.setMinimumHeight(430)
        self.source_list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                padding: 6px;
            }}
            QListWidget::item {{
                min-height: 34px;
                padding: 8px 10px;
                border-radius: 8px;
            }}
            QListWidget::item:selected {{
                background: {COLORS['primary_soft']};
                color: {COLORS['primary']};
                font-weight: 700;
            }}
        """)
        self.source_list.currentItemChanged.connect(self._on_source_selected)
        left_layout.addWidget(self.source_list, 1)
        self.primary_source_actions = QHBoxLayout()
        self.primary_source_actions.setSpacing(SPACING['sm'])
        add_source_btn = QPushButton("新增来源")
        add_source_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        add_source_btn.setStyleSheet(button_style("primary"))
        add_source_btn.clicked.connect(self._add_source)
        self.primary_source_actions.addWidget(add_source_btn)
        left_layout.addLayout(self.primary_source_actions)

        self.maintenance_source_actions = QHBoxLayout()
        self.maintenance_source_actions.setSpacing(SPACING['sm'])
        backup_btn = QPushButton("备份配置")
        backup_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        backup_btn.setStyleSheet(button_style("ghost"))
        backup_btn.clicked.connect(self._backup_config)
        self.maintenance_source_actions.addWidget(backup_btn)
        left_layout.addLayout(self.maintenance_source_actions)

        self.danger_source_actions = QHBoxLayout()
        self.danger_source_actions.setSpacing(SPACING['sm'])
        delete_source_btn = QPushButton("删除来源")
        delete_source_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        delete_source_btn.setStyleSheet(button_style("danger_ghost"))
        delete_source_btn.clicked.connect(self._delete_current_source)
        reset_btn = QPushButton("重置配置")
        reset_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        reset_btn.setStyleSheet(button_style("danger_ghost"))
        reset_btn.clicked.connect(self._reset_config)
        self.danger_source_actions.addWidget(delete_source_btn)
        self.danger_source_actions.addWidget(reset_btn)
        left_layout.addLayout(self.danger_source_actions)

        right = QFrame()
        apply_card_style(right)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(SPACING['lg'], SPACING['lg'], SPACING['lg'], SPACING['lg'])
        right_layout.setSpacing(16)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setWidget(right)
        self.source_splitter = QSplitter(Qt.Horizontal)
        self.source_splitter.addWidget(left)
        self.source_splitter.addWidget(right_scroll)
        self.source_splitter.setStretchFactor(0, 1)
        self.source_splitter.setStretchFactor(1, 3)
        self.source_splitter.setSizes([260, 760])
        body.addWidget(self.source_splitter, 1)

        source_title = QLabel("来源详情")
        source_title.setStyleSheet(label_style("section"))
        right_layout.addWidget(source_title)

        self.source_grid = QGridLayout()
        self.source_grid.setHorizontalSpacing(SPACING['md'])
        self.source_grid.setVerticalSpacing(12)
        self.source_grid.setColumnMinimumWidth(0, 92)
        self.source_grid.setColumnStretch(1, 1)
        right_layout.addLayout(self.source_grid)

        self.name_input = self._line_edit("source_name", "例如：dm-fox 中转站")
        self.name_input.setToolTip("来源显示名称，用于在界面上标识此 API 服务商")
        self.interface_combo = QComboBox()
        self.interface_combo.addItem("OpenAI 图像生成", "openai_images")
        self.interface_combo.addItem("自定义 / Custom（不拼接端点路径）", "custom")
        self.interface_combo.setStyleSheet(input_style())
        self.interface_combo.setMinimumHeight(38)
        self.interface_combo.currentIndexChanged.connect(self._on_interface_type_changed)
        self.interface_combo.setToolTip("接口格式：OpenAI 图片生成兼容接口 或 自定义请求模板")
        self.auth_combo = QComboBox()
        for key, label in AUTH_PRESET_LABELS.items():
            self.auth_combo.addItem(label, key)
        self.auth_combo.setStyleSheet(input_style())
        self.auth_combo.setMinimumHeight(38)
        self.auth_combo.setToolTip("鉴权方式：API Key 放在 Header (Bearer Token) 或 Query 参数中")
        self.response_format_label = self._label("响应格式")
        self.response_format_label.hide()
        self.response_format_combo = QComboBox()
        for key, label in RESPONSE_FORMAT_LABELS.items():
            self.response_format_combo.addItem(label, key)
        self.response_format_combo.setStyleSheet(input_style())
        self.response_format_combo.setMinimumHeight(38)
        self.response_format_combo.hide()
        self.url_input = self._line_edit("url_openai", "https://example.com/v1")
        self.url_input.setToolTip("API Base URL，例如 https://api.openai.com 或中转站地址")
        self.key_input = self._line_edit("key_openai", "sk-...", password=True)
        self.key_input.setToolTip("API 密钥，将以 Bearer Token 形式发送")
        self.proxy_check = QCheckBox("使用代理")
        self.proxy_check.setObjectName("proxy_check_openai")
        self.proxy_check.setToolTip("是否通过 HTTP 代理连接此 API")
        self.proxy_input = self._line_edit("proxy_openai", "http://127.0.0.1:8080")
        self.proxy_input.setToolTip("HTTP 代理地址，格式如 http://127.0.0.1:8080")
        self.active_check = QCheckBox("启用来源")
        self.active_check.setChecked(True)
        self.active_check.setToolTip("启用或禁用此来源（禁用后不会出现在生成面板中）")

        proxy_row = QWidget()
        proxy_layout = QHBoxLayout(proxy_row)
        proxy_layout.setContentsMargins(0, 0, 0, 0)
        proxy_layout.setSpacing(SPACING['sm'])
        proxy_layout.addWidget(self.proxy_input, 1)
        proxy_layout.addWidget(self.proxy_check)

        fields = [
            ("名称", self.name_input), ("接口格式", self.interface_combo),
            ("鉴权预设", self.auth_combo), ("Base URL", self.url_input),
            ("API Key", self.key_input), ("代理", proxy_row),
        ]
        self._response_format_row = 2
        for index, (label, widget) in enumerate(fields):
            row = index + 1 if index >= 2 else index
            self.source_grid.addWidget(self._label(label), row, 0)
            self.source_grid.addWidget(widget, row, 1)
        self.source_grid.addWidget(self.response_format_label, self._response_format_row, 0)
        self.source_grid.addWidget(self.response_format_combo, self._response_format_row, 1)
        self._rfm_added = True
        self.source_grid.addWidget(self.active_check, 7, 1)

        self.url_preview = QLabel()
        self.url_preview.setObjectName("url_preview_openai")
        self.url_preview.setStyleSheet(label_style("muted"))
        self.url_input.textChanged.connect(lambda: self._update_url_preview(self.interface_combo.currentData() or "openai_images"))
        self.url_preview.setMinimumHeight(28)
        self.url_preview.setContentsMargins(8, 4, 8, 4)
        self.url_preview.setStyleSheet(f"color: {COLORS['muted']}; font-size: 11px; background: {COLORS['panel_alt']}; border-radius: 8px; padding: 6px;")
        right_layout.addWidget(self.url_preview)

        headers_label = QLabel("来源级 Headers（高级，可覆盖自动鉴权 Header）")
        headers_label.setStyleSheet(label_style("section"))
        right_layout.addWidget(headers_label)
        self.header_table = QTableWidget(3, 2)
        self.header_table.setObjectName("headers_openai")
        self.header_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.header_table.setMinimumHeight(150)
        self.header_table.verticalHeader().setDefaultSectionSize(34)
        self.header_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.header_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.header_table.setStyleSheet(self._table_style())
        right_layout.addWidget(self.header_table)
        add_header_btn = QPushButton("+ 添加 Header")
        add_header_btn.setStyleSheet(button_style("ghost"))
        add_header_btn.clicked.connect(lambda: self.header_table.insertRow(self.header_table.rowCount()))
        right_layout.addWidget(add_header_btn)

        model_bar = QHBoxLayout()
        model_title = QLabel("模型")
        model_title.setStyleSheet(label_style("section"))
        model_bar.addWidget(model_title)
        model_bar.addStretch()
        add_model_btn = QPushButton("新增模型")
        add_model_btn.setStyleSheet(button_style("primary"))
        add_model_btn.clicked.connect(self._add_model_row)
        delete_model_btn = QPushButton("删除模型")
        delete_model_btn.setStyleSheet(button_style("danger_ghost"))
        delete_model_btn.clicked.connect(self._delete_model_row)
        model_bar.addWidget(add_model_btn)
        model_bar.addWidget(delete_model_btn)
        right_layout.addLayout(model_bar)

        self.model_table = QTableWidget(0, 5)
        self.model_table.setObjectName("model_openai")
        self.model_table.setHorizontalHeaderLabels(["显示名", "Model ID", "默认尺寸", "默认质量", "数量"])
        self.model_table.setMinimumHeight(210)
        self.model_table.setDragDropMode(QAbstractItemView.InternalMove)
        self.model_table.setDragDropOverwriteMode(False)
        self.model_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.model_table.verticalHeader().setDefaultSectionSize(36)
        self.model_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.model_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.model_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.model_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.model_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.model_table.setStyleSheet(self._table_style())
        self.model_table.horizontalHeaderItem(0).setToolTip("模型在界面上的显示名称，支持中文")
        self.model_table.horizontalHeaderItem(1).setToolTip("发送给 API 的模型 ID，必须与 API 文档一致（如 gpt-image-1）")
        self.model_table.horizontalHeaderItem(2).setToolTip("生成图片的默认尺寸")
        self.model_table.horizontalHeaderItem(3).setToolTip("生成图片的质量级别，高质量可能耗时更长")
        self.model_table.horizontalHeaderItem(4).setToolTip("单次请求生成的图片数量")
        right_layout.addWidget(self.model_table)

        self._update_url_preview("openai_images")

    def _setup_data_tab(self):
        """Setup the data management tab content"""
        layout = QVBoxLayout(self.data_tab)
        layout.setSpacing(16)

        # Export section
        export_group = QGroupBox("导出数据")
        export_layout = QVBoxLayout(export_group)
        export_desc = QLabel("将历史、模板、来源配置导出为 .imbackup 文件")
        export_desc.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")
        export_layout.addWidget(export_desc)
        self.export_btn = QPushButton("导出全部数据")
        self.export_btn.setStyleSheet(button_style("primary"))
        self.export_btn.clicked.connect(self._on_export)
        export_layout.addWidget(self.export_btn)
        layout.addWidget(export_group)

        # Import section
        import_group = QGroupBox("导入数据")
        import_layout = QVBoxLayout(import_group)
        import_desc = QLabel("从 .imbackup 文件导入历史、模板、来源配置")
        import_desc.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")
        import_layout.addWidget(import_desc)
        self.import_btn = QPushButton("导入数据")
        self.import_btn.setStyleSheet(button_style("secondary"))
        self.import_btn.clicked.connect(self._on_import)
        import_layout.addWidget(self.import_btn)
        layout.addWidget(import_group)

        # Key management section
        key_group = QGroupBox("API 密钥")
        key_layout = QVBoxLayout(key_group)
        key_desc = QLabel("导出或导入加密的密钥备份文件")
        key_desc.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")
        key_layout.addWidget(key_desc)
        key_btns = QHBoxLayout()
        self.export_keys_btn = QPushButton("导出密钥备份")
        self.export_keys_btn.setStyleSheet(button_style("ghost"))
        self.export_keys_btn.clicked.connect(self._on_export_keys)
        self.import_keys_btn = QPushButton("导入密钥备份")
        self.import_keys_btn.setStyleSheet(button_style("ghost"))
        self.import_keys_btn.clicked.connect(self._on_import_keys)
        key_btns.addWidget(self.export_keys_btn)
        key_btns.addWidget(self.import_keys_btn)
        key_layout.addLayout(key_btns)
        layout.addWidget(key_group)

        layout.addStretch()

    def _line_edit(self, object_name: str, placeholder: str, password: bool = False) -> QLineEdit:
        line_edit = QLineEdit()
        line_edit.setObjectName(object_name)
        line_edit.setPlaceholderText(placeholder)
        line_edit.setStyleSheet(input_style())
        line_edit.setMinimumHeight(38)
        if password:
            line_edit.setEchoMode(QLineEdit.Password)
        return line_edit

    def _table_style(self) -> str:
        return f"""
        QTableWidget {{
            background: {COLORS['panel']};
            border: 1px solid {COLORS['border']};
            border-radius: 12px;
            gridline-color: {COLORS['border']};
            selection-background-color: {COLORS['primary_soft']};
            selection-color: {COLORS['text']};
        }}
        QHeaderView::section {{
            background: {COLORS['panel_alt']};
            color: {COLORS['muted']};
            border: none;
            padding: 8px;
            font-weight: 700;
        }}
        QTableWidget::item {{
            padding: 8px;
        }}
        """

    def _load_saved_configs(self):
        if not self.db:
            self._ensure_draft_source()
            self._refresh_source_list()
            return
        from src.config.event_loop import run_async
        run_async(self.db.migrate_legacy_openai_config())
        self.sources = run_async(self.db.get_sources())
        self.models_by_source = {
            source["id"]: run_async(self.db.get_source_models(source["id"]))
            for source in self.sources
        }
        self._ensure_draft_source()
        self._refresh_source_list()

    def _ensure_draft_source(self):
        if self.sources:
            return
        source_id = f"src_{uuid4().hex}"
        self.sources = [{
            "id": source_id, "name": "OpenAI 官方", "interface_type": "openai_images",
            "auth_preset": "openai", "response_format": "openai",
            "api_base_url": constants.PLATFORM_DEFAULTS["openai"]["api_base_url"],
            "api_key_encrypted": None, "custom_headers": "{}", "proxy": None, "is_active": 1,
        }]
        self.models_by_source[source_id] = []

    def _refresh_source_list(self):
        self.source_list.clear()
        for source in self.sources:
            item = QListWidgetItem(source.get("name") or "未命名来源")
            item.setData(256, source["id"])
            self.source_list.addItem(item)
        if self.source_list.count() > 0:
            self.source_list.setCurrentRow(0)

    def _on_source_selected(self, current: QListWidgetItem | None, previous=None):
        if self.current_source_id:
            self._capture_current_source()
        if not current:
            return
        self.current_source_id = current.data(256)
        source = self._current_source()
        if not source:
            return
        self.name_input.setText(source.get("name", ""))
        self.interface_combo.setCurrentIndex(max(0, self.interface_combo.findData(source.get("interface_type", "openai_images"))))
        self.auth_combo.setCurrentIndex(max(0, self.auth_combo.findData(source.get("auth_preset", "openai"))))
        self.response_format_combo.setCurrentIndex(max(0, self.response_format_combo.findData(source.get("response_format", "openai"))))
        self.url_input.setText(source.get("api_base_url", ""))
        if source.get("api_key_encrypted"):
            try:
                self.key_input.setText(encryption.decrypt(source["api_key_encrypted"]))
            except Exception:
                self.key_input.clear()
        else:
            self.key_input.clear()
        proxy = source.get("proxy") or ""
        self.proxy_check.setChecked(bool(proxy))
        self.proxy_input.setText(proxy)
        self.active_check.setChecked(bool(source.get("is_active", 1)))
        self._fill_header_table(self._parse_headers(source.get("custom_headers")))
        self._fill_model_table(self.models_by_source.get(self.current_source_id, []))
        self._update_url_preview(self.interface_combo.currentData() or "openai_images")

    def _current_source(self) -> dict | None:
        return next((source for source in self.sources if source["id"] == self.current_source_id), None)

    def _capture_current_source(self):
        source = self._current_source()
        if not source:
            return
        source.update({
            "name": self.name_input.text().strip() or "未命名来源",
            "interface_type": self.interface_combo.currentData() or "openai_images",
            "auth_preset": self.auth_combo.currentData() or "openai",
            "response_format": self.response_format_combo.currentData() or "openai",
            "api_base_url": self.url_input.text().strip(),
            "api_key": self.key_input.text(),
            "custom_headers": json.dumps(self._headers_from_table(), ensure_ascii=False),
            "proxy": self.proxy_input.text().strip() if self.proxy_check.isChecked() else None,
            "is_active": 1 if self.active_check.isChecked() else 0,
        })
        self.models_by_source[source["id"]] = self._models_from_table(source["id"])

    def _add_source(self):
        self._capture_current_source()
        source_id = f"src_{uuid4().hex}"
        self.sources.append({
            "id": source_id, "name": "新来源", "interface_type": "openai_images",
            "auth_preset": "openai", "response_format": "openai",
            "api_base_url": "", "api_key_encrypted": None,
            "custom_headers": "{}", "proxy": None, "is_active": 1,
        })
        self.models_by_source[source_id] = []
        self._refresh_source_list()
        self.source_list.setCurrentRow(self.source_list.count() - 1)

    def _delete_current_source(self):
        if not self.current_source_id:
            return
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除当前来源及其所有模型配置吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.sources = [source for source in self.sources if source["id"] != self.current_source_id]
        self.models_by_source.pop(self.current_source_id, None)
        self.current_source_id = None
        self._ensure_draft_source()
        self._refresh_source_list()

    def _fill_header_table(self, headers: dict[str, str]):
        self.header_table.setRowCount(max(3, len(headers)))
        for row in range(self.header_table.rowCount()):
            self.header_table.setItem(row, 0, QTableWidgetItem(""))
            self.header_table.setItem(row, 1, QTableWidgetItem(""))
        for row, (key, value) in enumerate(headers.items()):
            self.header_table.setItem(row, 0, QTableWidgetItem(key))
            self.header_table.setItem(row, 1, QTableWidgetItem(value))

    def _headers_from_table(self) -> dict[str, str]:
        headers = {}
        for row in range(self.header_table.rowCount()):
            key_item = self.header_table.item(row, 0)
            value_item = self.header_table.item(row, 1)
            if key_item and key_item.text().strip() and value_item and value_item.text().strip():
                headers[key_item.text().strip()] = value_item.text().strip()
        return headers

    def _fill_model_table(self, models: list[dict]):
        self.model_table.setRowCount(0)
        for model in models:
            self._add_model_row(model)

    def _add_model_row(self, model: dict | None = None):
        row = self.model_table.rowCount()
        self.model_table.insertRow(row)
        values = [
            (model or {}).get("display_name", ""),
            (model or {}).get("model_id", ""),
            (model or {}).get("default_size", "1024x1024"),
            (model or {}).get("default_quality", "standard"),
            str((model or {}).get("default_n", 1)),
        ]
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col == 0 and model and model.get("id"):
                item.setData(256, model["id"])
            self.model_table.setItem(row, col, item)

    def _delete_model_row(self):
        row = self.model_table.currentRow()
        if row >= 0:
            self.model_table.removeRow(row)

    def _models_from_table(self, source_id: str) -> list[dict]:
        models = []
        for row in range(self.model_table.rowCount()):
            display_item = self.model_table.item(row, 0)
            model_item = self.model_table.item(row, 1)
            if not model_item or not model_item.text().strip():
                continue
            display_name = display_item.text().strip() if display_item and display_item.text().strip() else model_item.text().strip()
            models.append({
                "id": display_item.data(256) if display_item and display_item.data(256) else f"mdl_{uuid4().hex}",
                "source_id": source_id,
                "display_name": display_name,
                "model_id": model_item.text().strip(),
                "default_size": self._table_text(row, 2) or "1024x1024",
                "default_quality": self._table_text(row, 3) or "standard",
                "default_n": self._safe_int(self._table_text(row, 4), 1),
                "sort_order": row,
                "is_active": 1,
            })
        return models

    def _safe_int(self, value: str, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _table_text(self, row: int, col: int) -> str:
        item = self.model_table.item(row, col)
        return item.text().strip() if item else ""

    def _parse_headers(self, raw_headers) -> dict[str, str]:
        if not raw_headers:
            return {}
        if isinstance(raw_headers, dict):
            return {str(key): str(value) for key, value in raw_headers.items()}
        try:
            parsed = json.loads(raw_headers)
        except (TypeError, json.JSONDecodeError):
            return {}
        return {str(key): str(value) for key, value in parsed.items()} if isinstance(parsed, dict) else {}

    def _build_generation_url_preview(self, platform_id: str, base_url: str) -> str:
        adapter_key = "openai" if platform_id == "openai_images" else platform_id
        adapter = get_adapter(adapter_key)
        resolved_base_url = (base_url or constants.PLATFORM_DEFAULTS.get(platform_id, {}).get("api_base_url", "")).strip()
        if not adapter or not resolved_base_url:
            return "实际请求: -"
        if adapter_key == "custom":
            return f"实际请求: {resolved_base_url}（完整地址，不追加路径）"
        return f"实际请求: {adapter.build_url(resolved_base_url, '/images/generations')}"

    def _update_url_preview(self, platform_id: str):
        self.url_preview.setText(self._build_generation_url_preview(platform_id, self.url_input.text()))

    def _on_interface_type_changed(self, index: int):
        iface = self.interface_combo.currentData()
        is_custom = iface == "custom"
        row = self._response_format_row

        if is_custom:
            if not self._rfm_added:
                self.source_grid.addWidget(self.response_format_label, row, 0)
                self.source_grid.addWidget(self.response_format_combo, row, 1)
                self._rfm_added = True
            self.response_format_label.setVisible(True)
            self.response_format_combo.setVisible(True)
        else:
            if self._rfm_added:
                self.source_grid.removeWidget(self.response_format_label)
                self.source_grid.removeWidget(self.response_format_combo)
                self._rfm_added = False
            self.response_format_label.setVisible(False)
            self.response_format_combo.setVisible(False)

        if is_custom:
            self.url_input.setPlaceholderText("请输入完整 API 地址，例如 https://api.example.com/v1/image_generation")
        else:
            self.url_input.setPlaceholderText("https://example.com/v1")
        self._update_url_preview(iface or "openai_images")

    def _build_config_from_fields(self, platform_id: str, platform_name: str) -> PlatformConfig | None:
        return PlatformConfig(
            id=platform_id,
            name=platform_name,
            api_base_url=self.url_input.text().strip(),
            api_key=self.key_input.text(),
            custom_headers=self._headers_from_table(),
            model_name="",
            auth_preset=self.auth_combo.currentData() or "openai",
            interface_type=self.interface_combo.currentData() or "openai_images",
            proxy=self.proxy_input.text().strip() if self.proxy_check.isChecked() else None,
            is_active=self.active_check.isChecked(),
        )


    def _build_backup_payload(self) -> dict:
        self._capture_current_source()
        return {
            "version": 1,
            "sources": [
                {
                    key: value
                    for key, value in source.items()
                    if key not in {"api_key", "api_key_encrypted"}
                }
                for source in self.sources
            ],
            "models_by_source": self.models_by_source,
        }

    def _backup_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "备份配置", "imageMaker-sources.json", "JSON 文件 (*.json)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as file:
            json.dump(self._build_backup_payload(), file, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "备份完成", "配置已导出，API Key 不会包含在备份中。")

    def _reset_config(self):
        ok = QMessageBox.question(self, "重置配置", "确定清空当前来源和模型配置吗？历史图片不会删除。")
        if ok != QMessageBox.Yes:
            return
        self.sources = []
        self.models_by_source = {}
        self.current_source_id = None
        self._ensure_draft_source()
        self._refresh_source_list()

    def _save(self):
        self._capture_current_source()
        if not self.db:
            QMessageBox.warning(self, "保存失败", "数据库尚未初始化，无法保存配置")
            return
        from src.config.event_loop import run_async
        existing_sources = run_async(self.db.get_sources())
        existing_ids = {source["id"] for source in existing_sources}
        current_ids = {source["id"] for source in self.sources}
        for source_id in existing_ids - current_ids:
            run_async(self.db.delete_source(source_id))
        for source in self.sources:
            saved_source = dict(source)
            api_key = saved_source.pop("api_key", "")
            saved_source["api_key_encrypted"] = encryption.encrypt(api_key) if api_key else source.get("api_key_encrypted")
            run_async(self.db.save_source(saved_source))
            existing_models = run_async(self.db.get_source_models(source["id"]))
            existing_model_ids = {model["id"] for model in existing_models}
            current_models = self.models_by_source.get(source["id"], [])
            current_model_ids = {model["id"] for model in current_models}
            for model_id in existing_model_ids - current_model_ids:
                run_async(self.db.delete_source_model(model_id))
            for model in current_models:
                run_async(self.db.save_source_model(model))
        QMessageBox.information(self, "保存成功", "来源与模型配置已保存")
        self.accept()

    def _get_migration_manager(self):
        """Get or create MigrationManager instance"""
        if not hasattr(self, 'migration_manager') or self.migration_manager is None:
            from src.managers.migration_manager import MigrationManager
            from src.managers.history_manager import HistoryManager
            from src.managers.prompt_manager import PromptManager
            history_mgr = HistoryManager(self.db)
            prompt_mgr = PromptManager(self.db)
            # KeyVault would be needed for key backup, using a placeholder
            key_vault = MagicMock() if hasattr(self, 'key_vault') else None
            self.migration_manager = MigrationManager(self.db, history_mgr, prompt_mgr, key_vault)
        return self.migration_manager

    def _on_export(self):
        """Handle export button click"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出数据", "imageMaker-backup.imbackup", "备份文件 (*.imbackup)"
        )
        if not path:
            return

        from src.managers.migration_manager import ExportOptions
        from src.config.event_loop import run_async

        options = ExportOptions(
            include_history=True,
            include_templates=True,
            include_sources=True,
            include_settings=True,
            include_keys=False
        )
        try:
            run_async(self._get_migration_manager().export(path, options))
            QMessageBox.information(self, "导出成功", f"数据已导出到:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出时出错:\n{str(e)}")

    def _on_import(self):
        """Handle import button click"""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入数据", "", "备份文件 (*.imbackup);;所有文件 (*.*)"
        )
        if not path:
            return

        from src.managers.migration_manager import ImportOptions, ImportResult
        from src.config.event_loop import run_async

        preview = run_async(self._get_migration_manager().preview(path))
        msg = QMessageBox(self)
        msg.setWindowTitle("导入预览")
        msg.setText(f"备份文件内容:\n\n历史记录: {preview.history_count} 条\n"
                   f"模板: {preview.template_count} 条\n"
                   f"来源: {preview.source_count} 个\n"
                   f"密钥: {'有' if preview.has_keys else '无'}\n\n确定要导入吗？")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if msg.exec() != QMessageBox.Yes:
            return

        options = ImportOptions(
            include_history=True,
            include_templates=True,
            include_sources=True,
            include_settings=True,
            include_keys=False,
            conflict_mode="keep"
        )
        try:
            result = run_async(self._get_migration_manager().import_data(path, options))
            QMessageBox.information(self, "导入成功",
                f"导入完成:\n\n历史记录: {result.imported_history} 条\n"
                f"模板: {result.imported_templates} 条\n"
                f"来源: {result.imported_sources} 个")
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"导入时出错:\n{str(e)}")

    def _on_export_keys(self):
        """Handle export keys button click"""
        QMessageBox.information(self, "导出密钥", "密钥导出功能开发中")

    def _on_import_keys(self):
        """Handle import keys button click"""
        QMessageBox.information(self, "导入密钥", "密钥导入功能开发中")
