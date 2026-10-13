import json
import zipfile

import pytest
from PIL import Image

from src.config import constants, encryption
from src.config.database import Database
from src.config.providers import make_preset
from src.managers.history_manager import HistoryManager
from src.managers.migration_manager import ExportOptions, ImportOptions, MigrationManager
from src.managers.prompt_manager import PromptManager


@pytest.fixture
async def migration(tmp_path):
    db = Database(str(tmp_path / "origin.db"))
    await db.connect()
    source, models = make_preset("openai", "offline-source")
    source["api_key_encrypted"] = encryption.encrypt("offline-secret")
    source["custom_headers"] = json.dumps({"Authorization": "offline-token", "X-Project": "test"})
    await db.save_source(source)
    for model in models:
        await db.save_source_model(model)
    image = tmp_path / "original.png"
    Image.new("RGB", (16, 16), "green").save(image)
    await db.save_generation_history(
        {
            "task_id": "offline-task",
            "prompt": "offline",
            "image_path": str(image),
            "category": "test",
            "tags": "tag",
            "result_paths_json": [str(image)],
            "status": "COMPLETED",
        }
    )
    await db.save_prompt_template(
        {"name": "template", "prompt": "offline", "source_id": source["id"], "model_config_id": models[0]["id"]}
    )
    await db.execute(
        "INSERT INTO task_chains (id, name, created_at, status, failure_mode, tasks_json) VALUES (?, ?, ?, ?, ?, ?)",
        ("offline-chain", "chain", "2026-10-12", "running", "stop", '[{"prompt":"offline","status":"generating"}]'),
    )
    manager = MigrationManager(db, HistoryManager(db), PromptManager(db))
    yield manager, db
    await db.close()


@pytest.mark.asyncio
async def test_export_includes_images_and_excludes_secrets(migration, tmp_path):
    manager, _ = migration
    target = str(tmp_path / "backup.imbackup")
    await manager.export(target, ExportOptions())
    with zipfile.ZipFile(target) as archive:
        assert any(name.startswith("images/") for name in archive.namelist())
        sources = json.loads(archive.read("sources.json"))
        assert "offline-secret" not in json.dumps(sources)
        assert "offline-token" not in json.dumps(sources)
        assert "sources.keys" not in archive.namelist()
        assert json.loads(archive.read("models.json"))


@pytest.mark.asyncio
async def test_preview_counts_real_content(migration, tmp_path):
    manager, _ = migration
    target = str(tmp_path / "backup.imbackup")
    await manager.export(target, ExportOptions())
    preview = await manager.preview(target)
    assert (preview.history_count, preview.template_count, preview.source_count) == (1, 1, 1)
    assert not preview.has_keys


@pytest.mark.asyncio
async def test_password_backup_restores_on_another_machine(migration, tmp_path, monkeypatch):
    manager, _ = migration
    target = str(tmp_path / "portable.imbackup")
    await manager.export(target, ExportOptions(include_keys=True, key_password="offline-password"))
    monkeypatch.setattr(encryption, "_master_key", b"z" * 32)
    monkeypatch.setattr(constants, "GENERATIONS_DIR", str(tmp_path / "restored-images"))
    monkeypatch.setattr(constants, "THUMBNAILS_DIR", str(tmp_path / "restored-thumbs"))
    destination = Database(str(tmp_path / "destination.db"))
    await destination.connect()
    try:
        importer = MigrationManager(destination, HistoryManager(destination), PromptManager(destination))
        result = await importer.import_data(target, ImportOptions(include_keys=True, key_password="offline-password"))
        assert result.imported_history == 1 and result.imported_keys == 1
        source = await destination.get_source("offline-source")
        assert encryption.decrypt(source["api_key_encrypted"]) == "offline-secret"
        assert json.loads(source["custom_headers"])["Authorization"] == "offline-token"
        record = await destination.get_history_by_task_id("offline-task")
        assert record["category"] == "test" and record["tags"] == "tag"
        assert record["image_path"].startswith(str(tmp_path / "restored-images"))
        assert Image.open(record["image_path"]).size == (16, 16)
        template = (await destination.get_prompt_templates())[0]
        assert template["source_id"] == "offline-source"
        assert template["model_config_id"]
        chain = await destination.fetchone(
            "SELECT status, tasks_json FROM task_chains WHERE id = ?", ("offline-chain",)
        )
        assert chain[0] == "idle" and json.loads(chain[1])[0]["status"] == "pending"
    finally:
        await destination.close()
