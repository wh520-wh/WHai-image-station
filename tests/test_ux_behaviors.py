import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.managers.queue_manager import QueueManager
from src.widgets.generation_panel import GenerationPanel
from src.widgets.generation_panel import normalize_size_value
from src.widgets.history_panel import HistoryPanel
from src.widgets.theme import COLORS


_app = QApplication.instance() or QApplication(sys.argv)


def test_generation_panel_blocks_generation_until_platform_configured():
    panel = GenerationPanel(QueueManager())
    emitted = []
    panel.generate_signal.connect(lambda task: emitted.append(task))
    panel.prompt_edit.setPlainText("a cinematic cat")

    assert panel._generate() is False
    assert emitted == []
    assert "来源" in panel.config_hint_label.text()
    assert panel.generate_btn.isEnabled() is False


def test_generation_panel_shows_openai_model_missing_message():
    panel = GenerationPanel(QueueManager())
    panel.set_platform_config_statuses(
        {"openai": False},
        {"openai": "请先在 OpenAI 设置中填写模型名，再开始生成。"},
    )

    assert "模型名" in panel.config_hint_label.text()
    assert panel.generate_btn.isEnabled() is False


def test_generation_panel_allows_generation_after_platform_configured():
    panel = GenerationPanel(QueueManager())
    emitted = []
    panel.generate_signal.connect(lambda task: emitted.append(task))
    panel.current_source_id = "src_test"
    panel.current_model_id = "mdl_test"
    panel._update_config_state_ui()
    panel.prompt_edit.setPlainText("a cinematic cat")

    assert panel._generate() is True
    assert emitted[0]["prompt"] == "a cinematic cat"
    assert panel.generate_btn.isEnabled() is True


def test_generation_panel_normalizes_display_size_to_api_size():
    assert normalize_size_value("1024×1792") == "1024x1792"
    assert normalize_size_value("1024≠1792") == "1024x1792"


def test_generation_panel_accepts_custom_size_value():
    panel = GenerationPanel(QueueManager())
    panel.size_combo.setEditText("1536x1024")

    assert panel.size_combo.isEditable() is True
    assert panel._get_params()["size"] == "1536x1024"


def test_generation_panel_template_apply_accepts_custom_size_value():
    panel = GenerationPanel(QueueManager())

    panel.apply_template({"prompt": "reuse", "negative_prompt": "", "params": {"size": "1536x1024"}})

    assert panel.size_combo.currentText() == "1536x1024"


def test_reference_image_can_be_cleared(tmp_path):
    panel = GenerationPanel(QueueManager())
    panel.reference_image_path = str(tmp_path / "ref.png")
    panel._update_reference_image_ui()

    panel._clear_reference_image()

    assert panel.reference_image_path is None
    assert panel.image_btn.text() == "选择参考图"
    assert panel.clear_image_btn.isVisible() is False


def test_history_panel_reuse_emits_selected_record():
    panel = HistoryPanel(None)
    record = {"prompt": "reuse me", "params": {"size": "1024x1024"}}
    emitted = []
    panel.reuse_requested.connect(lambda value: emitted.append(value))

    panel.request_reuse(record)

    assert emitted == [record]



def test_generation_panel_shows_inline_status_for_generation():
    panel = GenerationPanel(QueueManager())
    panel.current_source_id = "src_test"
    panel.current_model_id = "mdl_test"
    panel._update_config_state_ui()
    panel.prompt_edit.setPlainText("visible feedback")

    assert panel._generate() is True

    assert panel.status_label.isHidden() is False
    assert "\u5df2\u63d0\u4ea4" in panel.status_label.text()


def test_generation_panel_template_apply_shows_feedback():
    panel = GenerationPanel(QueueManager())

    panel.apply_template({"prompt": "reuse", "negative_prompt": "bad", "params": {}})

    assert panel.prompt_edit.toPlainText() == "reuse"
    assert panel.status_label.isHidden() is False
    assert "\u5df2\u586b\u5165" in panel.status_label.text()


def test_generation_panel_status_message_can_show_error():
    panel = GenerationPanel(QueueManager())

    panel.show_status("failure reason", "error")

    assert panel.status_label.isHidden() is False
    assert "failure reason" in panel.status_label.text()
    assert COLORS["danger_soft"] in panel.status_frame.styleSheet()


def test_generation_panel_status_message_is_selectable_and_copyable():
    panel = GenerationPanel(QueueManager())
    panel.show_status("copy this failure", "error")

    assert panel.status_label.textInteractionFlags() & Qt.TextSelectableByMouse

    panel._copy_status_message()

    assert QApplication.clipboard().text() == "copy this failure"


def test_main_window_has_status_bar_method():
    from src.widgets.main_window import MainWindow
    assert hasattr(MainWindow, "_update_status_bar")


def test_main_window_status_bar_uses_currently_selected_source():
    from src.widgets.main_window import MainWindow

    class FakeLabel:
        def __init__(self):
            self.text = ""

        def setText(self, text):
            self.text = text

    class FakeGenerationPanel:
        sources = [
            {"id": "src_old", "name": "DALL·E / OpenAI Compatible", "is_active": 1},
            {"id": "src_new", "name": "当前中转站", "is_active": 1},
        ]
        models_by_source = {
            "src_old": [{"id": "old_model"}],
            "src_new": [{"id": "new_model_1"}, {"id": "new_model_2"}],
        }
        current_source_id = "src_new"

    class FakeQueueManager:
        def get_queue_info(self):
            return {"waiting": 0, "generating": 0, "completed": 0, "failed": 0}

    window = MainWindow.__new__(MainWindow)
    window.generation_panel = FakeGenerationPanel()
    window.queue_manager = FakeQueueManager()
    window.status_source_label = FakeLabel()
    window.status_queue_label = FakeLabel()

    MainWindow._update_status_bar(window)

    assert "当前中转站" in window.status_source_label.text
    assert "DALL·E" not in window.status_source_label.text


def test_open_settings_refreshes_status_bar_after_save():
    from src.widgets import main_window as main_window_module
    from src.widgets.main_window import MainWindow

    class FakeDialog:
        def __init__(self, db, parent=None):
            pass

        def exec(self):
            return True

    window = MainWindow.__new__(MainWindow)
    window.db = object()
    window._platform_status_dirty = False
    window.refreshed = False
    window.status_updated = False
    window._refresh_platform_config_statuses = lambda: setattr(window, "refreshed", True)
    window._update_status_bar = lambda: setattr(window, "status_updated", True)

    original_dialog = main_window_module.SettingsDialog
    main_window_module.SettingsDialog = FakeDialog
    try:
        MainWindow._open_settings(window)
    finally:
        main_window_module.SettingsDialog = original_dialog

    assert window.refreshed is True
    assert window.status_updated is True
