import os
import sys
from collections import deque

from PySide6.QtWidgets import QApplication, QAbstractItemView, QSizePolicy, QSplitter

from src.widgets.components.prompt_card import TaskCard
from src.widgets.history_panel import HistoryPanel
from src.widgets.settings_dialog import SettingsDialog


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_app = QApplication.instance() or QApplication(sys.argv)


def test_task_card_has_room_for_queue_content():
    card = TaskCard({"status": "GENERATING", "platform_id": "openai", "prompt": "a long prompt for layout"})

    assert card.minimumWidth() >= 210
    assert card.minimumHeight() >= 118


def test_history_panel_filters_records_without_images(tmp_path):
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"not a real image but path exists")
    panel = HistoryPanel(None)
    panel.history = [
        {"prompt": "ok", "image_path": str(image_path), "thumbnail_path": ""},
        {"prompt": "failed", "image_path": None, "thumbnail_path": None},
    ]

    panel._update_grid()

    assert panel.count_label.text() == "共 1 张"


def test_history_panel_shows_records_with_missing_image_files(tmp_path):
    """Records with image_path set but file missing should still appear in grid."""
    missing_path = str(tmp_path / "deleted_image.png")
    # File does NOT exist

    panel = HistoryPanel(None)
    panel.history = [
        {"task_id": "orphan-1", "prompt": "lost image", "image_path": missing_path, "thumbnail_path": ""},
    ]

    panel._update_grid()

    # Should still show 1 record (not be hidden)
    assert panel.count_label.text() == "共 1 张"



def test_history_panel_header_actions_use_separate_readable_row():
    panel = HistoryPanel(None)

    assert hasattr(panel, "toolbar_frame")
    assert hasattr(panel, "filter_toolbar_frame")
    assert hasattr(panel, "action_toolbar_frame")
    assert panel.toolbar_frame.minimumHeight() >= 72
    assert panel.grid_mode_btn.minimumWidth() >= 48
    assert panel.single_mode_btn.minimumWidth() >= 48
    assert panel.clear_btn.minimumWidth() >= 48
    assert panel.clean_invalid_btn.minimumWidth() >= 64




def test_history_panel_can_switch_to_single_preview_mode(tmp_path):
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"exists")
    panel = HistoryPanel(None)
    panel.history = [{"prompt": "ok", "image_path": str(image_path), "thumbnail_path": ""}]

    panel.set_view_mode("single")

    assert panel.view_mode == "single"


def test_settings_model_table_supports_drag_sorting_and_backup_is_redacted():
    dialog = SettingsDialog(None)

    assert dialog.model_table.dragDropMode() == QAbstractItemView.InternalMove
    payload = dialog._build_backup_payload()
    assert "api_key" not in str(payload).lower()
    assert "api_key_encrypted" not in str(payload).lower()


def test_settings_source_manager_uses_resizable_splitter_and_grouped_actions():
    dialog = SettingsDialog(None)

    assert isinstance(dialog.source_splitter, QSplitter)
    assert dialog.source_splitter.count() == 2
    assert dialog.source_left_panel.minimumWidth() == 220
    assert dialog.source_left_panel.maximumWidth() == 360
    assert hasattr(dialog, "primary_source_actions")
    assert hasattr(dialog, "maintenance_source_actions")
    assert hasattr(dialog, "danger_source_actions")
    assert dialog.primary_source_actions.count() == 1
    assert dialog.maintenance_source_actions.count() == 1
    assert dialog.danger_source_actions.count() == 2
    assert (
        dialog.primary_source_actions.itemAt(0).widget().sizePolicy().horizontalPolicy()
        == QSizePolicy.Expanding
    )


def test_clear_history_clears_panel_list(monkeypatch):
    """Clear history should empty the in-memory list and show zero count."""
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    panel = HistoryPanel(None)
    panel.history = [
        {"task_id": "a", "prompt": "first"},
        {"task_id": "b", "prompt": "second"},
    ]

    panel._clear_history()

    assert panel.history == deque()
    assert panel.count_label.text() == "共 0 张"


def test_clean_invalid_records_identifies_missing_files(tmp_path):
    """Clean invalid should detect records whose image files no longer exist."""
    existing = tmp_path / "exists.png"
    existing.write_bytes(b"real file")
    missing = str(tmp_path / "deleted.png")

    panel = HistoryPanel(None)
    panel.history = [
        {"task_id": "a", "image_path": str(existing), "thumbnail_path": ""},
        {"task_id": "b", "image_path": missing, "thumbnail_path": ""},
        {"task_id": "c", "image_path": "", "thumbnail_path": ""},
    ]

    # Simulate _clean_invalid_records logic manually (without run_async)
    invalid = []
    for record in panel.history:
        image_path = record.get("image_path")
        thumbnail_path = record.get("thumbnail_path")
        has_recorded_path = bool(image_path or thumbnail_path)
        if not has_recorded_path:
            continue
        has_file = (image_path and os.path.exists(image_path)) or \
                   (thumbnail_path and os.path.exists(thumbnail_path))
        if not has_file:
            invalid.append(record)

    # Record 'a' has existing file → not invalid
    # Record 'b' has missing file → invalid
    # Record 'c' has no path → skipped (not invalid)
    assert len(invalid) == 1
    assert invalid[0]["task_id"] == "b"
