import io
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from src.config import constants
from src.config.database import Database
from src.managers.history_manager import HistoryManager
from src.managers.image_assets import reference_dir, store_reference
from src.managers.migration_manager import ExportOptions, ImportOptions, MigrationManager
from src.managers.prompt_manager import PromptManager
from src.managers.reference_manager import migrate_references
from src.managers.task_chain_manager import TaskChainManager


@pytest.mark.asyncio
async def test_reference_backup_restores_templates_and_workflows_after_originals_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "GENERATIONS_DIR", str(tmp_path / "origin" / "images"))
    monkeypatch.setattr(constants, "THUMBNAILS_DIR", str(tmp_path / "origin" / "thumbs"))
    original = tmp_path / "source.png"
    Image.new("RGB", (40, 30), "green").save(original)
    data = original.read_bytes()
    db = Database(str(tmp_path / "origin.db"))
    await db.connect()
    try:
        prompts = PromptManager(db)
        await prompts.save_template({"name": "saved", "prompt": "use reference", "params": {"reference_image_path": str(original)}})
        chains = TaskChainManager(db, None)
        await chains.create_chain({"id": "saved-chain", "tasks": [{"prompt": "use reference", "reference_image_path": str(original)}]})
        retained = (await db.get_prompt_templates())[0]["params"]["reference_image_path"]
        assert chains.get_chain("saved-chain")["tasks"][0]["reference_image_path"] == retained
        await db.save_generation_history({"task_id": "original", "prompt": "original", "image_path": str(original), "result_paths_json": [str(original)], "status": "COMPLETED"})
        await HistoryManager(db).delete_record("original")
        assert not original.exists()
        assert Path(retained).read_bytes() == data
        backup = tmp_path / "portable.imbackup"
        await MigrationManager(db, HistoryManager(db), prompts).export(str(backup), ExportOptions())
        with zipfile.ZipFile(backup) as archive:
            assert len([name for name in archive.namelist() if name.startswith("references/")]) == 1
            assert json.loads(archive.read("manifest.json"))["version"] == 3
        Path(retained).unlink()
    finally:
        await db.close()
    monkeypatch.setattr(constants, "GENERATIONS_DIR", str(tmp_path / "destination" / "images"))
    monkeypatch.setattr(constants, "THUMBNAILS_DIR", str(tmp_path / "destination" / "thumbs"))
    destination = Database(str(tmp_path / "destination.db"))
    await destination.connect()
    try:
        await MigrationManager(destination, HistoryManager(destination), PromptManager(destination)).import_data(str(backup), ImportOptions())
        restored = (await destination.get_prompt_templates())[0]["params"]["reference_image_path"]
        tasks = json.loads((await destination.fetchone("SELECT tasks_json FROM task_chains WHERE id = ?", ("saved-chain",)))[0])
        assert tasks[0]["reference_image_path"] == restored
        assert Path(restored).parent == reference_dir()
        assert Path(restored).read_bytes() == data
    finally:
        await destination.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_asset", [False, True])
async def test_bad_reference_import_rolls_back_without_removing_existing_asset(tmp_path, monkeypatch, existing_asset):
    monkeypatch.setattr(constants, "GENERATIONS_DIR", str(tmp_path / "images"))
    buffer = io.BytesIO()
    Image.new("RGB", (16, 12), "green").save(buffer, "PNG")
    if existing_asset:
        store_reference(buffer.getvalue())
    backup = tmp_path / "broken.imbackup"
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"version": 3}))
        archive.writestr("templates.json", json.dumps([
            {"name": "valid", "prompt": "valid", "params": {"reference_image_path": "references/valid.png"}},
            {"name": "broken", "prompt": "broken", "params": {"reference_image_path": "references/broken.png"}},
        ]))
        archive.writestr("references/valid.png", buffer.getvalue())
        archive.writestr("references/broken.png", b"broken image")
    db = Database(str(tmp_path / "test.db"))
    await db.connect()
    try:
        with pytest.raises(OSError):
            await MigrationManager(db, HistoryManager(db), PromptManager(db)).import_data(str(backup), ImportOptions())
        assert not await db.get_prompt_templates()
        assert len(list(reference_dir().glob("*.png"))) == int(existing_asset)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_legacy_reference_is_retained_on_initialization(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "GENERATIONS_DIR", str(tmp_path / "images"))
    original = tmp_path / "legacy.png"
    Image.new("RGB", (20, 10), "green").save(original)
    db = Database(str(tmp_path / "legacy.db"))
    await db.connect()
    try:
        await db.save_prompt_template({"name": "legacy", "prompt": "saved", "params": {"reference_image_path": str(original)}})
        await migrate_references(db)
        assert len(await db.get_prompt_templates()) == 1
        retained = (await db.get_prompt_templates())[0]["params"]["reference_image_path"]
        original.unlink()
        assert Path(retained).is_file()
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_legacy_backup_without_reference_files_still_imports_settings(tmp_path):
    backup = tmp_path / "legacy.imbackup"
    missing = str(tmp_path / "old-machine" / "unavailable.png")
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"version": 2}))
        archive.writestr("templates.json", json.dumps([{ "name": "legacy", "prompt": "old", "params": {"reference_image_path": missing}}]))
    db = Database(str(tmp_path / "legacy-import.db"))
    await db.connect()
    try:
        await MigrationManager(db, HistoryManager(db), PromptManager(db)).import_data(str(backup), ImportOptions())
        assert (await db.get_prompt_templates())[0]["params"]["reference_image_path"] == missing
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_export_reads_shared_reference_once(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "GENERATIONS_DIR", str(tmp_path / "images"))
    original = tmp_path / "shared.png"
    Image.new("RGB", (16, 12), "green").save(original)
    db = Database(str(tmp_path / "shared.db"))
    await db.connect()
    try:
        prompts = PromptManager(db)
        for index in range(4):
            await prompts.save_template({"name": str(index), "prompt": "shared", "params": {"reference_image_path": str(original)}})
        from src.managers import migration_manager

        reads = []
        read_image_data = migration_manager.read_image_data

        def tracked_read(path):
            reads.append(path)
            return read_image_data(path)

        monkeypatch.setattr(migration_manager, "read_image_data", tracked_read)
        await MigrationManager(db, HistoryManager(db), prompts).export(str(tmp_path / "shared.imbackup"), ExportOptions())
        assert len(reads) == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_application_migrates_references_once_before_bridge_ready(tmp_path, monkeypatch, qapp):
    from types import SimpleNamespace

    from src import app as app_module
    from src.desktop import StudioBridge
    from src.managers.queue_manager import QueueManager

    monkeypatch.setattr(constants, "GENERATIONS_DIR", str(tmp_path / "images"))
    monkeypatch.setattr(constants, "THUMBNAILS_DIR", str(tmp_path / "thumbs"))
    db = Database(str(tmp_path / "startup.db"))
    await db.connect()
    original = tmp_path / "legacy.png"
    Image.new("RGB", (16, 12), "green").save(original)
    await db.save_prompt_template({"name": "legacy", "prompt": "saved", "params": {"reference_image_path": str(original)}})
    queue = QueueManager()
    monkeypatch.setattr(Database, "_instance", db)
    monkeypatch.setattr(QueueManager, "_instance", queue)
    monkeypatch.setattr(PromptManager, "_instance", PromptManager())
    monkeypatch.setattr(HistoryManager, "_instance", HistoryManager())
    calls = []

    async def tracked_migration(database):
        calls.append(database)
        await migrate_references(database)

    async def no_worker():
        pass

    monkeypatch.setattr(app_module, "migrate_references", tracked_migration)
    monkeypatch.setattr(queue, "start", no_worker)
    bridge = StudioBridge()
    try:
        await app_module.ImageMakerApp._async_init(SimpleNamespace(_bridge=bridge))
        assert calls == [db]
        assert bridge.property("state")["ready"]
        retained = (await db.get_prompt_templates())[0]["params"]["reference_image_path"]
        original.unlink()
        assert Path(retained).is_file()
    finally:
        await bridge.shutdown()
        await db.close()
