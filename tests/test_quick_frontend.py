"""The primary frontend runs without keys or external network access."""

import asyncio
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickItem

from src.config import constants
from src.config.database import Database
from src.config.event_loop import get_app_loop
from src.desktop import StudioBridge
from src.models.task import GenerationTask


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
    qtbot.waitUntil(lambda: not QGuiApplication.clipboard().image().isNull())
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
