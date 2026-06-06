import os
import sys
from PySide6.QtWidgets import QApplication, QTextEdit, QVBoxLayout
from PySide6.QtGui import QTextOption
from src.widgets.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_app = QApplication.instance() or QApplication(sys.argv)


def test_main_window_splitter_has_correct_configuration():
    window = MainWindow(None)
    splitter = window.main_splitter
    # Verify widget count
    assert splitter.count() == 3
    # Verify each widget slot has a minimum width set
    assert window.prompt_panel.minimumWidth() == 180
    assert window.history_panel.minimumWidth() == 300
    assert window.history_panel.maximumWidth() == 460
    # Verify collapsible state: prompt panel (index 0) is collapsible
    assert splitter.isCollapsible(0) is True
    window.deleteLater()


def test_main_window_prompt_panel_is_collapsible():
    window = MainWindow(None)
    assert window.main_splitter.isCollapsible(0) is True
    window.deleteLater()


def test_main_window_history_panel_has_max_width():
    window = MainWindow(None)
    assert window.history_panel.maximumWidth() == 460
    assert window.history_panel.minimumWidth() == 300
    window.deleteLater()


def test_on_prompt_panel_collapse_changed_behavior():
    window = MainWindow(None)
    # Verify collapse
    window._on_prompt_panel_collapse_changed(True)
    assert window.prompt_panel.maximumWidth() == 44
    assert window.prompt_panel.minimumWidth() == 44
    # Verify expand
    window._on_prompt_panel_collapse_changed(False)
    assert window.prompt_panel.maximumWidth() == 260
    assert window.prompt_panel.minimumWidth() == 180
    window.deleteLater()


from src.widgets.prompt_panel import PromptPanel


def test_prompt_panel_default_is_not_collapsed():
    panel = PromptPanel(None)
    assert panel.is_collapsed is False
    assert panel.expand_btn.isHidden() is True
    assert panel.collapse_btn.isHidden() is False


def test_prompt_panel_collapse_hides_content():
    panel = PromptPanel(None)
    panel._toggle_collapse()
    assert panel.is_collapsed is True
    assert panel.scroll_area.isHidden() is True
    assert panel.category_scroll.isHidden() is True
    assert panel.expand_btn.isHidden() is False
    assert panel.collapse_btn.isHidden() is True


def test_prompt_panel_expand_restores_content():
    panel = PromptPanel(None)
    panel._toggle_collapse()
    panel._toggle_collapse()
    assert panel.is_collapsed is False
    assert panel.scroll_area.isHidden() is False
    assert panel.category_scroll.isHidden() is False
    assert panel.expand_btn.isHidden() is True
    assert panel.collapse_btn.isHidden() is False


from PySide6.QtWidgets import QScrollArea, QSizePolicy
from src.widgets.generation_panel import GenerationPanel


def test_generation_panel_param_combos_use_minimum_expanding():
    panel = GenerationPanel(None)
    assert panel.size_combo.sizePolicy().horizontalPolicy() == QSizePolicy.MinimumExpanding
    assert panel.quality_combo.sizePolicy().horizontalPolicy() == QSizePolicy.MinimumExpanding
    assert panel.count_combo.sizePolicy().horizontalPolicy() == QSizePolicy.MinimumExpanding
    assert panel.seed_input.sizePolicy().horizontalPolicy() == QSizePolicy.MinimumExpanding


def test_generation_panel_param_combos_have_correct_minimum_width():
    panel = GenerationPanel(None)
    assert panel.size_combo.minimumWidth() == 90
    assert panel.quality_combo.minimumWidth() == 90
    assert panel.count_combo.minimumWidth() == 60
    assert panel.seed_input.minimumWidth() == 80


def test_generation_panel_selector_controls_are_responsive():
    panel = GenerationPanel(None)

    assert hasattr(panel, "selector_control_layout")
    assert hasattr(panel, "selector_action_layout")
    assert panel.source_combo.minimumWidth() >= 180
    assert panel.model_combo.minimumWidth() >= 190
    assert panel.source_combo.maximumWidth() > 1000
    assert panel.model_combo.maximumWidth() > 1000
    assert panel.source_combo.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert panel.model_combo.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding


def test_generation_panel_params_are_split_into_readable_rows():
    panel = GenerationPanel(None)

    assert hasattr(panel, "primary_params_layout")
    assert hasattr(panel, "secondary_params_layout")
    assert panel.primary_params_layout.count() >= 3
    assert panel.secondary_params_layout.count() >= 2


def test_generation_panel_queue_uses_vertical_list_layout():
    panel = GenerationPanel(None)

    assert isinstance(panel.queue_container, QVBoxLayout)
    assert panel.queue_container.spacing() >= 10


def test_generation_panel_queue_cards_expand_horizontally():
    class FakeQueueManager:
        def clear_completed(self):
            pass

        def get_queue_info(self):
            return {"waiting": 1, "generating": 0}

        def get_task_snapshots(self, limit):
            return [
                {
                    "task_id": "task-1",
                    "id": "task-1",
                    "status": "WAITING",
                    "prompt": "测试队列卡片宽度",
                    "platform_id": "openai",
                }
            ]

    panel = GenerationPanel(FakeQueueManager())
    panel.refresh_queue()
    card = panel.queue_container.itemAt(0).widget()

    assert card.minimumWidth() == 0
    assert card.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding


def test_generation_panel_uses_scroll_area_for_workbench_content():
    panel = GenerationPanel(None)

    assert isinstance(panel.scroll_area, QScrollArea)
    assert panel.scroll_area.widgetResizable() is True
    assert panel.scroll_area.widget() is panel.content_widget
    assert panel.prompt_edit.parentWidget() is not panel
    parent = panel.queue_empty_label.parentWidget()
    ancestors = []
    while parent is not None:
        ancestors.append(parent)
        parent = parent.parentWidget()
    assert panel.content_widget in ancestors


from src.widgets.history_panel import HistoryPanel


def test_history_panel_has_single_toolbar_frame():
    panel = HistoryPanel(None)
    assert hasattr(panel, 'toolbar_frame')
    assert hasattr(panel, 'search_toolbar_frame')
    assert hasattr(panel, 'filter_toolbar_frame')
    assert hasattr(panel, 'sort_toolbar_frame')
    assert hasattr(panel, 'action_toolbar_frame')
    assert panel.toolbar_frame.minimumHeight() == 154


def test_history_panel_toolbar_contains_search_and_actions():
    panel = HistoryPanel(None)
    search_layout = panel.search_toolbar_frame.layout()
    filter_layout = panel.filter_toolbar_frame.layout()
    sort_layout = panel.sort_toolbar_frame.layout()
    action_layout = panel.action_toolbar_frame.layout()
    search_widgets = [
        search_layout.itemAt(i).widget()
        for i in range(search_layout.count())
        if search_layout.itemAt(i).widget()
    ]
    filter_widgets = [
        filter_layout.itemAt(i).widget()
        for i in range(filter_layout.count())
        if filter_layout.itemAt(i).widget()
    ]
    sort_widgets = [
        sort_layout.itemAt(i).widget()
        for i in range(sort_layout.count())
        if sort_layout.itemAt(i).widget()
    ]
    action_widgets = [
        action_layout.itemAt(i).widget()
        for i in range(action_layout.count())
        if action_layout.itemAt(i).widget()
    ]
    assert panel.search_input in search_widgets
    assert panel.platform_filter in filter_widgets
    assert panel.sort_combo in sort_widgets
    assert panel.grid_mode_btn in action_widgets
    assert panel.clear_btn in action_widgets


def test_history_panel_toolbar_prevents_visible_text_clipping():
    panel = HistoryPanel(None)

    assert panel.grid_mode_btn.text() == "网格"
    assert panel.sort_combo.minimumWidth() >= 118
    assert panel.date_filter.minimumWidth() >= 72
    assert panel.platform_filter.minimumWidth() >= 88
    assert panel.search_input.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert panel.sort_combo.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert panel.title_layout.spacing() >= 8
    assert panel.action_toolbar_frame.layout().contentsMargins().right() >= 8


def test_history_panel_sort_filter_uses_own_row_to_avoid_right_clipping():
    panel = HistoryPanel(None)

    assert hasattr(panel, "sort_toolbar_frame")
    assert panel.filter_toolbar_frame.layout().count() <= 3
    assert panel.sort_toolbar_frame.layout().itemAt(0).widget() is panel.sort_combo
    assert panel.sort_combo.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding


def test_history_panel_has_no_diagnostic_scroll():
    panel = HistoryPanel(None)
    assert not hasattr(panel, 'diagnostic_scroll')


def test_generation_panel_has_diagnostic_history_container():
    panel = GenerationPanel(None)
    assert hasattr(panel, 'diagnostic_history_container')
    assert panel.diagnostic_history_container.isVisible() is False


def test_generation_panel_show_diagnostic_history_renders_records():
    panel = GenerationPanel(None)
    panel.show()  # must be a shown window for isVisible() to work
    records = [
        {"prompt": "test prompt", "error": "timeout", "diagnostic": {"error": "timeout"}},
    ]
    panel.show_diagnostic_history(records)
    assert panel.diagnostic_history_container.isVisible() is True
    assert panel.diagnostic_history_layout.count() >= 1
    panel.hide()


def test_generation_panel_diagnostic_view_keeps_full_copyable_text():
    panel = GenerationPanel(None)
    diagnostic = {
        "request_url": "https://relay.example/codex/v1/images/generations",
        "payload": {"prompt": "x" * 220, "model": "gpt-image-2"},
        "error": "timeout " * 80,
    }

    panel.update_diagnostic(diagnostic, expand=True)

    assert isinstance(panel.diagnostic_label, QTextEdit)
    assert panel.diagnostic_label.isReadOnly() is True
    assert panel.diagnostic_label.lineWrapMode() == QTextEdit.WidgetWidth
    assert panel.diagnostic_label.wordWrapMode() == QTextOption.WrapAnywhere
    assert panel.diagnostic_label.toPlainText() == panel._diagnostic_text()
