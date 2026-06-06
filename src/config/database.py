import aiosqlite
import json
import os
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4
from ..config import constants

ALLOWED_UPDATE_COLUMNS = frozenset({
    "status", "error", "image_path", "thumbnail_path",
    "completed_at", "result_paths_json", "diagnostic",
    "response_summary",
})


class Database:
    _instance: Optional["Database"] = None

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or constants.DEFAULT_DB_PATH
        self._conn: Optional[aiosqlite.Connection] = None
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> "Database":
        if cls._instance is None:
            cls._instance = cls(db_path)
        return cls._instance

    async def connect(self):
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA cache_size=-8000")
            await self._init_tables()

    async def _init_tables(self):
        cursor = await self._conn.execute("PRAGMA user_version")
        row = await cursor.fetchone()
        current_version = row[0] if row else 0

        if current_version == 0:
            await self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS prompt_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    negative_prompt TEXT,
                    platform_id TEXT,
                    params TEXT,
                    category TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS generation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL UNIQUE,
                    platform_id TEXT,
                    prompt TEXT,
                    negative_prompt TEXT,
                    params TEXT,
                    image_path TEXT,
                    thumbnail_path TEXT,
                    seed TEXT,
                    status TEXT,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    interface_type TEXT NOT NULL DEFAULT 'openai_images',
                    auth_preset TEXT NOT NULL DEFAULT 'openai',
                    api_base_url TEXT NOT NULL,
                    api_key_encrypted BLOB,
                    custom_headers TEXT,
                    proxy TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS source_models (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    default_size TEXT DEFAULT '1024x1024',
                    default_quality TEXT DEFAULT 'standard',
                    default_n INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS reference_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT UNIQUE,
                    path TEXT,
                    width INTEGER,
                    height INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS app_prefs (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)

        if current_version < 1:
            await self._ensure_column("sources", "response_format", "TEXT")
            await self._ensure_column("generation_history", "source_id", "TEXT")
            await self._ensure_column("generation_history", "model_config_id", "TEXT")
            await self._ensure_column("generation_history", "request_url", "TEXT")
            await self._ensure_column("generation_history", "request_payload", "TEXT")
            await self._ensure_column("generation_history", "response_summary", "TEXT")
            await self._ensure_column("generation_history", "diagnostic", "TEXT")
            await self._ensure_column("generation_history", "result_paths_json", "TEXT")
            await self._ensure_column("generation_history", "category", "TEXT")
            await self._ensure_column("generation_history", "tags", "TEXT")
            await self._ensure_column("source_models", "reference_image_enabled", "INTEGER DEFAULT 0")
            await self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_created_at ON generation_history(created_at DESC)"
            )
            await self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_task_id ON generation_history(task_id)"
            )
            await self.migrate_legacy_openai_config()

        if current_version < 2:
            await self._migrate_to_v2()

        target_version = 2
        if current_version < target_version:
            await self._conn.execute(f"PRAGMA user_version = {target_version}")
            await self._conn.commit()

    async def _ensure_column(self, table_name: str, column_name: str, column_type: str):
        cursor = await self._conn.execute(f"PRAGMA table_info({table_name})")
        columns = await cursor.fetchall()
        if column_name not in {column[1] for column in columns}:
            await self._conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params=None):
        await self._conn.execute(sql, params or ())
        await self._conn.commit()

    async def fetchone(self, sql: str, params=None):
        cursor = await self._conn.execute(sql, params or ())
        return await cursor.fetchone()

    async def fetchall(self, sql: str, params=None):
        cursor = await self._conn.execute(sql, params or ())
        return await cursor.fetchall()

    # 来源/模型 CRUD
    async def get_sources(self, active_only: bool = False) -> list[dict]:
        sql = """
            SELECT id, name, interface_type, auth_preset, api_base_url,
                   api_key_encrypted, custom_headers, proxy, is_active,
                   response_format
            FROM sources
        """
        if active_only:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY created_at ASC, name ASC"
        rows = await self.fetchall(sql)
        return [self._row_to_source(row) for row in rows]

    async def get_source(self, source_id: str) -> Optional[dict]:
        row = await self.fetchone(
            """
            SELECT id, name, interface_type, auth_preset, api_base_url,
                   api_key_encrypted, custom_headers, proxy, is_active,
                   response_format
            FROM sources WHERE id = ?
            """,
            (source_id,),
        )
        return self._row_to_source(row) if row else None

    async def save_source(self, source: dict):
        source_id = source.get("id") or f"src_{uuid4().hex}"
        api_key_encrypted = source.get("api_key_encrypted")
        if api_key_encrypted is None:
            existing = await self.get_source(source_id)
            if existing:
                api_key_encrypted = existing.get("api_key_encrypted")
        await self.execute(
            """
            INSERT OR REPLACE INTO sources
            (id, name, interface_type, auth_preset, api_base_url, api_key_encrypted,
             custom_headers, proxy, is_active, response_format)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                source["name"],
                source.get("interface_type", "openai_images"),
                source.get("auth_preset", "openai"),
                source.get("api_base_url", ""),
                api_key_encrypted,
                source.get("custom_headers"),
                source.get("proxy"),
                source.get("is_active", 1),
                source.get("response_format", "openai"),
            ),
        )
        return source_id

    async def delete_source(self, source_id: str):
        await self.execute("DELETE FROM source_models WHERE source_id = ?", (source_id,))
        await self.execute("DELETE FROM sources WHERE id = ?", (source_id,))

    async def get_source_models(self, source_id: str | None = None, active_only: bool = False) -> list[dict]:
        sql = """
            SELECT id, source_id, display_name, model_id, default_size,
                   default_quality, default_n, sort_order, is_active,
                   reference_image_enabled
            FROM source_models
        """
        clauses = []
        params = []
        if source_id:
            clauses.append("source_id = ?")
            params.append(source_id)
        if active_only:
            clauses.append("is_active = 1")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY sort_order ASC, created_at ASC, display_name ASC"
        rows = await self.fetchall(sql, params)
        return [self._row_to_source_model(row) for row in rows]

    async def get_source_model(self, model_id: str) -> Optional[dict]:
        row = await self.fetchone(
            """
            SELECT id, source_id, display_name, model_id, default_size,
                   default_quality, default_n, sort_order, is_active,
                   reference_image_enabled
            FROM source_models WHERE id = ?
            """,
            (model_id,),
        )
        return self._row_to_source_model(row) if row else None

    async def save_source_model(self, model: dict):
        model_config_id = model.get("id") or f"mdl_{uuid4().hex}"
        await self.execute(
            """
            INSERT OR REPLACE INTO source_models
            (id, source_id, display_name, model_id, default_size, default_quality,
             default_n, sort_order, is_active, reference_image_enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_config_id,
                model["source_id"],
                model["display_name"],
                model["model_id"],
                model.get("default_size", "1024x1024"),
                model.get("default_quality", "standard"),
                self._safe_int(model.get("default_n", 1), 1),
                self._safe_int(model.get("sort_order", 0), 0),
                model.get("is_active", 1),
                int(model.get("reference_image_enabled", False)),
            ),
        )
        return model_config_id

    def _safe_int(self, value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    async def delete_source_model(self, model_id: str):
        await self.execute("DELETE FROM source_models WHERE id = ?", (model_id,))

    async def get_pref(self, key: str, default: str = "") -> str:
        row = await self.fetchone("SELECT value FROM app_prefs WHERE key = ?", (key,))
        return row[0] if row else default

    async def set_pref(self, key: str, value: str):
        await self.execute(
            "INSERT OR REPLACE INTO app_prefs (key, value) VALUES (?, ?)",
            (key, value),
        )

    async def _migrate_to_v2(self):
        """迁移到版本2：添加任务链表、历史标签字段"""
        await self.execute("""
            CREATE TABLE IF NOT EXISTS task_chains (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'idle',
                failure_mode TEXT DEFAULT 'stop',
                tasks_json TEXT NOT NULL
            )
        """)
        await self._ensure_column("generation_history", "tags", "TEXT")

    async def _migrate_to_v3(self):
        """迁移到版本3：添加密钥加密存储（预留）"""
        pass

    async def migrate_legacy_openai_config(self):
        existing = await self.get_sources()
        if existing:
            return
        try:
            row = await self.fetchone(
                "SELECT id, name, api_base_url, api_key_encrypted, custom_headers, "
                "model_name, proxy, is_active FROM platform_configs WHERE id = ?",
                ("openai",),
            )
        except Exception:
            return
        if not row or not row[2]:
            return
        legacy = {
            "id": row[0], "name": row[1], "api_base_url": row[2],
            "api_key_encrypted": row[3], "custom_headers": row[4],
            "model_name": row[5] or "", "proxy": row[6], "is_active": row[7],
        }
        source_id = "legacy_openai"
        await self.save_source({
            "id": source_id,
            "name": legacy.get("name") or "OpenAI 兼容来源",
            "interface_type": "openai_images",
            "auth_preset": "openai",
            "api_base_url": legacy.get("api_base_url", ""),
            "api_key_encrypted": legacy.get("api_key_encrypted"),
            "custom_headers": legacy.get("custom_headers"),
            "proxy": legacy.get("proxy"),
            "is_active": legacy.get("is_active", 1),
        })
        model_name = legacy.get("model_name") or "gpt-image-1"
        await self.save_source_model({
            "id": "legacy_openai_model",
            "source_id": source_id,
            "display_name": model_name,
            "model_id": model_name,
            "default_size": "1024x1024",
            "default_quality": "standard",
            "default_n": 1,
            "sort_order": 0,
            "is_active": 1,
        })

    def _row_to_source(self, row) -> dict:
        return {
            "id": row[0], "name": row[1], "interface_type": row[2],
            "auth_preset": row[3], "api_base_url": row[4],
            "api_key_encrypted": row[5], "custom_headers": row[6],
            "proxy": row[7], "is_active": row[8],
            "response_format": row[9] if len(row) > 9 else "openai",
        }

    def _row_to_source_model(self, row) -> dict:
        return {
            "id": row[0], "source_id": row[1], "display_name": row[2],
            "model_id": row[3], "default_size": row[4],
            "default_quality": row[5], "default_n": row[6],
            "sort_order": row[7], "is_active": row[8],
            "reference_image_enabled": bool(row[9]) if len(row) > 9 else False,
        }

    # 提示词模板 CRUD
    async def get_prompt_templates(self, category: str = None) -> list[dict]:
        if category:
            rows = await self.fetchall(
                "SELECT * FROM prompt_templates WHERE category = ? ORDER BY created_at DESC",
                (category,)
            )
        else:
            rows = await self.fetchall("SELECT * FROM prompt_templates ORDER BY created_at DESC")
        return [self._row_to_template(r) for r in rows]

    async def save_prompt_template(self, template: dict) -> int:
        cursor = await self._conn.execute("""
            INSERT INTO prompt_templates (name, prompt, negative_prompt, platform_id, params, category, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            template["name"], template["prompt"], template.get("negative_prompt"),
            template.get("platform_id"), json.dumps(template.get("params", {})),
            template.get("category"), template.get("tags"),
        ))
        await self._conn.commit()
        return cursor.lastrowid

    async def delete_prompt_template(self, template_id: int):
        await self.execute("DELETE FROM prompt_templates WHERE id = ?", (template_id,))

    async def get_history_by_task_id(self, task_id: str) -> Optional[dict]:
        row = await self.fetchone(
            "SELECT * FROM generation_history WHERE task_id = ?", (task_id,)
        )
        return self._row_to_history(row) if row else None

    async def delete_generation_history(self, task_id: str):
        await self.execute("DELETE FROM generation_history WHERE task_id = ?", (task_id,))

    def _row_to_template(self, row) -> dict:
        return {
            "id": row[0], "name": row[1], "prompt": row[2],
            "negative_prompt": row[3], "platform_id": row[4],
            "params": json.loads(row[5]) if row[5] else {},
            "category": row[6], "tags": row[7], "created_at": row[8],
        }

    # 历史记录 CRUD
    async def save_generation_history(self, record: dict):
        await self.execute("""
            INSERT OR REPLACE INTO generation_history
            (task_id, platform_id, prompt, negative_prompt, params, image_path,
             thumbnail_path, seed, status, error, created_at, completed_at,
             source_id, model_config_id, request_url, request_payload, response_summary,
             diagnostic, result_paths_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["task_id"], record.get("platform_id"), record.get("prompt"),
            record.get("negative_prompt"), json.dumps(record.get("params", {})),
            record.get("image_path"), record.get("thumbnail_path"),
            record.get("seed"), record.get("status"),
            record.get("error"), record.get("created_at"), record.get("completed_at"),
            record.get("source_id"), record.get("model_config_id"), record.get("request_url"),
            json.dumps(record.get("request_payload", {}), ensure_ascii=False),
            record.get("response_summary"), json.dumps(record.get("diagnostic", {}), ensure_ascii=False),
            json.dumps(record.get("result_paths_json", []), ensure_ascii=False),
        ))

    async def get_generation_history(self, limit: int = 100, offset: int = 0) -> list[dict]:
        rows = await self.fetchall(
            "SELECT * FROM generation_history ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return [self._row_to_history(r) for r in rows]

    async def update_history_status(self, task_id: str, status: str, **kwargs):
        for key in kwargs:
            if key not in ALLOWED_UPDATE_COLUMNS:
                raise ValueError(f"Disallowed column name: {key}")
        sets = ["status = ?"]
        vals: list[Any] = [status]
        for k, v in kwargs.items():
            # status is always set first from the positional arg; skip duplicates
            # to avoid `SET status = ?, status = ?, ...` in the generated SQL.
            if k == "status":
                continue
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(task_id)
        await self.execute(
            f"UPDATE generation_history SET {', '.join(sets)} WHERE task_id = ?",
            vals
        )

    async def update_history_category(self, task_id: str, category: str):
        """更新历史记录的分类"""
        await self.execute(
            "UPDATE generation_history SET category = ? WHERE task_id = ?",
            (category, task_id),
        )

    async def update_history_tags(self, task_id: str, tags: list[str]):
        """更新历史记录的标签"""
        await self.execute(
            "UPDATE generation_history SET tags = ? WHERE task_id = ?",
            (",".join(tags), task_id),
        )

    def _row_to_history(self, row) -> dict:
        return {
            "id": row[0], "task_id": row[1], "platform_id": row[2],
            "prompt": row[3], "negative_prompt": row[4],
            "params": json.loads(row[5]) if row[5] else {},
            "image_path": row[6], "thumbnail_path": row[7],
            "seed": row[8], "status": row[9], "error": row[10],
            "created_at": row[11], "completed_at": row[12],
            "source_id": row[13] if len(row) > 13 else None,
            "model_config_id": row[14] if len(row) > 14 else None,
            "request_url": row[15] if len(row) > 15 else None,
            "request_payload": json.loads(row[16]) if len(row) > 16 and row[16] else {},
            "response_summary": row[17] if len(row) > 17 else None,
            "diagnostic": json.loads(row[18]) if len(row) > 18 and row[18] else {},
            "result_paths": json.loads(row[19]) if len(row) > 19 and row[19] else ([row[6]] if row[6] else []),
            "category": row[20] if len(row) > 20 else None,
            "tags": row[21] if len(row) > 21 else None,
        }
