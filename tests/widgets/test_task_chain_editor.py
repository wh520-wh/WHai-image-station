import asyncio
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.managers.task_chain_manager import TaskChainManager
from src.widgets.task_chain_editor import TaskChainEditor


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_app = QApplication.instance() or QApplication(sys.argv)


class DummyQueueManager:
    pass


def make_manager():
    return TaskChainManager(db=None, queue_manager=DummyQueueManager())


def test_task_chain_editor_opens_with_empty_manager():
    manager = make_manager()

    editor = TaskChainEditor(manager, DummyQueueManager())

    assert editor.chain_list.count() == 0
    editor.deleteLater()


def test_task_chain_editor_lists_existing_chains():
    manager = make_manager()
    chain_id = asyncio.run(manager.create_chain({"name": "existing chain", "tasks": []}))

    editor = TaskChainEditor(manager, DummyQueueManager())

    assert editor.chain_list.count() == 1
    assert editor.chain_list.item(0).text() == "existing chain"
    assert editor.chain_list.item(0).data(Qt.UserRole) == chain_id
    editor.deleteLater()


def test_new_task_uses_default_source_and_model_context():
    manager = make_manager()
    editor = TaskChainEditor(
        manager,
        DummyQueueManager(),
        default_source_id="src-1",
        default_model_config_id="model-1",
    )

    editor._on_new_chain()
    task_widget = editor._task_widgets[0]
    task_widget.prompt_edit.setPlainText("prompt")
    task_widget.steps.setText("12")
    task_widget.guidance.setText("4.2")

    task = editor._collect_tasks()[0]

    assert task["source_id"] == "src-1"
    assert task["model_config_id"] == "model-1"
    assert task["params"]["steps"] == 12
    assert task["params"]["guidance"] == 4.2
    editor.deleteLater()


def test_existing_task_params_are_preserved_when_selected():
    manager = make_manager()
    asyncio.run(manager.create_chain({
        "id": "chain-1",
        "name": "chain",
        "tasks": [
            {
                "prompt": "prompt",
                "negative_prompt": "negative",
                "source_id": "src-1",
                "model_config_id": "model-1",
                "params": {"steps": 12, "guidance": 4.2},
            }
        ],
    }))
    editor = TaskChainEditor(manager, DummyQueueManager())

    editor._on_chain_selected(editor.chain_list.item(0))

    task_widget = editor._task_widgets[0]
    assert task_widget.steps.text() == "12"
    assert task_widget.guidance.text() == "4.2"
    task = editor._collect_tasks()[0]
    assert task["params"]["steps"] == 12
    assert task["params"]["guidance"] == 4.2
    editor.deleteLater()


def test_save_assigns_id_and_reselects_saved_chain():
    manager = make_manager()
    saved_payloads = []
    editor = TaskChainEditor(
        manager,
        DummyQueueManager(),
        default_source_id="src-1",
        default_model_config_id="model-1",
    )
    editor.chain_saved.connect(saved_payloads.append)

    editor._on_new_chain()
    editor.chain_name_input.setText("saved chain")
    editor._task_widgets[0].prompt_edit.setPlainText("prompt")
    editor._on_save_chain()

    assert saved_payloads[0]["id"]
    assert editor._current_chain_id == saved_payloads[0]["id"]
    assert editor.start_btn.isEnabled() is True
    assert "saved chain" in editor.context_hint_label.text()
    editor.deleteLater()


def test_start_without_selection_updates_user_guidance():
    manager = make_manager()
    editor = TaskChainEditor(manager, DummyQueueManager())

    editor._on_start_chain()

    assert "选择" in editor.context_hint_label.text()
    editor.deleteLater()


def test_start_reports_failure_when_manager_declines():
    class RefusingManager:
        def __init__(self):
            self.started = []

        def get_all_chains(self):
            return [{"id": "chain-1", "name": "chain", "tasks": []}]

        def get_chain(self, chain_id):
            return {"id": chain_id, "name": "chain", "tasks": []}

        def start_chain_background(self, chain_id):
            self.started.append(chain_id)
            return False

    manager = RefusingManager()
    editor = TaskChainEditor(manager, DummyQueueManager())
    editor._on_chain_selected(editor.chain_list.item(0))

    editor._on_start_chain()

    assert manager.started == ["chain-1"]
    assert "失败" in editor.context_hint_label.text()
    editor.deleteLater()


def test_main_window_loads_task_chains_during_initial_data_load():
    from src.widgets.main_window import MainWindow

    class FakeDb:
        async def get_sources(self, active_only=False):
            return []

        async def get_source_models(self, source_id, active_only=False):
            return []

    class FakePromptPanel:
        async def load_templates(self):
            pass

    class FakeGenerationPanel:
        def refresh_queue(self):
            pass

        def set_sources(self, sources, models_by_source):
            pass

        def set_platform_config_statuses(self, statuses, messages=None):
            pass

    class FakeOverlay:
        def setVisible(self, visible):
            self.visible = visible

        def setText(self, text):
            self.text = text

        def setStyleSheet(self, style):
            self.style = style

    class LoadingManager:
        def __init__(self):
            self.loaded = False

        async def load_chains(self):
            self.loaded = True

    window = MainWindow.__new__(MainWindow)
    window.db = FakeDb()
    window.prompt_panel = FakePromptPanel()
    window.generation_panel = FakeGenerationPanel()
    window.loading_overlay = FakeOverlay()
    window.task_chain_manager = LoadingManager()
    window._update_status_bar = lambda: None

    asyncio.run(MainWindow._async_load_data(window))

    assert window.task_chain_manager.loaded is True
