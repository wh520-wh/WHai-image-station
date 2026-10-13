"""Reference-field compatibility and migration for saved application data."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from pathlib import Path

from src.config.database import Database
from src.managers.image_assets import reference_dir, retain_reference


def get_reference_path(settings: dict) -> str | None:
    return settings.get("reference_image_path") or (settings.get("params") or {}).get("reference_image_path")


def replace_reference_path(settings: dict, path: str) -> dict:
    saved = deepcopy(settings)
    if saved.get("reference_image_path"):
        saved["reference_image_path"] = path
    else:
        saved["params"] = dict(saved.get("params") or {}, reference_image_path=path)
    return saved


async def retain_settings(settings: dict, missing_ok=False) -> dict:
    reference = get_reference_path(settings)
    if not reference or (missing_ok and not Path(reference).is_file()):
        return deepcopy(settings)
    if missing_ok and Path(reference).parent.resolve() == reference_dir().resolve():
        return deepcopy(settings)
    retained = await asyncio.to_thread(retain_reference, reference)
    return replace_reference_path(settings, retained)


async def migrate_references(db: Database):
    """Retain readable legacy references; leave broken paths available for replacement."""
    for template in await db.get_prompt_templates():
        try:
            saved = await retain_settings(template, missing_ok=True)
        except (OSError, ValueError):
            continue
        if saved != template:
            await db.execute(
                "UPDATE prompt_templates SET params = ? WHERE id = ?",
                (json.dumps(saved["params"]), template["id"]),
            )
    for chain_id, raw in await db.fetchall("SELECT id, tasks_json FROM task_chains"):
        tasks = json.loads(raw or "[]")
        saved = []
        for task in tasks:
            try:
                saved.append(await retain_settings(task, missing_ok=True))
            except (OSError, ValueError):
                saved.append(task)
        if saved != tasks:
            await db.execute("UPDATE task_chains SET tasks_json = ? WHERE id = ?", (json.dumps(saved), chain_id))
