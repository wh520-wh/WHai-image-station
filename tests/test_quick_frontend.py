"""The primary frontend runs without keys or external network access."""

import asyncio
import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickItem

from src.config import constants
from src.config.database import Database
from src.config.event_loop import get_app_loop
from src.desktop import StudioBridge
from src.models.task import GenerationTask


def test_local_image_tools_use_real_qml_controls_and_keep_original(quick_studio, qtbot, tmp_path):
    import os

    from PIL import Image, ImageDraw
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest

    bridge, root, _, warnings = quick_studio
    original = tmp_path / "forest.png"
    image = Image.new("RGB", (720, 480), "#dce8dc")
    drawing = ImageDraw.Draw(image)
    drawing.ellipse((430, 60, 550, 180), fill="#ebc893")
    drawing.polygon([(0, 380), (200, 170), (380, 380), (520, 230), (720, 360), (720, 480), (0, 480)], fill="#729e85")
    drawing.polygon([(0, 430), (260, 320), (420, 460), (630, 330), (720, 390), (720, 480), (0, 480)], fill="#285d45")
    image.save(original)
    original_data = original.read_bytes()
    root.setProperty("currentPage", "tools")
    bridge.loadToolImage(QUrl.fromLocalFile(str(original)).toString())
    qtbot.waitUntil(lambda: bool(bridge.state["toolInput"]) and not bridge.state["toolLoading"])
    qtbot.wait(100)
    page = root.property("activePageLoader").property("item")

    def control(name):
        pending = [page]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        return None

    def click(name):
        button = control(name)
        assert button and button.property("enabled")
        point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint()
        QTest.mouseClick(root, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)

    click("tool_resize")
    edge = control("toolEdge")
    edge.setProperty("text", "360")
    click("runImageTool")
    qtbot.waitUntil(lambda: bool(bridge.state["toolResult"]) and not bridge.state["toolBusy"])
    result = bridge.state["toolResult"]
    assert (result["width"], result["height"]) == (360, 240)
    assert result["recordSaved"]
    assert bridge.state["galleryTotal"] == 1
    assert original.read_bytes() == original_data
    assert bridge.gallery.records[0]["image_path"] == result["path"]
    artifacts = os.environ.get("WHAI_UI_ARTIFACTS")
    if artifacts:
        output = Path(artifacts)
        output.mkdir(parents=True, exist_ok=True)
        qtbot.wait(200)
        root.grabWindow().save(str(output / "tools-result.png"))
        bridge.update(dark=True)
        qtbot.wait(150)
        root.grabWindow().save(str(output / "tools-dark.png"))
        bridge.update(dark=False)
        root.setWidth(1000)
        root.setHeight(680)
        qtbot.wait(150)
        root.grabWindow().save(str(output / "tools-compact.png"))
    click("workflowTab")
    assert page.property("toolTab") == 1
    click("imageToolsTab")
    assert page.property("toolTab") == 0
    assert not warnings


def test_local_tool_history_failure_keeps_processed_file_available(quick_studio, qtbot, tmp_path, monkeypatch):
    from PIL import Image

    bridge, _, _, warnings = quick_studio
    original = tmp_path / "local.png"
    Image.new("RGB", (32, 24), "green").save(original)
    bridge.loadToolImage(str(original))
    qtbot.waitUntil(lambda: bool(bridge.state["toolInput"]) and not bridge.state["toolLoading"])

    async def fail_save(record):
        raise RuntimeError("offline database unavailable")

    monkeypatch.setattr(bridge.db, "save_generation_history", fail_save)
    bridge.runImageTool("convert", "JPEG", 1024, 85)
    qtbot.waitUntil(lambda: bool(bridge.state["toolResult"]) and not bridge.state["toolBusy"])
    assert Path(bridge.state["toolResult"]["path"]).is_file()
    assert not bridge.state["toolResult"]["recordSaved"]
    assert "database unavailable" in bridge.state["toolError"]
    assert original.is_file()
    assert not warnings


def test_tool_preview_respects_photo_orientation(quick_studio, qtbot, tmp_path):
    from PIL import Image

    bridge, root, _, warnings = quick_studio
    original = tmp_path / "portrait.jpg"
    photo = Image.new("RGB", (256, 128), "green")
    exif = photo.getexif()
    exif[274] = 6
    photo.save(original, exif=exif)
    bridge.editImage(str(original))
    qtbot.waitUntil(lambda: bool(bridge.state["toolInput"]) and not bridge.state["toolLoading"])
    page = root.property("activePageLoader").property("item")
    preview = page.findChild(QQuickItem, "toolImagePreview")
    qtbot.waitUntil(lambda: preview.property("paintedHeight") > preview.property("paintedWidth") > 0)
    assert not warnings


def test_reusing_local_edit_opens_tools_without_changing_generation_draft(quick_studio, qtbot, tmp_path):
    from PIL import Image

    from src.managers.history_manager import LOCAL_EDIT_PLATFORM

    bridge, root, _, warnings = quick_studio
    original = tmp_path / "edited.png"
    Image.new("RGB", (64, 32), "green").save(original)
    draft = dict(bridge.state["draft"])
    record = bridge._present_record({"platform_id": LOCAL_EDIT_PLATFORM, "image_path": str(original), "params": {"quality": 85}})
    assert record["isLocalEdit"]
    bridge.reuseRecord(record)
    qtbot.waitUntil(lambda: bool(bridge.state["toolInput"]) and not bridge.state["toolLoading"])
    assert root.property("currentPage") == "tools"
    assert bridge.state["draft"] == draft
    assert not bridge.state["tasks"]
    assert not warnings


def test_workflow_preserves_full_settings_until_explicit_replacement(quick_studio, qtbot, tmp_path):
    from PIL import Image

    bridge, *_ = quick_studio
    reference = tmp_path / "reference.png"
    Image.new("RGB", (16, 12), "green").save(reference)
    for key, value in {
        "reference": str(reference),
        "output_format": "webp",
        "transparent": True,
        "quality": "high",
    }.items():
        bridge.setDraft(key, value)
    bridge.saveChain("", "saved settings", "first\nsecond")
    qtbot.waitUntil(lambda: len(bridge.state["chains"]) == 1)
    chain = bridge.chains.get_all_chains()[0]
    chain_id = chain["id"]
    bridge.chains.get_chain_status(chain_id).failure_mode = "skip"
    original = chain["tasks"][0]
    assert Path(original["reference_image_path"]).read_bytes() == reference.read_bytes()
    assert Path(original["reference_image_path"]).parent.name == "references"
    assert original["params"]["output_format"] == "webp"
    assert original["params"]["background"] == "transparent"

    minimax = next(source for source in bridge._sources if source["interface_type"] == "minimax")
    bridge.selectSource(minimax["id"])
    bridge.setDraft("seed", "0")
    bridge.saveChain(chain_id, "edited", "changed\nsecond\nextra", False)
    qtbot.waitUntil(lambda: bridge.state["chains"][0]["name"] == "edited")
    edited = bridge.chains.get_chain(chain_id)
    assert edited["failure_mode"] == "skip"
    assert len({task["task_id"] for task in edited["tasks"]}) == 3
    for task in edited["tasks"]:
        for key in ("source_id", "model_config_id", "params", "negative_prompt", "reference_image_path"):
            assert task[key] == original[key]
    get_app_loop().run_until_complete(bridge.chains.load_chains())
    assert bridge.chains.get_chain(chain_id)["tasks"][0]["reference_image_path"] == original["reference_image_path"]

    bridge.saveChain(chain_id, "replaced", "new settings", True)
    qtbot.waitUntil(lambda: bridge.state["chains"][0]["name"] == "replaced")
    replaced = bridge.chains.get_chain(chain_id)["tasks"][0]
    assert replaced["source_id"] == minimax["id"]
    assert replaced["params"]["seed"] == 0
    assert "background" not in replaced["params"]
    assert "output_format" not in replaced["params"]


def test_template_preserves_supported_parameters_and_reference(quick_studio, qtbot, tmp_path):
    from PIL import Image

    bridge, *_ = quick_studio
    reference = tmp_path / "template-reference.png"
    Image.new("RGB", (16, 12), "green").save(reference)
    for key, value in {
        "prompt": "a template",
        "reference": str(reference),
        "transparent": True,
        "output_format": "webp",
    }.items():
        bridge.setDraft(key, value)
    bridge.savePrompt("saved", "")
    qtbot.waitUntil(lambda: len(bridge.state["prompts"]) == 1)
    bridge.setDraft("reference", "")
    bridge.setDraft("transparent", False)
    bridge.usePrompt(bridge.state["prompts"][0])
    assert Path(bridge.state["draft"]["reference"]).read_bytes() == reference.read_bytes()
    assert Path(bridge.state["draft"]["reference"]).parent.name == "references"
    assert bridge.state["draft"]["transparent"]
    assert bridge.state["draft"]["output_format"] == "webp"


def test_waiting_task_cancellation_updates_selected_preview(quick_studio):
    bridge, *_ = quick_studio
    task = GenerationTask(prompt="cancel this")
    bridge.queue.add_task(task)
    bridge.refresh_tasks()
    bridge.selectTask(str(task.id))
    bridge.cancelTask(str(task.id))
    assert bridge.state["preview"]["status"] == "CANCELLED"
    assert not bridge.state["tasks"]


def test_legacy_completed_record_does_not_invent_elapsed_time(quick_studio):
    bridge, *_ = quick_studio
    bridge._publish_preview({"task_id": "legacy", "status": "COMPLETED", "created_at": "2026-01-01T00:00:00"})
    assert bridge.state["previewElapsed"] == ""


def test_compatible_options_survive_refresh_and_reuse(quick_studio):
    bridge, *_ = quick_studio
    loop = get_app_loop()
    source = next(source for source in bridge._sources if source["id"] == bridge.state["sourceId"])
    loop.run_until_complete(
        bridge.db.save_source(dict(source, interface_type="custom", api_base_url="https://relay.test/v1"))
    )
    loop.run_until_complete(bridge.reload_sources())
    bridge.setDraft("quality", "provider-specific")
    bridge.setDraft("n", 3)
    loop.run_until_complete(bridge.reload_sources())
    assert bridge.state["draft"]["quality"] == "provider-specific"
    assert bridge.state["draft"]["n"] == 3
    bridge.usePrompt(
        {
            "source_id": source["id"],
            "model_config_id": bridge.state["modelId"],
            "prompt": "restored",
            "params": {"size": "1280x768", "quality": "provider-specific", "n": 3, "seed": 0},
        }
    )
    assert bridge.state["draft"]["quality"] == "provider-specific"
    assert bridge.state["draft"]["n"] == 3
    assert bridge.task_from_draft(require_key=False).params["seed"] == 0


def test_entire_workflow_is_validated_before_normalized_tasks_start(quick_studio, monkeypatch):
    bridge, *_ = quick_studio
    loop = get_app_loop()
    source = next(source for source in bridge._sources if source["id"] == bridge.state["sourceId"])
    bfl = next(source for source in bridge._sources if source["interface_type"] == "bfl")
    loop.run_until_complete(bridge.db.save_source(dict(source, interface_type="custom", auth_preset="none")))
    loop.run_until_complete(bridge.db.save_source(dict(bfl, auth_preset="none")))
    loop.run_until_complete(bridge.reload_sources())
    flux_model = next(model for model in bridge._models if model["source_id"] == bfl["id"])
    chain_id = loop.run_until_complete(
        bridge.chains.create_chain(
            {
                "name": "legacy options",
                "tasks": [
                    {
                        "prompt": "first",
                        "source_id": source["id"],
                        "model_config_id": bridge.state["modelId"],
                        "negative_prompt": "blur",
                        "params": {
                            "size": "1280×768",
                            "quality": "provider-specific",
                            "n": 3,
                            "seed": "0",
                            "steps": 25,
                            "guidance": 7,
                        },
                    },
                    {
                        "prompt": "second",
                        "source_id": bfl["id"],
                        "model_config_id": flux_model["id"],
                        "params": {"size": "999x768", "n": 1},
                    },
                ],
            }
        )
    )
    started = []
    monkeypatch.setattr(bridge.chains, "start_chain_background", started.append)
    bridge.chainAction(chain_id, "start")
    assert not started
    runtime = bridge.chains.get_chain_status(chain_id)
    assert runtime.tasks[0].params["size"] == "1280×768"
    assert runtime.tasks[0].params["seed"] == "0"
    runtime.tasks[1].params["size"] = "1024x1024"
    bridge.chainAction(chain_id, "start")
    assert started == [chain_id]
    assert runtime.tasks[0].params == {
        "size": "1280x768",
        "quality": "provider-specific",
        "n": 3,
        "seed": 0,
        "steps": 25,
        "guidance": 7,
    }
    assert runtime.tasks[0].negative_prompt == "blur"


def test_selected_task_and_image_survive_other_completions_and_gallery_filters(
    quick_studio, qtbot, monkeypatch, tmp_path
):
    from PIL import Image
    from PySide6.QtGui import QGuiApplication

    from src.adapters.base import BaseAdapter, GenerationResult
    from src.config import encryption
    from src.managers.queue_manager import QueueManager

    bridge, root, _, warnings = quick_studio
    paths = {}
    gates = {name: threading.Event() for name in ("A", "B")}
    for name, colors in {"A": ("#cc5544", "#58a077"), "B": ("#4466cc", "#ccaa44")}.items():
        paths[name] = []
        for index, color in enumerate(colors):
            path = tmp_path / f"{name}-{index}.png"
            Image.new("RGB", (32, 24), color).save(path)
            paths[name].append(str(path))

    class ControlledAdapter(BaseAdapter):
        async def generate(self, task, config):
            while not gates[task.prompt].is_set():
                await asyncio.sleep(0.01)
            return GenerationResult(True, paths[task.prompt])

        async def validate_config(self, config):
            return True

        def get_params_schema(self):
            return {}

    adapter = ControlledAdapter()
    monkeypatch.setattr("src.managers.queue_manager.get_adapter", lambda _: adapter)
    loop = get_app_loop()
    source = next(source for source in bridge._sources if source["interface_type"] == "openai_images")
    loop.run_until_complete(
        bridge.db.save_source(dict(source, api_key_encrypted=encryption.encrypt("offline-placeholder")))
    )
    loop.run_until_complete(bridge.reload_sources())
    bridge.selectSource(source["id"])
    bridge.queue = QueueManager()
    bridge.queue.set_event_callback(bridge.eventsAvailable.emit)
    bridge.queue.max_concurrent = 2
    loop.run_until_complete(bridge.queue.initialize(bridge.db))
    loop.run_until_complete(bridge.queue.start())
    try:
        bridge.setDraft("prompt", "A")
        bridge.generate()
        task_a = bridge.state["selectedTaskId"]
        bridge.setDraft("prompt", "B")
        bridge.generate()
        task_b = bridge.state["selectedTaskId"]
        bridge.selectTask(task_a)
        bridge.searchGallery("no matching record", "")
        gates["B"].set()
        qtbot.waitUntil(
            lambda: any(task["task_id"] == task_b and task["status"] == "COMPLETED" for task in bridge.state["tasks"]),
            timeout=5000,
        )
        assert bridge.state["selectedTaskId"] == task_a
        assert not bridge.state["preview"]["images"]

        gates["A"].set()
        qtbot.waitUntil(lambda: bridge.state["preview"].get("status") == "COMPLETED", timeout=5000)
        assert bridge.state["preview"]["result_paths"] == paths["A"]
        assert len(bridge.state["preview"]["images"]) == 2
        qtbot.waitUntil(lambda: not bridge.state["galleryLoading"])
        assert bridge.state["galleryTotal"] == 0
        bridge.selectPreviewImage(1)
        qtbot.wait(50)
        page = root.property("activePageLoader").property("item")
        expression = QQmlExpression(QQmlEngine.contextForObject(page), page, "imagePath")
        assert expression.evaluate()[0] == paths["A"][1]
        assert not expression.hasError()

        target = tmp_path / "selected-result.png"
        monkeypatch.setattr("src.desktop.QFileDialog.getSaveFileName", lambda *args: (str(target), "PNG"))
        for name in ("savePreviewButton", "copyPreviewButton", "referencePreviewButton"):
            click = QQmlExpression(QQmlEngine.contextForObject(page), page, name + ".clicked()")
            click.evaluate()
            assert not click.hasError(), click.error().toString()
            if name == "savePreviewButton":
                qtbot.waitUntil(target.exists)
                assert target.read_bytes() == Path(paths["A"][1]).read_bytes()
            elif name == "copyPreviewButton":
                qtbot.waitUntil(
                    lambda: (
                        not QGuiApplication.clipboard().image().isNull()
                        and QGuiApplication.clipboard().image().pixelColor(0, 0).name() == "#58a077"
                    )
                )
            else:
                qtbot.waitUntil(lambda: bool(bridge.state["draft"]["reference"]))
                assert Path(bridge.state["draft"]["reference"]).read_bytes() == Path(paths["A"][1]).read_bytes()
                assert Path(bridge.state["draft"]["reference"]).parent.name == "references"

        requested = []
        bridge.viewerRequested.connect(requested.append)
        bridge.viewPreview()
        assert requested[-1]["selected_image_index"] == 1
        qtbot.wait(30)
        assert root.property("modalOpen")
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        count = len(bridge.queue.get_task_snapshots(100))
        QTest.keyClick(root, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
        qtbot.wait(100)
        assert len(bridge.queue.get_task_snapshots(100)) == count
        expression = QQmlExpression(QQmlEngine.contextForObject(page), page, "previewPicture.source.toString()")
        assert expression.evaluate()[0] == QUrl.fromLocalFile(paths["A"][1]).toString()
        assert not warnings, warnings
    finally:
        gates["A"].set()
        gates["B"].set()
        loop.run_until_complete(bridge.queue.stop())


@pytest.fixture
def quick_studio(qapp, qtbot, tmp_path, monkeypatch):
    from src.managers.queue_manager import QueueManager

    monkeypatch.setattr(QueueManager, "_instance", QueueManager())
    monkeypatch.setattr(constants, "GENERATIONS_DIR", str(tmp_path / "images"))
    monkeypatch.setattr(constants, "THUMBNAILS_DIR", str(tmp_path / "thumbs"))
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    bridge = StudioBridge()
    db = Database(str(tmp_path / "studio.db"))
    loop = get_app_loop()
    loop.run_until_complete(db.connect())
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    engine.rootContext().setContextProperty("studio", bridge)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parents[1] / "src/ui/Main.qml")))
    if not engine.rootObjects():
        loop.run_until_complete(db.close())
    assert engine.rootObjects(), warnings
    loop.run_until_complete(bridge.initialize(db))
    qtbot.wait(250)
    root = engine.rootObjects()[0]
    yield bridge, root, engine, warnings
    root.close()
    bridge._timer.stop()
    engine.deleteLater()
    qtbot.wait(20)
    loop.run_until_complete(db.close())


def test_all_pages_load_and_are_navigable(quick_studio, qtbot):
    bridge, root, engine, warnings = quick_studio
    assert len(bridge.state["sources"]) == 4
    for page in ("create", "gallery", "prompts", "sources", "tools", "settings"):
        root.setProperty("currentPage", page)
        qtbot.wait(100)
        loader = root.property("activePageLoader")
        assert isinstance(loader, QQuickItem)
        assert loader.property("item") is not None, warnings
    assert not warnings, "\n".join(warnings)


def test_empty_key_never_submits_task(quick_studio):
    bridge, *_ = quick_studio
    bridge.setDraft("prompt", "An offline test")
    before = len(bridge.queue.get_task_snapshots(100))
    errors = []
    bridge.message.connect(lambda message, error: errors.append((message, error)))
    bridge.generate()
    assert len(bridge.queue.get_task_snapshots(100)) == before
    assert errors[-1][1] and "密钥" in errors[-1][0]


def test_navigation_keeps_unsaved_source_fields(quick_studio, qtbot):
    _, root, _, warnings = quick_studio
    root.setProperty("currentPage", "sources")
    qtbot.wait(100)
    page = root.property("activePageLoader").property("item")
    context = QQmlEngine.contextForObject(page)
    setter = QQmlExpression(context, page, "keyField.text = 'offline-unsaved'")
    setter.evaluate()
    assert not setter.hasError()
    root.setProperty("currentPage", "tools")
    qtbot.wait(100)
    root.setProperty("currentPage", "sources")
    qtbot.wait(100)
    restored = root.property("activePageLoader").property("item")
    assert restored == page
    reader = QQmlExpression(QQmlEngine.contextForObject(restored), restored, "keyField.text")
    assert reader.evaluate()[0] == "offline-unsaved"
    assert not warnings


def test_refresh_keeps_draft_and_template_restores_model(quick_studio):
    bridge, *_ = quick_studio
    bridge.setDraft("prompt", "keep this")
    bridge.setDraft("size", "1536x1024")
    get_app_loop().run_until_complete(bridge.reload_sources())
    assert bridge.state["draft"]["prompt"] == "keep this"
    assert bridge.state["draft"]["size"] == "1536x1024"
    gemini = next(s for s in bridge.state["sources"] if s["interface_type"] == "gemini")
    model = next(m for m in bridge.state["models"] if m["source_id"] == gemini["id"])
    bridge.usePrompt(
        {
            "source_id": gemini["id"],
            "model_config_id": model["id"],
            "prompt": "restore",
            "params": {"size": "16:9", "quality": "2K"},
        }
    )
    assert bridge.state["draft"]["size"] == "16:9"
    assert bridge.state["draft"]["quality"] == "2K"
    assert bridge.state["modelId"] == model["id"]


def test_queue_snapshots_are_qml_serializable(quick_studio):
    bridge, *_ = quick_studio
    task = GenerationTask(prompt="offline", params={"_internal": object()})
    bridge.queue.add_task(task)
    bridge.refresh_tasks()
    assert bridge.state["tasks"][0]["params"] == {}
    bridge.cancelTask(str(task.id))


def test_source_save_preserves_key_and_user_draft(quick_studio, qtbot):
    from src.config import encryption

    bridge, *_ = quick_studio
    source = next(s for s in bridge._sources if s["interface_type"] == "openai_images")
    source["api_key_encrypted"] = encryption.encrypt("offline-secret")
    loop = get_app_loop()
    loop.run_until_complete(bridge.db.save_source(source))
    loop.run_until_complete(bridge.reload_sources())
    safe = next(s for s in bridge._state["sources"] if s["id"] == source["id"])
    models = [m for m in bridge._models if m["source_id"] == source["id"]]
    bridge.setDraft("prompt", "preserve")
    bridge.saveSource(dict(safe, name="renamed", proxy="http://localhost:7890"), models, "")
    qtbot.waitUntil(lambda: not bridge._state["busy"])
    saved = loop.run_until_complete(bridge.db.get_source(source["id"]))
    assert encryption.decrypt(saved["api_key_encrypted"]) == "offline-secret"
    assert saved["proxy"] == "http://localhost:7890"
    assert bridge._state["draft"]["prompt"] == "preserve"


def test_single_image_providers_do_not_offer_ignored_counts(quick_studio):
    bridge, *_ = quick_studio
    bridge.setDraft("n", 4)
    gemini = next(s for s in bridge._sources if s["interface_type"] == "gemini")
    bridge.selectSource(gemini["id"])
    assert bridge._state["caps"]["counts"] == [1]
    assert bridge._state["draft"]["n"] == 1


def test_custom_dimensions_survive_refresh_and_template_reuse(quick_studio):
    bridge, *_ = quick_studio
    bridge.setDraft("size", "1280x768")
    get_app_loop().run_until_complete(bridge.reload_sources())
    assert bridge._state["draft"]["size"] == "1280x768"
    bridge.usePrompt(
        {
            "source_id": bridge._state["sourceId"],
            "model_config_id": bridge._state["modelId"],
            "prompt": "reuse",
            "params": {"size": "1280x768"},
        }
    )
    assert bridge._state["draft"]["size"] == "1280x768"


def test_unconfigured_workflow_fails_before_worker_starts(quick_studio, monkeypatch):
    bridge, *_ = quick_studio
    chain_id = get_app_loop().run_until_complete(
        bridge.chains.create_chain(
            {
                "name": "offline",
                "tasks": [
                    {
                        "prompt": "offline",
                        "source_id": bridge._state["sourceId"],
                        "model_config_id": bridge._state["modelId"],
                    }
                ],
            }
        )
    )
    started = []
    monkeypatch.setattr(bridge.chains, "start_chain_background", started.append)
    messages = []
    bridge.message.connect(lambda message, error: messages.append((message, error)))
    bridge.chainAction(chain_id, "start")
    assert not started and messages[-1][1]


def test_copy_and_save_image_keep_original_pixels(quick_studio, qtbot, tmp_path, monkeypatch):
    from PIL import Image
    from PySide6.QtGui import QGuiApplication

    bridge, *_ = quick_studio
    original = tmp_path / "offline.png"
    Image.new("RGB", (16, 12), "green").save(original)
    destination = tmp_path / "saved.png"
    monkeypatch.setattr("src.desktop.QFileDialog.getSaveFileName", lambda *args: (str(destination), "PNG"))
    bridge.saveImage(str(original))
    qtbot.waitUntil(lambda: not bridge._state["busy"])
    assert destination.read_bytes() == original.read_bytes()
    bridge.copyImage(str(original))
    qtbot.waitUntil(lambda: QGuiApplication.clipboard().image().width() == 16)
    assert QGuiApplication.clipboard().image().width() == 16


@pytest.mark.asyncio
async def test_database_search_includes_old_records_and_literal_wildcards(tmp_path):
    db = Database(str(tmp_path / "search.db"))
    await db.connect()
    try:
        for i in range(75):
            await db.save_generation_history(
                {
                    "task_id": str(i),
                    "prompt": "literal 100%_" if i == 0 else "new",
                    "created_at": f"2026-01-{i:03d}",
                    "status": "COMPLETED",
                }
            )
        records, total = await db.search_history("100%_")
        assert total == 1 and records[0]["task_id"] == "0"
        records, total = await db.search_history(limit=60)
        assert len(records) == 60 and total == 75
        older, _ = await db.search_history(limit=60, offset=60)
        assert len(older) == 15
        assert not {r["task_id"] for r in records} & {r["task_id"] for r in older}
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_transaction_rollback_does_not_capture_other_ui_operations(tmp_path):
    db = Database(str(tmp_path / "transactions.db"))
    await db.connect()
    try:
        with pytest.raises(ValueError, match="rollback"):
            async with db.transaction():
                await db.save_generation_history({"task_id": "rolled-back"})
                concurrent = asyncio.create_task(db.save_generation_history({"task_id": "keep"}))
                await asyncio.sleep(0.01)
                assert not concurrent.done()
                raise ValueError("rollback")
        await concurrent
        records = await db.get_generation_history()
        assert [r["task_id"] for r in records] == ["keep"]
    finally:
        await db.close()


def test_async_io_does_not_block_qt_events(qapp, qtbot):
    from PySide6.QtCore import QTimer

    from src.config.event_loop import schedule_async

    ticks = []
    timer = QTimer()
    timer.setInterval(15)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    results = []
    schedule_async(asyncio.sleep(0.25, result="done"), on_success=results.append)
    qtbot.waitUntil(lambda: bool(results), timeout=1500)
    timer.stop()
    assert len(ticks) >= 8
    from src.config import event_loop

    assert not event_loop._pump.isActive()


def test_mocked_generation_reaches_qml_gallery(quick_studio, qtbot, monkeypatch, tmp_path):
    import base64
    import io

    from PIL import Image

    from src.adapters.base import BaseAdapter, GenerationResult
    from src.config import encryption
    from src.managers.queue_manager import QueueManager

    bridge, root, engine, warnings = quick_studio
    image = io.BytesIO()
    Image.new("RGB", (32, 24), "#285D45").save(image, "JPEG")

    class OfflineAdapter(BaseAdapter):
        async def generate(self, task, config):
            paths = await self.save_image_refs([base64.b64encode(image.getvalue()).decode()], task, config)
            return GenerationResult(True, paths)

        async def validate_config(self, config):
            return True

        def get_params_schema(self):
            return {}

    adapter = OfflineAdapter()
    monkeypatch.setattr("src.managers.queue_manager.get_adapter", lambda _: adapter)
    source = bridge._sources[0]
    loop = get_app_loop()
    loop.run_until_complete(
        bridge.db.save_source(dict(source, api_key_encrypted=encryption.encrypt("offline-placeholder")))
    )
    loop.run_until_complete(bridge.reload_sources())
    bridge.selectSource(source["id"])
    bridge.queue = QueueManager()
    bridge.queue.set_event_callback(bridge.eventsAvailable.emit)
    loop.run_until_complete(bridge.queue.initialize(bridge.db))
    loop.run_until_complete(bridge.queue.start())
    try:
        bridge.setDraft("prompt", "offline fixture")
        bridge.generate()
        qtbot.waitUntil(lambda: bridge.state["galleryTotal"] == 1, timeout=5000)
        record = bridge.gallery.records[0]
        assert record["status"] == "COMPLETED"
        assert record["image_path"].endswith(".jpg")
        assert Path(record["thumbnail_path"]).exists()
        root.setProperty("currentPage", "gallery")
        qtbot.wait(150)
        bridge.viewRecord(record)
        qtbot.wait(150)
        assert not warnings, warnings
    finally:
        loop.run_until_complete(bridge.queue.stop())
