from __future__ import annotations
import os, json, zipfile, shutil
from dataclasses import dataclass
from typing import Optional

@dataclass
class ExportOptions:
    include_history: bool = True
    include_templates: bool = True
    include_sources: bool = True
    include_settings: bool = True
    include_keys: bool = False
    key_password: Optional[str] = None

@dataclass
class ImportOptions:
    include_history: bool = True
    include_templates: bool = True
    include_sources: bool = True
    include_settings: bool = True
    include_keys: bool = False
    key_password: Optional[str] = None
    conflict_mode: str = "keep"  # "keep", "overwrite", "ask"

@dataclass
class BackupPreview:
    history_count: int
    template_count: int
    source_count: int
    has_keys: bool

@dataclass
class ImportResult:
    imported_history: int
    imported_templates: int
    imported_sources: int
    imported_keys: int

class MigrationManager:
    def __init__(self, db, history_manager, prompt_manager, key_vault):
        self.db = db
        self.history_manager = history_manager
        self.prompt_manager = prompt_manager
        self.key_vault = key_vault

    async def export(self, output_path: str, options: ExportOptions) -> str:
        """导出数据到 .imbackup 文件"""
        manifest = {"version": "1.0", "exported_at": "", "contents": {}}

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if options.include_history:
                history = await self.history_manager.get_history(1000)
                history_data = [{"task_id": r["task_id"], "prompt": r["prompt"],
                                 "platform_id": r["platform_id"], "image_path": r.get("image_path")}
                                for r in history]
                zf.writestr("history.json", json.dumps(history_data, ensure_ascii=False))
                manifest["contents"]["history"] = len(history_data)

            if options.include_templates:
                templates = await self.prompt_manager.get_templates()
                zf.writestr("templates.json", json.dumps(templates, ensure_ascii=False))
                manifest["contents"]["templates"] = len(templates)

            if options.include_sources:
                sources = await self.db.get_sources()
                zf.writestr("sources.json", json.dumps(sources, ensure_ascii=False))
                manifest["contents"]["sources"] = len(sources)

            if options.include_keys and options.key_password:
                keys_path = output_path + ".keys.tmp"
                try:
                    self.key_vault.export_encrypted(keys_path, options.key_password)
                    zf.write(keys_path, "keys.ikey")
                finally:
                    if os.path.exists(keys_path):
                        os.remove(keys_path)
                manifest["contents"]["keys"] = True

            manifest["exported_at"] = str(os.path.getmtime(output_path))
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        return output_path

    async def preview(self, file_path: str) -> BackupPreview:
        """预览备份文件内容"""
        with zipfile.ZipFile(file_path, "r") as zf:
            manifest = json.loads(zf.read("manifest.json").decode())
            return BackupPreview(
                history_count=manifest["contents"].get("history", 0),
                template_count=manifest["contents"].get("templates", 0),
                source_count=manifest["contents"].get("sources", 0),
                has_keys="keys" in manifest["contents"]
            )

    async def import_data(self, file_path: str, options: ImportOptions) -> ImportResult:
        """导入数据"""
        result = ImportResult(0, 0, 0, 0)

        with zipfile.ZipFile(file_path, "r") as zf:
            if options.include_history and "history.json" in zf.namelist():
                history_data = json.loads(zf.read("history.json").decode())
                for record in history_data:
                    await self.history_manager.save_record(record)
                result.imported_history = len(history_data)

            if options.include_templates and "templates.json" in zf.namelist():
                templates = json.loads(zf.read("templates.json").decode())
                for t in templates:
                    await self.prompt_manager.save_template(t)
                result.imported_templates = len(templates)

            if options.include_sources and "sources.json" in zf.namelist():
                sources = json.loads(zf.read("sources.json").decode())
                for s in sources:
                    await self.db.save_source(s)
                result.imported_sources = len(sources)

            if options.include_keys and "keys.ikey" in zf.namelist() and options.key_password:
                keys_path = file_path + ".keys.tmp"
                try:
                    with open(keys_path, "wb") as f:
                        f.write(zf.read("keys.ikey"))
                    count = self.key_vault.import_encrypted(keys_path, options.key_password)
                finally:
                    if os.path.exists(keys_path):
                        os.remove(keys_path)
                result.imported_keys = count

        return result