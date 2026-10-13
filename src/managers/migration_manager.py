"""Portable, versioned backups. Images are archived; secrets are opt-in."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import tempfile
import zipfile
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.config import constants, encryption
from src.config.utils import get_thumbnail_path, parse_headers
from src.managers.image_assets import EXTENSIONS, create_thumbnail, read_image_data, store_reference
from src.managers.reference_manager import get_reference_path, replace_reference_path


@dataclass
class ExportOptions:
    include_history: bool = True
    include_templates: bool = True
    include_sources: bool = True
    include_settings: bool = True
    include_keys: bool = False
    key_password: str | None = None
    include_chains: bool = True


@dataclass
class ImportOptions:
    include_history: bool = True
    include_templates: bool = True
    include_sources: bool = True
    include_settings: bool = True
    include_keys: bool = False
    key_password: str | None = None
    conflict_mode: str = "keep"
    include_chains: bool = True


@dataclass
class BackupPreview:
    history_count: int
    template_count: int
    source_count: int
    has_keys: bool


@dataclass
class ImportResult:
    imported_history: int = 0
    imported_templates: int = 0
    imported_sources: int = 0
    imported_keys: int = 0


def _password_cipher(password: str, salt: bytes) -> Fernet:
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600000).derive(password.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def _without_secret_headers(raw) -> str:
    return json.dumps(
        {
            key: value
            for key, value in parse_headers(raw).items()
            if not any(word in key.lower() for word in ("key", "token", "secret", "authorization", "cookie"))
        }
    )


class MigrationManager:
    def __init__(self, db, history_manager, prompt_manager, key_vault=None):
        self.db = db
        self.history_manager = history_manager
        self.prompt_manager = prompt_manager
        self.key_vault = key_vault

    async def export(self, output_path: str, options: ExportOptions) -> str:
        history = []
        if options.include_history:
            offset = 0
            while True:
                page = await self.history_manager.get_history(500, offset)
                history.extend(page)
                if len(page) < 500:
                    break
                offset += len(page)
        templates = await self.prompt_manager.get_templates() if options.include_templates else []
        sources = await self.db.get_sources() if options.include_sources else []
        models = await self.db.get_source_models() if options.include_sources else []
        settings = (
            await self.db.fetchall("SELECT key, value FROM app_prefs") if options.include_settings and self.db else []
        )
        chains = (
            await self.db.fetchall("SELECT id, name, created_at, status, failure_mode, tasks_json FROM task_chains")
            if self.db and options.include_chains
            else []
        )
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        def write_backup():
            handle, staging = tempfile.mkstemp(suffix=".imbackup", dir=target.parent)
            os.close(handle)
            try:
                with zipfile.ZipFile(staging, "w", zipfile.ZIP_DEFLATED) as archive:
                    reference_members = set()
                    reference_paths = {}

                    def portable_settings(raw):
                        saved = dict(raw)
                        reference = get_reference_path(saved)
                        if reference:
                            key = str(Path(reference).resolve())
                            member = reference_paths.get(key)
                            if member is None:
                                data, image_format = read_image_data(reference)
                                member = "references/" + hashlib.sha256(data).hexdigest() + EXTENSIONS[image_format]
                                if member not in reference_members:
                                    archive.writestr(member, data)
                                    reference_members.add(member)
                                reference_paths[key] = member
                            saved = replace_reference_path(saved, member)
                        return saved

                    saved_history = []
                    for raw in history:
                        record = portable_settings(raw)
                        paths = list(
                            record.get("result_paths") or ([record["image_path"]] if record.get("image_path") else [])
                        )
                        refs = []
                        for path in paths:
                            if Path(path).is_file():
                                name = f"images/{uuid4().hex}{Path(path).suffix}"
                                archive.write(path, name)
                                refs.append(name)
                        record["archive_images"] = refs
                        record["image_path"] = None
                        record["thumbnail_path"] = None
                        record["result_paths"] = []
                        saved_history.append(record)
                    sanitized_sources = []
                    keys = {}
                    for raw in sources:
                        source = {k: v for k, v in raw.items() if k not in {"api_key", "api_key_encrypted"}}
                        source["custom_headers"] = _without_secret_headers(source.get("custom_headers"))
                        sanitized_sources.append(source)
                        if options.include_keys and options.key_password:
                            keys[raw["id"]] = {
                                "key": encryption.decrypt(raw["api_key_encrypted"])
                                if raw.get("api_key_encrypted")
                                else "",
                                "headers": raw.get("custom_headers"),
                            }
                    for name, value in (
                        ("history", saved_history),
                        ("templates", [portable_settings(template) for template in templates]),
                        ("sources", sanitized_sources),
                        ("models", models),
                        ("settings", settings),
                        (
                            "chains",
                            [
                                [*chain[:5], json.dumps([portable_settings(task) for task in json.loads(chain[5] or "[]")])]
                                for chain in chains
                            ],
                        ),
                    ):
                        archive.writestr(f"{name}.json", json.dumps(value, ensure_ascii=False))
                    if options.include_keys and options.key_password:
                        if self.key_vault is not None:
                            keys_path = output_path + ".keys.tmp"
                            try:
                                self.key_vault.export_encrypted(keys_path, options.key_password)
                                archive.write(keys_path, "keys.ikey")
                            finally:
                                Path(keys_path).unlink(missing_ok=True)
                        else:
                            salt = os.urandom(16)
                            token = _password_cipher(options.key_password, salt).encrypt(json.dumps(keys).encode())
                            archive.writestr("sources.keys", salt + token)
                    manifest = {
                        "version": 3,
                        "contents": {
                            "history": len(history),
                            "templates": len(templates),
                            "sources": len(sources),
                            "keys": bool(options.include_keys and options.key_password),
                            "chains": len(chains),
                        },
                    }
                    archive.writestr("manifest.json", json.dumps(manifest))
                os.replace(staging, target)
            finally:
                Path(staging).unlink(missing_ok=True)

        await asyncio.to_thread(write_backup)
        return output_path

    async def preview(self, file_path: str) -> BackupPreview:
        with zipfile.ZipFile(file_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            version = manifest.get("version", 1)
            if str(version) not in {"1", "1.0", "2", "3"}:
                raise ValueError("此备份版本不受支持")
            counts = manifest.get("contents", {})
            return BackupPreview(
                counts.get("history", 0), counts.get("templates", 0), counts.get("sources", 0), bool(counts.get("keys"))
            )

    async def import_data(self, file_path: str, options: ImportOptions) -> ImportResult:
        await self.preview(file_path)
        result = ImportResult()
        with zipfile.ZipFile(file_path) as archive:
            if sum(info.file_size for info in archive.infolist()) > 2 * 1024**3:
                raise ValueError("备份解压后超过 2 GB，请拆分导入")
            archive_members = set(archive.namelist())

            async def read_json(name):
                if name not in archive_members:
                    return []
                return json.loads(await asyncio.to_thread(archive.read, name))

            keys = {}
            if options.include_keys and "sources.keys" in archive_members:
                if not options.key_password:
                    raise ValueError("请输入密钥备份密码")
                encrypted = archive.read("sources.keys")
                try:

                    def decode_keys():
                        return json.loads(
                            _password_cipher(options.key_password or "", encrypted[:16]).decrypt(encrypted[16:])
                        )

                    keys = await asyncio.to_thread(decode_keys)
                except Exception as exc:
                    raise ValueError("备份密码不正确或密钥数据损坏") from exc
            created_files = []
            restored_references = {}

            async def restore_settings(raw):
                saved = dict(raw)
                reference = get_reference_path(saved)
                if reference and str(reference).startswith("references/"):
                    if ".." in Path(reference).parts or reference not in archive_members:
                        raise ValueError("备份中的参考图丢失或路径不合法")
                    if reference not in restored_references:
                        data = await asyncio.to_thread(archive.read, reference)
                        retained, created = await asyncio.to_thread(store_reference, data)
                        restored_references[reference] = retained
                        if created:
                            created_files.append(Path(retained))
                    saved = replace_reference_path(saved, restored_references[reference])
                return saved

            try:
                async with (
                    self.db.transaction() if self.db and hasattr(self.db, "transaction") else _null_transaction()
                ):
                    if options.include_sources:
                        for source in await read_json("sources.json"):
                            existing = await self.db.get_source(source["id"])
                            if existing and options.conflict_mode == "keep":
                                continue
                            secret = keys.get(source["id"])
                            if secret:
                                source["api_key_encrypted"] = encryption.encrypt(secret["key"])
                                source["custom_headers"] = secret.get("headers") or source.get("custom_headers")
                                result.imported_keys += 1
                            await self.db.save_source(source)
                            result.imported_sources += 1
                        for model in await read_json("models.json"):
                            if options.conflict_mode == "keep" and await self.db.get_source_model(model["id"]):
                                continue
                            await self.db.save_source_model(model)
                    if options.include_history and "history.json" in archive_members:
                        Path(constants.GENERATIONS_DIR).mkdir(parents=True, exist_ok=True)
                        for record in await read_json("history.json"):
                            if options.conflict_mode == "keep" and await self.history_manager.get_record(
                                record["task_id"]
                            ):
                                continue
                            record = await restore_settings(record)
                            paths = []
                            for member in record.pop("archive_images", []):
                                if not member.startswith("images/") or ".." in Path(member).parts:
                                    raise ValueError("备份图片路径不合法")
                                path = Path(constants.GENERATIONS_DIR) / f"{uuid4().hex}{Path(member).suffix}"
                                data = await asyncio.to_thread(archive.read, member)
                                await asyncio.to_thread(path.write_bytes, data)
                                created_files.append(path)
                                paths.append(str(path))
                            if paths:
                                record.update(
                                    image_path=paths[0], thumbnail_path=get_thumbnail_path(paths[0]), result_paths=paths
                                )
                                for path in paths:
                                    created_files.append(Path(get_thumbnail_path(path)))
                                    await asyncio.to_thread(create_thumbnail, path)
                            record["result_paths_json"] = record.get("result_paths", [])
                            await self.history_manager.save_record(record)
                            result.imported_history += 1
                    if options.include_templates and "templates.json" in archive_members:
                        existing = {(t["name"], t["prompt"]) for t in await self.prompt_manager.get_templates()}
                        for template in await read_json("templates.json"):
                            if options.conflict_mode == "keep" and (template["name"], template["prompt"]) in existing:
                                continue
                            await self.prompt_manager.save_template(await restore_settings(template))
                            result.imported_templates += 1
                    if options.include_settings:
                        for key, value in await read_json("settings.json"):
                            if options.conflict_mode != "keep" or await self.db.get_pref(key, "") == "":
                                await self.db.set_pref(key, value)
                    if options.include_chains and self.db:
                        for chain in await read_json("chains.json"):
                            if options.conflict_mode == "keep" and await self.db.fetchone(
                                "SELECT id FROM task_chains WHERE id = ?", (chain[0],)
                            ):
                                continue
                            task_data = json.loads(chain[5])
                            task_data = [await restore_settings(task) for task in task_data]
                            for task in task_data:
                                task["status"] = "pending"
                            mode = "IGNORE" if options.conflict_mode == "keep" else "REPLACE"
                            await self.db.execute(
                                f"INSERT OR {mode} INTO task_chains (id, name, created_at, status, failure_mode, tasks_json) VALUES (?, ?, ?, ?, ?, ?)",
                                (
                                    chain[0],
                                    chain[1],
                                    chain[2],
                                    "idle",
                                    chain[4],
                                    json.dumps(task_data, ensure_ascii=False),
                                ),
                            )
                    if options.include_keys and "keys.ikey" in archive_members and options.key_password:
                        if self.key_vault is None:
                            raise ValueError("此旧版备份需要原密钥库；请用原应用重新导出")
                        keys_path = file_path + ".keys.tmp"
                        try:
                            Path(keys_path).write_bytes(archive.read("keys.ikey"))
                            result.imported_keys = self.key_vault.import_encrypted(keys_path, options.key_password)
                        finally:
                            Path(keys_path).unlink(missing_ok=True)
            except BaseException:
                for path in created_files:
                    path.unlink(missing_ok=True)
                raise
        return result


@asynccontextmanager
async def _null_transaction():
    yield
