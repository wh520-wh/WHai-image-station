from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.widgets.components.prompt_card import PromptCard
from src.widgets.theme import COLORS, RADIUS, app_font, apply_card_style, button_style, label_style, make_empty_state_label, scroll_area_style
from src.config.event_loop import run_async


class PromptPanel(QWidget):
    template_selected = Signal(dict)
    template_used = Signal(dict)
    template_deleted = Signal(int)
    collapse_changed = Signal(bool)

    def __init__(self, prompt_manager, parent=None):
        super().__init__(parent)
        self.prompt_manager = prompt_manager
        self.templates: list[dict] = []
        self.categories: list[str] = []
        self.current_category: str | None = None
        self.is_collapsed = False
        self._setup_ui()

    def _setup_ui(self):
        apply_card_style(self)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        title_layout = QHBoxLayout()
        title = QLabel("提示词库")
        title.setFont(app_font(13, QFont.Bold))
        title.setStyleSheet(label_style("title"))
        title_layout.addWidget(title)
        title_layout.addStretch()

        self.collapse_btn = QPushButton("◀")
        self.collapse_btn.setFixedSize(24, 24)
        self.collapse_btn.setToolTip("收起提示词库")
        self.collapse_btn.setStyleSheet(
            button_style("ghost") + "QPushButton { border-radius: 6px; font-size: 10px; padding: 0; }"
        )
        self.collapse_btn.clicked.connect(self._toggle_collapse)
        title_layout.addWidget(self.collapse_btn)

        self.add_btn = QPushButton("+")
        self.add_btn.setFixedSize(30, 30)
        self.add_btn.setToolTip("新增模板")
        self.add_btn.setStyleSheet(button_style("primary") + f"QPushButton {{ padding: 0; border-radius: {RADIUS['card']}px; font-size: 18px; }}")
        self.add_btn.clicked.connect(self._add_template)
        title_layout.addWidget(self.add_btn)
        main_layout.addLayout(title_layout)

        self.category_scroll = QScrollArea()
        self.category_scroll.setFixedHeight(38)
        self.category_scroll.setWidgetResizable(True)
        self.category_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.category_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.category_scroll.setStyleSheet(scroll_area_style())

        self.category_widget = QWidget()
        self.category_layout = QHBoxLayout(self.category_widget)
        self.category_layout.setContentsMargins(0, 0, 0, 0)
        self.category_layout.setSpacing(8)
        self.category_scroll.setWidget(self.category_widget)
        main_layout.addWidget(self.category_scroll)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(scroll_area_style())
        self.template_container = QWidget()
        self.template_layout = QVBoxLayout(self.template_container)
        self.template_layout.setContentsMargins(0, 0, 0, 0)
        self.template_layout.setSpacing(12)
        self.scroll_area.setWidget(self.template_container)
        main_layout.addWidget(self.scroll_area)

        self.expand_btn = QPushButton("▶")
        self.expand_btn.setFixedSize(30, 30)
        self.expand_btn.setToolTip("展开提示词库")
        self.expand_btn.setStyleSheet(
            button_style("primary")
            + f"QPushButton {{ padding: 0; border-radius: {RADIUS['card']}px; font-size: 14px; }}"
        )
        self.expand_btn.clicked.connect(self._toggle_collapse)
        self.expand_btn.setVisible(False)
        main_layout.addWidget(self.expand_btn, alignment=Qt.AlignCenter)
        main_layout.addStretch()

    def _toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
        if self.is_collapsed:
            self.category_scroll.setVisible(False)
            self.scroll_area.setVisible(False)
            self.add_btn.setVisible(False)
            self.collapse_btn.setVisible(False)
            self.expand_btn.setVisible(True)
            self.setMaximumWidth(44)
            self.setMinimumWidth(44)
        else:
            self.category_scroll.setVisible(True)
            self.scroll_area.setVisible(True)
            self.add_btn.setVisible(True)
            self.collapse_btn.setVisible(True)
            self.expand_btn.setVisible(False)
            self.setMaximumWidth(260)
            self.setMinimumWidth(180)
        self.collapse_changed.emit(self.is_collapsed)

    async def load_templates(self):
        self.templates = await self.prompt_manager.get_templates(self.current_category)
        self.categories = await self.prompt_manager.get_categories()
        self._update_category_widget()
        self._update_template_list()

    def _update_category_widget(self):
        while self.category_layout.count():
            item = self.category_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        all_btn = QPushButton("全部")
        all_btn.setCheckable(True)
        all_btn.setChecked(self.current_category is None)
        all_btn.setStyleSheet(self._get_category_style(self.current_category is None))
        all_btn.clicked.connect(lambda: self._select_category(None))
        self.category_layout.addWidget(all_btn)

        for category in self.categories:
            btn = QPushButton(category)
            btn.setCheckable(True)
            btn.setChecked(self.current_category == category)
            btn.setStyleSheet(self._get_category_style(self.current_category == category))
            btn.clicked.connect(lambda checked, c=category: self._select_category(c if checked else None))
            self.category_layout.addWidget(btn)

        self.category_layout.addStretch()

    def _get_category_style(self, checked: bool) -> str:
        if checked:
            return f"""
            QPushButton {{
                background: {COLORS['primary']};
                color: {COLORS['panel']};
                border: none;
                border-radius: {RADIUS['control']}px;
                padding: 6px 13px;
                font-size: 11px;
                font-weight: 700;
            }}
            """
        return f"""
        QPushButton {{
            background: {COLORS['panel_alt']};
            color: {COLORS['muted']};
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['control']}px;
            padding: 6px 13px;
            font-size: 11px;
        }}
        QPushButton:hover {{
            background: {COLORS['primary_soft']};
            color: {COLORS['primary_text']};
            border-color: {COLORS['primary']};
        }}
        """

    def _select_category(self, category: str | None):
        self.current_category = category
        run_async(self.load_templates())

    def _update_template_list(self):
        while self.template_layout.count():
            item = self.template_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.templates:
            empty = make_empty_state_label("暂无提示词模板\n保存常用 Prompt 后会显示在这里")
            self.template_layout.addWidget(empty)
        else:
            for template in self.templates:
                card = PromptCard(template)
                card.clicked.connect(self.template_selected.emit)
                card.use_template.connect(self.template_used.emit)
                card.delete_template.connect(self.template_deleted.emit)
                self.template_layout.addWidget(card)
        self.template_layout.addStretch()

    def _add_template(self):
        from src.models.prompt import PromptTemplate

        template = PromptTemplate()
        template.name = f"新模板 {len(self.templates) + 1}"
        template.category = "默认"
        run_async(self.prompt_manager.save_template(template.to_dict()))
        run_async(self.load_templates())
