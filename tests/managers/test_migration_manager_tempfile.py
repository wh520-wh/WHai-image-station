import os
import pytest
from src.managers.migration_manager import MigrationManager, ExportOptions, ImportOptions


class FakeKeyVault:
    def __init__(self):
        self.exported = []
        self.imported = []
    def export_encrypted(self, path, password):
        with open(path, "wb") as f:
            f.write(b"fake-encrypted")
        self.exported.append((path, password))
    def import_encrypted(self, path, password):
        self.imported.append((path, password))
        return 2


@pytest.mark.asyncio
async def test_export_with_keys_cleans_tempfile_on_success(tmp_path):
    key_vault = FakeKeyVault()
    mgr = MigrationManager(db=None, history_manager=None, prompt_manager=None, key_vault=key_vault)
    output = str(tmp_path / "backup.imbackup")
    await mgr.export(output, ExportOptions(
        include_history=False, include_templates=False, include_sources=False,
        include_keys=True, key_password="secret",
    ))
    temp_pattern = output + ".keys.tmp"
    remaining = list(tmp_path.glob("*.keys.tmp"))
    assert remaining == []


@pytest.mark.asyncio
async def test_import_with_keys_cleans_tempfile_on_success(tmp_path):
    key_vault = FakeKeyVault()
    mgr = MigrationManager(db=None, history_manager=None, prompt_manager=None, key_vault=key_vault)
    backup = tmp_path / "backup.imbackup"
    import zipfile
    with zipfile.ZipFile(backup, "w") as zf:
        zf.writestr("keys.ikey", b"fake-data")
        zf.writestr("manifest.json", b'{"contents": {"keys": true}}')
    await mgr.import_data(str(backup), ImportOptions(include_keys=True, key_password="secret"))
    remaining = list(tmp_path.glob("*.keys.tmp"))
    assert remaining == []


class FailingKeyVault:
    def export_encrypted(self, path, password):
        with open(path, "wb") as f:
            f.write(b"data")
        raise RuntimeError("Simulated export failure")


@pytest.mark.asyncio
async def test_export_cleans_tempfile_on_failure(tmp_path):
    key_vault = FailingKeyVault()
    mgr = MigrationManager(db=None, history_manager=None, prompt_manager=None, key_vault=key_vault)
    output = str(tmp_path / "backup.imbackup")
    with pytest.raises(RuntimeError):
        await mgr.export(output, ExportOptions(
            include_history=False, include_templates=False, include_sources=False,
            include_keys=True, key_password="secret",
        ))
    remaining = list(tmp_path.glob("*.keys.tmp"))
    assert remaining == []
