from typing import Optional

from src.config import database


class PromptManager:
    _instance: Optional["PromptManager"] = None

    def __init__(self, db: database.Database | None = None):
        self._db = db

    @classmethod
    def get_instance(cls) -> "PromptManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self, db: database.Database):
        self._db = db

    async def get_templates(self, category: str | None = None) -> list[dict]:
        if not self._db:
            return []
        return await self._db.get_prompt_templates(category)

    async def save_template(self, template: dict) -> int:
        if not self._db:
            return -1
        return await self._db.save_prompt_template(template)

    async def delete_template(self, template_id: int):
        if self._db:
            await self._db.delete_prompt_template(template_id)

    async def get_categories(self) -> list[str]:
        """获取所有分类"""
        if not self._db:
            return []
        rows = await self._db.fetchall(
            "SELECT DISTINCT category FROM prompt_templates WHERE category IS NOT NULL AND category != ''"
        )
        return [row[0] for row in rows if row[0]]
