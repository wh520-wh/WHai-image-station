from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from src.adapters.errors import Category, Diagnostic
from src.widgets.theme import COLORS, RADIUS, SPACING, app_font, apply_card_style, button_style, label_style


CATEGORY_LABELS: dict[Category, str] = {
    Category.AUTH: "鉴权失败",
    Category.RATE_LIMIT: "请求频率超限",
    Category.NETWORK: "网络问题",
    Category.SERVER: "服务器错误",
    Category.BAD_REQUEST: "请求参数错误",
    Category.CONTENT: "响应内容错误",
    Category.UNKNOWN: "未知错误",
}


CATEGORY_COLORS: dict[Category, str] = {
    Category.AUTH: "#d23f3f",
    Category.RATE_LIMIT: "#e8a93b",
    Category.NETWORK: "#e8a93b",
    Category.SERVER: "#d23f3f",
    Category.BAD_REQUEST: "#e8a93b",
    Category.CONTENT: "#4a8fbf",
    Category.UNKNOWN: "#888888",
}


class DiagnosticCard(QFrame):
    """Compact card showing a structured Diagnostic: badge + fields + hint + collapsible original + copy."""

    def __init__(self, diagnostic: Diagnostic | None, parent: QWidget | None = None):
        super().__init__(parent)
        self._diagnostic = diagnostic
        self._setup_ui()
        self._render()

    def _setup_ui(self):
        apply_card_style(self, COLORS["panel_alt"])
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"])
        layout.setSpacing(SPACING["xs"])

        header = QHBoxLayout()
        self.badge_label = QLabel()
        self.badge_label.setFont(app_font(10, QFont.Bold))
        header.addWidget(self.badge_label)
        header.addStretch()

        self.copy_button = QPushButton("📋 复制诊断")
        self.copy_button.setStyleSheet(button_style("ghost"))
        self.copy_button.clicked.connect(self._on_copy)
        header.addWidget(self.copy_button)
        layout.addLayout(header)

        self.field_table = QGridLayout()
        self.field_table.setHorizontalSpacing(SPACING["sm"])
        self.field_table.setVerticalSpacing(2)
        layout.addLayout(self.field_table)
        self.field_rows: list[QWidget] = []

        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.hint_label.setStyleSheet(f"color: {COLORS['info']}; font-size: 11px;")
        layout.addWidget(self.hint_label)

        original_header = QHBoxLayout()
        self.original_toggle = QPushButton("展开原文")
        self.original_toggle.setStyleSheet(button_style("ghost"))
        self.original_toggle.clicked.connect(self.toggle_original)
        original_header.addWidget(self.original_toggle)
        original_header.addStretch()
        layout.addLayout(original_header)

        self.original_text = QLabel()
        self.original_text.setWordWrap(True)
        self.original_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.original_text.setStyleSheet(f"color: {COLORS['muted']}; font-size: 10px;")
        self.original_text.setVisible(False)
        layout.addWidget(self.original_text)

    def _render(self):
        if self._diagnostic is None:
            self.setVisible(False)
            return
        diag = self._diagnostic
        category = diag.category
        badge_text = CATEGORY_LABELS.get(category, category.value)
        color = CATEGORY_COLORS.get(category, COLORS.get("muted", "#888"))
        self.badge_label.setText(badge_text)
        self.badge_label.setStyleSheet(
            f"color: white; background: {color}; padding: 4px 10px; border-radius: {RADIUS['compact']}px;"
        )

        for row in self.field_rows:
            row.setParent(None)
            row.deleteLater()
        self.field_rows = []

        for index, field in enumerate(diag.fields):
            row = QFrame(self)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(SPACING["sm"])
            name_lbl = QLabel(f"{field.name}:")
            name_lbl.setStyleSheet(label_style("muted"))
            name_lbl.setMinimumWidth(96)
            display_value = "***" if field.redact else field.value
            value_lbl = QLabel(display_value)
            value_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
            issue_lbl = QLabel(f"— {field.issue}" if field.issue else "")
            issue_lbl.setStyleSheet(f"color: {COLORS['subtle']}; font-size: 11px;")
            row_layout.addWidget(name_lbl)
            row_layout.addWidget(value_lbl, 1)
            row_layout.addWidget(issue_lbl, 2)
            self.field_table.addWidget(row, index, 0)
            self.field_rows.append(row)

        if diag.hint:
            self.hint_label.setText(diag.hint)
            self.hint_label.setVisible(True)
        else:
            self.hint_label.setVisible(False)

        self.original_text.setText(diag.original or "")
        self.setVisible(True)

    def toggle_original(self):
        self.original_text.setVisible(not self.original_text.isVisible())
        self.original_toggle.setText("收起原文" if self.original_text.isVisible() else "展开原文")

    def _on_copy(self):
        if not self._diagnostic:
            return
        QApplication.clipboard().setText(
            json.dumps(self._diagnostic.to_dict(), ensure_ascii=False, indent=2)
        )
