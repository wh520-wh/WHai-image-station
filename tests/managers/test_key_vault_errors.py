import os
import pytest
from src.managers.key_vault import KeyVault


def test_derive_key_raises_friendly_error_on_salt_failure(tmp_path):
    vault_path = str(tmp_path / "vault.dat")
    # 把 salt 文件设为目录，模拟 IO 错误
    salt_file = vault_path + ".salt"
    (tmp_path / "vault.dat.salt").mkdir()
    with pytest.raises(ValueError, match="Failed to access salt file"):
        KeyVault(vault_path, "password")
