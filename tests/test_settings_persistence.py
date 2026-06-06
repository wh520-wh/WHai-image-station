import asyncio
import json
import sys

from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QLineEdit, QTableWidget, QTableWidgetItem

from src.adapters import init_adapters
from src.config.database import Database
from src.config import encryption
from src.widgets.settings_dialog import SettingsDialog


_app = QApplication.instance() or QApplication(sys.argv)


def run(coro):
    return asyncio.run(coro)


def test_source_config_update_preserves_existing_api_key_when_left_blank(tmp_path):
    async def scenario():
        db = Database(str(tmp_path / "data.db"))
        await db.connect()
        try:
            source_id = await db.save_source({
                "id": "src_test",
                "name": "测试来源",
                "api_base_url": "https://first.example/v1",
                "api_key_encrypted": b"encrypted-secret",
                "custom_headers": json.dumps({"X-First": "1"}),
                "proxy": "http://127.0.0.1:8080",
                "is_active": 1,
            })

            await db.save_source({
                "id": source_id,
                "name": "测试来源",
                "api_base_url": "https://second.example/v1",
                "api_key_encrypted": None,
                "custom_headers": json.dumps({"X-Second": "2"}),
                "proxy": None,
                "is_active": 1,
            })

            source = await db.get_source(source_id)
            assert source["api_base_url"] == "https://second.example/v1"
            assert source["api_key_encrypted"] == b"encrypted-secret"
            assert json.loads(source["custom_headers"]) == {"X-Second": "2"}
            assert source["proxy"] is None
        finally:
            await db.close()

    run(scenario())


def test_settings_dialog_loads_persisted_source_config(tmp_path):
    async def scenario():
        db = Database(str(tmp_path / "data.db"))
        await db.connect()
        source_id = await db.save_source({
            "id": "src_test",
            "name": "DALL·E 3",
            "api_base_url": "https://relay.example/v1",
            "api_key_encrypted": encryption.encrypt("sk-test"),
            "custom_headers": json.dumps({"Authorization-Proxy": "abc"}),
            "proxy": "http://127.0.0.1:8080",
            "is_active": 1,
        })
        await db.save_source_model({
            "id": "mdl_test",
            "source_id": source_id,
            "display_name": "gpt-image-2",
            "model_id": "gpt-image-2",
            "default_size": "1024x1024",
            "default_quality": "standard",
            "default_n": 1,
            "sort_order": 0,
            "is_active": 1,
        })
        return db

    init_adapters()
    db = run(scenario())
    try:
        dialog = SettingsDialog(db)
        url_input = dialog.findChild(QLineEdit, "url_openai")
        key_input = dialog.findChild(QLineEdit, "key_openai")
        proxy_check = dialog.findChild(QCheckBox, "proxy_check_openai")
        proxy_input = dialog.findChild(QLineEdit, "proxy_openai")
        header_table = dialog.findChild(QTableWidget, "headers_openai")

        assert url_input.text() == "https://relay.example/v1"
        assert key_input.text() == "sk-test"
        assert proxy_check.isChecked() is True
        assert proxy_input.text() == "http://127.0.0.1:8080"
        assert header_table.item(0, 0).text() == "Authorization-Proxy"
        assert header_table.item(0, 1).text() == "abc"
    finally:
        run(db.close())



def test_settings_dialog_builds_config_from_current_fields():
    init_adapters()
    dialog = SettingsDialog(None)
    url_input = dialog.findChild(QLineEdit, "url_openai")
    key_input = dialog.findChild(QLineEdit, "key_openai")
    proxy_check = dialog.findChild(QCheckBox, "proxy_check_openai")
    proxy_input = dialog.findChild(QLineEdit, "proxy_openai")
    header_table = dialog.findChild(QTableWidget, "headers_openai")

    url_input.setText("https://relay.example/v1")
    key_input.setText("sk-current")
    proxy_check.setChecked(True)
    proxy_input.setText("http://127.0.0.1:8080")
    header_table.setItem(0, 0, QTableWidgetItem("X-Test"))
    header_table.setItem(0, 1, QTableWidgetItem("yes"))

    config = dialog._build_config_from_fields("openai", "OpenAI")

    assert config.api_base_url == "https://relay.example/v1"
    assert config.api_key == "sk-current"
    assert config.proxy == "http://127.0.0.1:8080"
    assert config.custom_headers == {"X-Test": "yes"}


def test_settings_dialog_shows_generation_url_preview_for_openai_base_url():
    init_adapters()
    dialog = SettingsDialog(None)
    url_input = dialog.findChild(QLineEdit, "url_openai")
    preview_label = dialog.findChild(QLabel, "url_preview_openai")

    url_input.setText("https://relay.example/v1/")

    assert preview_label.text() == "实际请求: https://relay.example/v1/images/generations"


def test_settings_dialog_save_does_not_remove_api_key_from_draft_source(tmp_path):
    async def scenario():
        db = Database(str(tmp_path / "data.db"))
        await db.connect()
        return db

    db = run(scenario())
    init_adapters()
    try:
        dialog = SettingsDialog(db)
        dialog.name_input.setText("测试来源")
        dialog.url_input.setText("https://relay.example/v1")
        dialog.key_input.setText("sk-test")
        dialog._add_model_row({
            "id": "mdl_test",
            "display_name": "gpt-image-test",
            "model_id": "gpt-image-test",
            "default_size": "1024x1024",
            "default_quality": "standard",
            "default_n": 1,
        })

        from src.widgets import settings_dialog as settings_dialog_module

        original_info = settings_dialog_module.QMessageBox.information
        settings_dialog_module.QMessageBox.information = lambda *args, **kwargs: None
        try:
            dialog._save()
        finally:
            settings_dialog_module.QMessageBox.information = original_info

        assert dialog.sources[0]["api_key"] == "sk-test"
    finally:
        run(db.close())


def test_settings_dialog_reopens_with_saved_api_key_without_reentry(tmp_path):
    async def scenario():
        db = Database(str(tmp_path / "data.db"))
        await db.connect()
        return db

    db = run(scenario())
    init_adapters()
    try:
        dialog = SettingsDialog(db)
        dialog.name_input.setText("测试来源")
        dialog.url_input.setText("https://relay.example/v1")
        dialog.key_input.setText("sk-keep-me")
        dialog._add_model_row({
            "id": "mdl_keep",
            "display_name": "gpt-image-keep",
            "model_id": "gpt-image-keep",
            "default_size": "1024x1024",
            "default_quality": "standard",
            "default_n": 1,
        })

        from src.widgets import settings_dialog as settings_dialog_module

        original_info = settings_dialog_module.QMessageBox.information
        settings_dialog_module.QMessageBox.information = lambda *args, **kwargs: None
        try:
            dialog._save()
        finally:
            settings_dialog_module.QMessageBox.information = original_info

        reopened = SettingsDialog(db)
        key_input = reopened.findChild(QLineEdit, "key_openai")
        source = run(db.get_sources())[0]

        assert key_input.text() == "sk-keep-me"
        assert encryption.decrypt(source["api_key_encrypted"]) == "sk-keep-me"
    finally:
        run(db.close())


def test_settings_dialog_invalid_model_count_falls_back_to_one():
    init_adapters()
    dialog = SettingsDialog(None)
    dialog.model_table.setRowCount(0)
    dialog._add_model_row({
        "display_name": "bad count",
        "model_id": "gpt-image-bad-count",
        "default_size": "1024x1024",
        "default_quality": "standard",
        "default_n": 1,
    })
    dialog.model_table.item(0, 4).setText("不是数字")

    models = dialog._models_from_table("src_test")

    assert models[0]["default_n"] == 1


def test_database_source_model_crud_and_legacy_migration(tmp_path):
    async def scenario():
        db = Database(str(tmp_path / "data.db"))
        await db.connect()
        try:
            # 模拟旧数据库：直接建旧表并插入数据
            await db.execute("""
                CREATE TABLE IF NOT EXISTS platform_configs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    api_base_url TEXT NOT NULL,
                    api_key_encrypted BLOB,
                    custom_headers TEXT,
                    model_name TEXT,
                    proxy TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)
            await db.execute(
                "INSERT OR REPLACE INTO platform_configs "
                "(id, name, api_base_url, api_key_encrypted, custom_headers, model_name, proxy, is_active) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("openai", "DALL·E / OpenAI Compatible", "https://relay.example/v1",
                 encryption.encrypt("sk-test"), json.dumps({"X-Relay": "yes"}),
                 "gpt-image-2", None, 1),
            )
            await db.migrate_legacy_openai_config()

            sources = await db.get_sources()
            assert sources[0]["name"] == "DALL·E / OpenAI Compatible"
            assert sources[0]["api_base_url"] == "https://relay.example/v1"
            assert json.loads(sources[0]["custom_headers"]) == {"X-Relay": "yes"}

            models = await db.get_source_models(sources[0]["id"])
            assert models[0]["model_id"] == "gpt-image-2"
            assert models[0]["display_name"] == "gpt-image-2"
        finally:
            await db.close()

    run(scenario())
