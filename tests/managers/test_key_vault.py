import pytest, os, tempfile
from src.managers.key_vault import KeyVault

class TestKeyVault:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.vault_path = os.path.join(self.test_dir, "test.vault")

    def test_store_and_retrieve(self):
        vault = KeyVault(self.vault_path, "test-password-123")
        vault.store("openai", "sk-test-key-123")
        retrieved = vault.get("openai")
        assert retrieved == "sk-test-key-123"

    def test_get_masked(self):
        vault = KeyVault(self.vault_path, "test-password-123")
        vault.store("openai", "sk-test-key-123")
        masked = vault.get_masked("openai")
        assert masked.startswith("sk-")
        assert "*" in masked
        assert "123" not in masked

    def test_list_keys(self):
        vault = KeyVault(self.vault_path, "test-password-123")
        vault.store("openai", "sk-test-key-123")
        vault.store("stability", "sk-stability-key-456")
        keys = vault.list_keys()
        assert len(keys) == 2
        assert keys[0]["platform_id"] == "openai"

    def test_delete_key(self):
        vault = KeyVault(self.vault_path, "test-password-123")
        vault.store("openai", "sk-test-key-123")
        vault.delete("openai")
        assert vault.get("openai") is None

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)