import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_master_key = None


def _get_machine_fingerprint() -> bytes:
    """根据机器信息生成唯一指纹"""
    import uuid

    cpu_id = str(uuid.getnode())
    board_id = str(uuid.UUID(int=uuid.getnode()))
    combined = f"{cpu_id}-{board_id}".encode()
    return hashlib.sha256(combined).digest()


def _get_master_key() -> bytes:
    """获取或生成主密钥"""
    global _master_key
    if _master_key is not None:
        return _master_key
    fingerprint = _get_machine_fingerprint()
    _master_key = fingerprint[:32]
    return _master_key


def encrypt(plaintext: str) -> bytes:
    """AES-256-GCM 加密"""
    key = _get_master_key()
    nonce = os.urandom(12)
    cipher = AESGCM(key)
    ciphertext = cipher.encrypt(nonce, plaintext.encode(), None)
    return nonce + ciphertext


def decrypt(encrypted: bytes) -> str:
    """AES-256-GCM 解密"""
    key = _get_master_key()
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    cipher = AESGCM(key)
    return cipher.decrypt(nonce, ciphertext, None).decode()
