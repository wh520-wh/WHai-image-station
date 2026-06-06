# tests/widgets/test_history_panel_batch.py
import pytest
from PySide6.QtWidgets import QApplication
from src.widgets.history_panel import HistoryPanel
from src.widgets.batch_ops_bar import BatchOpsBar

class TestHistoryPanelBatch:
    @pytest.fixture
    def app(self):
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app

    def test_batch_mode_attribute_exists(self, app):
        """HistoryPanel should have _batch_mode attribute"""
        panel = HistoryPanel(None)
        assert hasattr(panel, '_batch_mode'), "HistoryPanel should have _batch_mode attribute"
        assert panel._batch_mode == False, "Batch mode should be False by default"

    def test_selected_ids_attribute_exists(self, app):
        """HistoryPanel should have _selected_ids attribute"""
        panel = HistoryPanel(None)
        assert hasattr(panel, '_selected_ids'), "HistoryPanel should have _selected_ids attribute"
        assert panel._selected_ids == set(), "Selected IDs should be empty set by default"

    def test_batch_selection_changed_signal_exists(self, app):
        """HistoryPanel should emit batch_selection_changed signal"""
        panel = HistoryPanel(None)
        assert hasattr(panel, 'batch_selection_changed'), "HistoryPanel should have batch_selection_changed signal"

    def test_batch_ops_bar_exists(self, app):
        """BatchOpsBar should exist and have required signals"""
        bar = BatchOpsBar()
        assert hasattr(bar, 'delete_requested'), "BatchOpsBar should have delete_requested signal"
        assert hasattr(bar, 'move_requested'), "BatchOpsBar should have move_requested signal"
        assert hasattr(bar, 'export_requested'), "BatchOpsBar should have export_requested signal"
        assert hasattr(bar, 'tag_requested'), "BatchOpsBar should have tag_requested signal"
        assert hasattr(bar, 'clear_selection_requested'), "BatchOpsBar should have clear_selection_requested signal"

    def test_batch_ops_bar_update_count(self, app):
        """BatchOpsBar should update count label when update_count is called"""
        bar = BatchOpsBar()
        bar.update_count(5)
        assert "已选择 5 项" in bar.count_label.text()

    def test_toggle_batch_mode(self, app):
        """HistoryPanel should toggle batch mode"""
        panel = HistoryPanel(None)
        panel.toggle_batch_mode()
        assert panel._batch_mode == True, "Batch mode should be True after toggle"
        panel.toggle_batch_mode()
        assert panel._batch_mode == False, "Batch mode should be False after second toggle"

    def test_enter_batch_mode(self, app):
        """HistoryPanel should enter batch mode"""
        panel = HistoryPanel(None)
        panel.enter_batch_mode()
        assert panel._batch_mode == True, "Batch mode should be True"

    def test_exit_batch_mode(self, app):
        """HistoryPanel should exit batch mode and clear selection"""
        panel = HistoryPanel(None)
        panel.enter_batch_mode()
        panel._selected_ids.add("test_id")
        panel.exit_batch_mode()
        assert panel._batch_mode == False, "Batch mode should be False"
        assert len(panel._selected_ids) == 0, "Selected IDs should be cleared"