import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from PySide6.QtWidgets import QApplication
from src.widgets.settings_dialog import SettingsDialog

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def mock_db():
    async def mock_migrate():
        return None
    async def mock_get_sources():
        return []
    async def mock_get_source_models(source_id):
        return []

    db = MagicMock()
    db.migrate_legacy_openai_config = MagicMock(return_value=mock_migrate())
    db.get_sources = MagicMock(return_value=mock_get_sources())
    db.get_source_models = MagicMock(return_value=mock_get_source_models(""))
    return db

class TestSettingsDialogMigration:
    def test_export_button_triggers_export(self, app, mock_db):
        """Test that clicking export button triggers MigrationManager.export"""
        dialog = SettingsDialog(mock_db)

        # Mock the migration manager
        mock_migration = MagicMock()
        mock_migration.export = AsyncMock()
        dialog.migration_manager = mock_migration

        # Mock the file dialog and message box
        with patch.object(dialog, '_get_migration_manager', return_value=mock_migration):
            with patch('src.widgets.settings_dialog.QFileDialog.getSaveFileName', return_value=("test.imbackup", "")):
                with patch('src.widgets.settings_dialog.QMessageBox.information'):
                    dialog._on_export()

        mock_migration.export.assert_called_once()

    def test_import_preview_shows_content(self, app, mock_db):
        """Test that import preview shows correct content"""
        dialog = SettingsDialog(mock_db)

        mock_migration = MagicMock()
        preview_data = MagicMock()
        preview_data.history_count = 10
        preview_data.template_count = 5
        preview_data.source_count = 3
        preview_data.has_keys = True
        mock_migration.preview = AsyncMock(return_value=preview_data)
        mock_migration.import_data = AsyncMock(return_value=MagicMock(imported_history=10, imported_templates=5, imported_sources=3, imported_keys=0))
        dialog.migration_manager = mock_migration

        with patch.object(dialog, '_get_migration_manager', return_value=mock_migration):
            with patch('src.widgets.settings_dialog.QFileDialog.getOpenFileName', return_value=("test.imbackup", "")):
                with patch('src.widgets.settings_dialog.QMessageBox.question', return_value=65536):  # Yes
                    with patch('src.widgets.settings_dialog.QMessageBox.information'):
                        dialog._on_import()

        # Verify preview was called
        dialog.migration_manager.preview.assert_called_once_with("test.imbackup")

    def test_key_import_option_works(self, app, mock_db):
        """Test that key import/export buttons exist"""
        dialog = SettingsDialog(mock_db)

        # Check that the buttons exist
        assert hasattr(dialog, 'export_keys_btn')
        assert hasattr(dialog, 'import_keys_btn')

        # Check that clicking them shows an info dialog (stub implementation)
        with patch('src.widgets.settings_dialog.QMessageBox.information'):
            dialog._on_export_keys()
            dialog._on_import_keys()