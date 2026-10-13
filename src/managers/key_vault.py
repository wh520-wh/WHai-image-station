from __future__ import annotations

import base64
import json
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class KeyVault:
    """API密钥安全存储，使用AES-128-CBC加密"""

    def __init__(self, vault_path: str, password: str):
        self._vault_path = vault_path
        self._key = self._derive_key(password)
        self._fernet = Fernet(base64.urlsafe_b64encode(self._key))
        self._data: dict[str, str] = {}
        self._load()

    def _derive_key(self, password: str) -> bytes:
        salt_file = self._vault_path + ".salt"
        try:
            if os.path.exists(salt_file):
                with open(salt_file, "rb") as f:
                    salt = f.read()
            else:
                salt = os.urandom(16)
                with open(salt_file, "wb") as f:
                    f.write(salt)
        except OSError as e:
            raise ValueError(f"Failed to access salt file {salt_file}: {e}") from e
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600000,
        )
        return kdf.derive(password.encode())

    def _load(self):
        if os.path.exists(self._vault_path):
            try:
                with open(self._vault_path, "rb") as f:
                    encrypted = f.read()
            except OSError as e:
                raise ValueError(f"Failed to read vault file: {e}") from e
            if encrypted:
                try:
                    decrypted = self._fernet.decrypt(encrypted)
                    self._data = json.loads(decrypted)
                except Exception as e:
                    raise ValueError("Failed to decrypt vault - incorrect password or corrupted data") from e

    def _save(self):
        try:
            with open(self._vault_path, "wb") as f:
                encrypted = self._fernet.encrypt(json.dumps(self._data).encode())
                f.write(encrypted)
        except OSError as e:
            raise ValueError(f"Failed to write vault file: {e}") from e

    def store(self, platform_id: str, key: str) -> None:
        self._data[platform_id] = key
        self._save()

    def get(self, platform_id: str) -> str | None:
        return self._data.get(platform_id)

    def get_masked(self, platform_id: str) -> str:
        key = self.get(platform_id)
        if not key:
            return ""
        if len(key) <= 8:
            return "*" * len(key)
        return key[:6] + "*" * (len(key) - 8) + key[-2:]

    def list_keys(self) -> list[dict]:
        return [{"platform_id": pid, "masked": self.get_masked(pid)} for pid in self._data.keys()]

    def delete(self, platform_id: str) -> None:
        if platform_id in self._data:
            del self._data[platform_id]
            self._save()

    def export_encrypted(self, output_path: str, password: str) -> None:
        export_key = self._derive_key(password)
        export_fernet = Fernet(base64.urlsafe_b64encode(export_key))
        with open(output_path, "wb") as f:
            encrypted = export_fernet.encrypt(json.dumps(self._data).encode())
            f.write(encrypted)

    def import_encrypted(self, file_path: str, password: str) -> int:
        decrypt_key = self._derive_key(password)
        decrypt_fernet = Fernet(base64.urlsafe_b64encode(decrypt_key))
        try:
            with open(file_path, "rb") as f:
                decrypted = decrypt_fernet.decrypt(f.read())
        except OSError as e:
            raise ValueError(f"Failed to read encrypted file: {e}") from e
        except Exception as e:
            raise ValueError("Failed to decrypt file - incorrect password or corrupted data") from e
        imported = json.loads(decrypted)
        count = 0
        for pid, key in imported.items():
            self._data[pid] = key
            count += 1
        self._save()
        return count
