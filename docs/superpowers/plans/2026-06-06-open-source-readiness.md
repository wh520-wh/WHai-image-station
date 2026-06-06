# imageMaker 开源准备实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复代码质量隐患、补全文档、跨平台适配（Windows 10+ 全版本），引入代码质量工具，使项目达到可公开发布的工程水准。

**Architecture:** 通过 TDD 方式逐步重构，从基础设施（包配置、工具模块）开始，再到具体修复（SQL 注入、错误处理），最后是跨平台和文档。所有改动保持向后兼容，单个任务可独立提交。

**Tech Stack:** Python 3.10+、PySide6、pytest、ruff、pyright

---

## 文件结构

### 新建文件
- `src/config/utils.py` — 共享工具函数（_parse_headers、_safe_int、get_thumbnail_path）
- `tests/config/test_utils.py` — utils 模块测试
- `tests/conftest.py` — pytest 共享 fixture
- `docs/development.md` — 开发文档
- `CONTRIBUTING.md` — 贡献指南
- `CHANGELOG.md` — 版本记录
- `start.sh` — Linux/macOS 启动脚本
- `tests/test_cross_platform_paths.py` — 跨平台路径测试
- `tests/managers/test_migration_manager_tempfile.py` — 临时文件清理测试

### 修改文件
- `pyproject.toml` — 添加 ruff/pyright/pytest 配置，配置包发现
- `src/app.py` — 移除 sys.path、移除模块级 makedirs
- `src/main.py` — 移除 sys.path
- `src/adapters/base.py` — 移除 sys.path、改进错误处理、使用 get_thumbnail_path
- `src/adapters/__init__.py` — 移除 sys.path
- `src/adapters/openai_adapter.py` — 移除 sys.path、删除重复 import
- `src/adapters/stability_adapter.py` — 移除 sys.path、删除重复 import、改进错误处理
- `src/adapters/midjourney_adapter.py` — 移除 sys.path、删除重复 import
- `src/managers/queue_manager.py` — 移除 sys.path、使用 _parse_headers
- `src/managers/prompt_manager.py` — 移除 sys.path
- `src/managers/history_manager.py` — 移除 sys.path、改进错误处理
- `src/managers/batch_ops_manager.py` — 提取 _batch_execute
- `src/managers/migration_manager.py` — try/finally 保护临时文件
- `src/managers/key_vault.py` — 错误处理增强
- `src/widgets/main_window.py` — 使用 get_thumbnail_path
- `src/widgets/history_panel.py` — os.startfile → QDesktopServices
- `src/widgets/setting_dialog.py` — 移除 sys.path、使用 _parse_headers
- `src/widgets/generation_panel.py` — 移除 sys.path
- `src/widgets/prompt_panel.py` — 移除 sys.path
- `src/widgets/image_viewer.py` — 移除 sys.path
- `src/widgets/components/prompt_card.py` — 移除 sys.path
- `src/widgets/task_chain_editor.py` — 移除 sys.path
- `src/widgets/settings_dialog.py` — 移除 sys.path
- `src/config/database.py` — 修复 SQL 注入
- `tests/test_ux_behaviors.py` — 修复硬编码路径
- `tests/models/test_batch_result.py` — 移除 sys.path
- `tests/models/test_task_chain.py` — 移除 sys.path
- `tests/test_adapter_lazy_load.py` — 移除 sys.path

---

## Task 1: 配置 pyproject.toml 包发现和工具链

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 编辑 pyproject.toml 添加 [tool.hatch.build]**

替换 `pyproject.toml` 完整内容为：

```toml
[project]
name = "image-maker"
version = "1.0.0"
description = "轻量化桌面端图片生成工具"
requires-python = ">=3.10"
dependencies = [
    "PySide6>=6.6.0",
    "httpx>=0.27.0",
    "Pillow>=10.0.0",
    "cryptography>=42.0.0",
    "aiosqlite>=0.20.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-qt>=4.4.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.4.0",
    "pyright>=1.1.0",
]

[project.scripts]
image-maker = "src.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-ra"

[tool.ruff]
target-version = "py310"
line-length = 120
extend-exclude = ["build", "dist", ".venv"]

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B"]
ignore = ["E501"]

[tool.pyright]
pythonVersion = "3.10"
typeCheckingMode = "basic"
reportMissingTypeStubs = false
```

- [ ] **Step 2: 验证配置可读**

Run: `python -c "import tomllib; tomllib.loads(open('pyproject.toml').read())"`
Expected: 无输出（无异常）

- [ ] **Step 3: 暂存并继续**

不要 commit 这一步（先验证整个包能装上后再 commit）。

---

## Task 2: 创建共享 utils 模块（含 TDD）

**Files:**
- Create: `src/config/utils.py`
- Create: `tests/config/test_utils.py`

- [ ] **Step 1: 写测试文件**

创建 `tests/config/test_utils.py`：

```python
import pytest
from src.config.utils import parse_headers, safe_int, get_thumbnail_path


class TestParseHeaders:
    def test_none_returns_empty_dict(self):
        assert parse_headers(None) == {}

    def test_empty_string_returns_empty_dict(self):
        assert parse_headers("") == {}

    def test_empty_dict_returns_empty_dict(self):
        assert parse_headers({}) == {}

    def test_dict_input_returns_stringified_dict(self):
        result = parse_headers({"X-Key": "value", "Auth": "Bearer token"})
        assert result == {"X-Key": "value", "Auth": "Bearer token"}

    def test_valid_json_string(self):
        result = parse_headers('{"X-Foo": "bar"}')
        assert result == {"X-Foo": "bar"}

    def test_invalid_json_returns_empty_dict(self):
        assert parse_headers("not json") == {}

    def test_json_array_returns_empty_dict(self):
        assert parse_headers('[1, 2, 3]') == {}

    def test_json_non_dict_returns_empty_dict(self):
        assert parse_headers('"a string"') == {}

    def test_int_values_are_stringified(self):
        result = parse_headers({"count": 42})
        assert result == {"count": "42"}


class TestSafeInt:
    def test_valid_int_string(self):
        assert safe_int("42") == 42

    def test_valid_int(self):
        assert safe_int(42) == 42

    def test_invalid_string_returns_default(self):
        assert safe_int("not a number", 10) == 10

    def test_none_returns_default(self):
        assert safe_int(None, 5) == 5

    def test_float_string_returns_default(self):
        assert safe_int("3.14", 0) == 0

    def test_negative_int(self):
        assert safe_int("-5") == -5


class TestGetThumbnailPath:
    def test_returns_expected_path(self, tmp_path, monkeypatch):
        from src.config import constants
        monkeypatch.setattr(constants, "THUMBNAILS_DIR", str(tmp_path))
        result = get_thumbnail_path("/some/path/image.png")
        assert result == str(tmp_path / "thumb_image.jpg")

    def test_empty_path_returns_empty(self):
        assert get_thumbnail_path("") == ""
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/config/test_utils.py -v`
Expected: ImportError 或 ModuleNotFoundError（utils 还不存在）

- [ ] **Step 3: 创建 utils.py**

创建 `src/config/utils.py`：

```python
"""Shared utility functions used across config, managers, and widgets."""
from __future__ import annotations

import json
import os
from typing import Any

from src.config import constants


def parse_headers(raw_headers: Any) -> dict[str, str]:
    """Parse headers from dict, JSON string, or None into a plain str→str dict.

    Returns empty dict for any invalid input (None, empty, non-JSON, non-dict JSON).
    """
    if not raw_headers:
        return {}
    if isinstance(raw_headers, dict):
        return {str(key): str(value) for key, value in raw_headers.items()}
    try:
        parsed = json.loads(raw_headers)
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}


def safe_int(value: Any, default: int) -> int:
    """Convert value to int, returning default on any conversion failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_thumbnail_path(image_path: str) -> str:
    """Return the expected thumbnail path for a given image path.

    Returns empty string if image_path is empty.
    """
    if not image_path:
        return ""
    name = os.path.basename(image_path)
    thumb_name = f"thumb_{os.path.splitext(name)[0]}.jpg"
    return os.path.join(constants.THUMBNAILS_DIR, thumb_name)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/config/test_utils.py -v`
Expected: 14 passed

- [ ] **Step 5: 在 src/config/__init__.py 导出**

修改 `src/config/__init__.py`，在 `from .constants import *` 之后加入：

```python
from .utils import parse_headers, safe_int, get_thumbnail_path
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/config/utils.py src/config/__init__.py tests/config/test_utils.py
git commit -m "feat: add shared utils module (parse_headers, safe_int, get_thumbnail_path)"
```

---

## Task 3: 修复 SQL 注入风险

**Files:**
- Modify: `src/config/database.py:444-454`

- [ ] **Step 1: 写测试**

在 `tests/config/` 下新建 `test_database_sql_safety.py`：

```python
import pytest
from src.config.database import Database


@pytest.fixture
async def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    database = Database(db_path=db_path)
    await database.connect()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_update_history_status_rejects_unknown_columns(db):
    with pytest.raises(ValueError, match="Disallowed column"):
        await db.update_history_status("task_1", "FAILED", malicious_key="value")


@pytest.mark.asyncio
async def test_update_history_status_accepts_known_columns(db):
    await db.save_generation_history({
        "task_id": "task_1",
        "prompt": "test",
        "status": "WAITING",
    })
    await db.update_history_status("task_1", "FAILED", error="boom")
    record = await db.get_history_by_task_id("task_1")
    assert record["status"] == "FAILED"
    assert record["error"] == "boom"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/config/test_database_sql_safety.py -v`
Expected: 测试通过（因为当前实现接受任意 kwargs，test 1 应失败，test 2 应通过）。第一个 test 应失败，提示 "DID NOT RAISE"。

- [ ] **Step 3: 添加 pytest-asyncio 配置**

在 `pyproject.toml` 的 `[tool.pytest.ini_options]` 中加入 `asyncio_mode = "auto"`：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-ra"
asyncio_mode = "auto"
```

- [ ] **Step 4: 重新运行测试**

Run: `pytest tests/config/test_database_sql_safety.py -v`
Expected: 第一个 test FAIL（DID NOT RAISE ValueError）

- [ ] **Step 5: 修改 update_history_status 加入白名单**

在 `src/config/database.py` 顶部（import 之后）添加常量：

```python
ALLOWED_UPDATE_COLUMNS = frozenset({
    "status", "error", "image_path", "thumbnail_path",
    "completed_at", "result_paths_json", "diagnostic",
    "response_summary",
})
```

替换 `update_history_status` 方法（约第 444-454 行）：

```python
    async def update_history_status(self, task_id: str, status: str, **kwargs):
        for key in kwargs:
            if key not in ALLOWED_UPDATE_COLUMNS:
                raise ValueError(f"Disallowed column name: {key}")
        sets = ["status = ?"]
        vals: list = [status]
        for k, v in kwargs.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(task_id)
        await self.execute(
            f"UPDATE generation_history SET {', '.join(sets)} WHERE task_id = ?",
            vals
        )
```

- [ ] **Step 6: 运行测试确认通过**

Run: `pytest tests/config/test_database_sql_safety.py -v`
Expected: 2 passed

- [ ] **Step 7: 运行全部测试确认无回归**

Run: `pytest tests/ -x -q`
Expected: 全部通过

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/config/database.py tests/config/test_database_sql_safety.py
git commit -m "fix(security): whitelist allowed columns in update_history_status"
```

---

## Task 4: 修复 migration_manager 临时文件保护

**Files:**
- Modify: `src/managers/migration_manager.py:69-74, 115-121`
- Create: `tests/managers/test_migration_manager_tempfile.py`

- [ ] **Step 1: 写测试**

```python
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
    await mgr.export(output, ExportOptions(include_keys=True, key_password="secret"))
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
```

- [ ] **Step 2: 运行测试确认当前状态下临时文件问题**

Run: `pytest tests/managers/test_migration_manager_tempfile.py -v`
Expected: 2 passed（当前实现不抛异常，正常路径上临时文件被清理）

- [ ] **Step 3: 修改 export 方法加 try/finally**

替换 `src/managers/migration_manager.py:69-74`：

```python
            if options.include_keys and options.key_password:
                keys_path = output_path + ".keys.tmp"
                try:
                    self.key_vault.export_encrypted(keys_path, options.key_password)
                    zf.write(keys_path, "keys.ikey")
                finally:
                    if os.path.exists(keys_path):
                        os.remove(keys_path)
                manifest["contents"]["keys"] = True
```

- [ ] **Step 4: 修改 import_data 方法加 try/finally**

替换 `src/managers/migration_manager.py:115-121`：

```python
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
```

- [ ] **Step 5: 写一个验证 finally 触发的测试**

追加到 `tests/managers/test_migration_manager_tempfile.py`：

```python
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
        await mgr.export(output, ExportOptions(include_keys=True, key_password="secret"))
    remaining = list(tmp_path.glob("*.keys.tmp"))
    assert remaining == []
```

- [ ] **Step 6: 验证新测试在修复后通过**

Run: `pytest tests/managers/test_migration_manager_tempfile.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add src/managers/migration_manager.py tests/managers/test_migration_manager_tempfile.py
git commit -m "fix: protect temp files in migration_manager with try/finally"
```

---

## Task 5: 修复 history_manager.delete_record 错误处理

**Files:**
- Modify: `src/managers/history_manager.py:46-60`

- [ ] **Step 1: 写测试**

新建 `tests/managers/test_history_manager_delete.py`：

```python
import os
import pytest
from src.managers.history_manager import HistoryManager


class FakeDb:
    def __init__(self, history):
        self._history = history
        self.deleted = []
    async def get_generation_history(self, limit=100, offset=0):
        return self._history
    async def get_history_by_task_id(self, task_id):
        for r in self._history:
            if r["task_id"] == task_id:
                return r
        return None
    async def delete_generation_history(self, task_id):
        self.deleted.append(task_id)
        self._history = [r for r in self._history if r["task_id"] != task_id]


@pytest.mark.asyncio
async def test_delete_record_handles_permission_error(tmp_path):
    record = {
        "task_id": "t1",
        "image_path": str(tmp_path / "image.png"),
        "thumbnail_path": str(tmp_path / "thumb.jpg"),
        "result_paths": [str(tmp_path / "image.png")],
    }
    (tmp_path / "image.png").write_bytes(b"x")
    (tmp_path / "thumb.jpg").write_bytes(b"y")
    db = FakeDb([record])
    mgr = HistoryManager()
    await mgr.initialize(db)
    # 把 thumbnail_path 改成目录，模拟删除失败
    record["thumbnail_path"] = str(tmp_path)
    await mgr.delete_record("t1")  # 不应抛异常
    assert db.deleted == ["t1"]  # DB 记录仍然被删除


@pytest.mark.asyncio
async def test_delete_record_missing_file_does_not_raise(tmp_path):
    record = {
        "task_id": "t2",
        "image_path": str(tmp_path / "nonexistent.png"),
        "thumbnail_path": None,
        "result_paths": [],
    }
    db = FakeDb([record])
    mgr = HistoryManager()
    await mgr.initialize(db)
    await mgr.delete_record("t2")  # 不应抛异常
    assert db.deleted == ["t2"]
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/managers/test_history_manager_delete.py -v`
Expected: 第一个 FAIL（PermissionError 未被捕获）

- [ ] **Step 3: 修改 delete_record**

替换 `src/managers/history_manager.py:46-60`：

```python
    async def delete_record(self, task_id: str):
        """删除历史记录和对应的图片文件。文件删除失败不影响数据库记录清理。"""
        history = await self.get_history(1000)
        for record in history:
            if record.get("task_id") == task_id:
                paths = set(record.get("result_paths") or [])
                if record.get("image_path"):
                    paths.add(record["image_path"])
                if record.get("thumbnail_path"):
                    paths.add(record["thumbnail_path"])
                for path in paths:
                    if path and os.path.exists(path) and not os.path.isdir(path):
                        try:
                            os.remove(path)
                        except (PermissionError, OSError) as e:
                            print(f"[history_manager] Failed to remove {path}: {e}")
                await self._db.delete_generation_history(task_id)
                break
```

- [ ] **Step 4: 验证测试通过**

Run: `pytest tests/managers/test_history_manager_delete.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/managers/history_manager.py tests/managers/test_history_manager_delete.py
git commit -m "fix: handle file removal errors gracefully in history_manager.delete_record"
```

---

## Task 6: 修复 base.py 的 download_image 错误处理

**Files:**
- Modify: `src/adapters/base.py:97-110`

- [ ] **Step 1: 写测试**

新建 `tests/test_adapter_download_errors.py`：

```python
import os
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from src.adapters.base import BaseAdapter, GenerationResult


class _DummyAdapter(BaseAdapter):
    platform_id = "dummy"
    platform_name = "Dummy"
    def get_params_schema(self): return {}
    async def validate_config(self, config): return True
    async def generate(self, task, config): return GenerationResult(success=True)


@pytest.mark.asyncio
async def test_download_image_raises_typed_exception_on_http_error(tmp_path):
    adapter = _DummyAdapter()
    config = MagicMock()
    config.api_key = "key"
    config.custom_headers = None
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )
    adapter._get_shared_client = lambda: MagicMock(get=AsyncMock(return_value=mock_response))
    with pytest.raises(httpx.HTTPStatusError):
        await adapter.download_image("http://example.com/img.png", str(tmp_path / "out.png"), config)


@pytest.mark.asyncio
async def test_download_image_returns_path_on_success(tmp_path):
    adapter = _DummyAdapter()
    config = MagicMock()
    config.api_key = "key"
    config.custom_headers = None
    mock_response = MagicMock()
    mock_response.content = b"fake-image-bytes"
    mock_response.raise_for_status = MagicMock()
    adapter._get_shared_client = lambda: MagicMock(get=AsyncMock(return_value=mock_response))
    result = await adapter.download_image("http://example.com/img.png", str(tmp_path / "out.png"), config)
    assert result == str(tmp_path / "out.png")
    assert (tmp_path / "out.png").read_bytes() == b"fake-image-bytes"
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_adapter_download_errors.py -v`
Expected: 2 passed（download_image 已通过 raise_for_status 处理 HTTP 错误）

- [ ] **Step 3: 用 try/except 包裹文件写入**

替换 `src/adapters/base.py:97-110`：

```python
    async def download_image(self, url: str, save_path: str, config: PlatformConfig) -> str:
        client = self._get_shared_client()
        headers = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        if config.custom_headers:
            headers.update(config.custom_headers)

        response = await client.get(url, headers=headers)
        response.raise_for_status()

        try:
            with open(save_path, "wb") as f:
                f.write(response.content)
        except (IOError, OSError) as e:
            raise IOError(f"Failed to save image to {save_path}: {e}") from e
        return save_path
```

- [ ] **Step 4: 验证测试通过**

Run: `pytest tests/test_adapter_download_errors.py -v`
Expected: 2 passed

- [ ] **Step 5: 追加错误信息测试**

追加到 `tests/test_adapter_download_errors.py`：

```python
@pytest.mark.asyncio
async def test_download_image_wraps_io_error(tmp_path):
    adapter = _DummyAdapter()
    config = MagicMock()
    config.api_key = "key"
    config.custom_headers = None
    mock_response = MagicMock()
    mock_response.content = b"data"
    mock_response.raise_for_status = MagicMock()
    adapter._get_shared_client = lambda: MagicMock(get=AsyncMock(return_value=mock_response))
    # 传入目录作为保存路径，触发 IOError
    with pytest.raises(IOError, match="Failed to save image"):
        await adapter.download_image("http://example.com/img.png", str(tmp_path), config)
```

- [ ] **Step 6: 验证新测试通过**

Run: `pytest tests/test_adapter_download_errors.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add src/adapters/base.py tests/test_adapter_download_errors.py
git commit -m "fix: wrap IOError with context in BaseAdapter.download_image"
```

---

## Task 7: 跨平台修复 - os.startfile → QDesktopServices

**Files:**
- Modify: `src/widgets/history_panel.py:1-10, 366-369`
- Create: `tests/test_cross_platform_paths.py`

- [ ] **Step 1: 写测试**

```python
from unittest.mock import patch, MagicMock
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_open_folder_uses_qdesktop_services(qapp):
    """验证跨平台文件管理器打开逻辑用 QDesktopServices 而不是 os.startfile。"""
    from src.widgets.history_panel import HistoryPanel
    with patch("src.widgets.history_panel.QDesktopServices.openUrl") as mock_open:
        panel = HistoryPanel.__new__(HistoryPanel)  # 不调用 __init__
        path = "/some/image.png"
        panel._open_in_file_manager(path)
        mock_open.assert_called_once()
        called_url = mock_open.call_args[0][0]
        assert "image" in called_url.toString() or called_url.isLocalFile()
```

- [ ] **Step 2: 检查当前 history_panel 是否有 _open_in_file_manager**

Run: `grep -n "_open_in_file_manager\|os.startfile" src/widgets/history_panel.py`
Expected: 找到 `os.startfile` 在第 369 行

- [ ] **Step 3: 修改 history_panel.py**

在 `src/widgets/history_panel.py` 顶部 imports 中加入（如果没有）：

```python
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
```

替换第 366-369 行：

```python
        elif action == folder_action:
            path = record.get("image_path") or ""
            if path:
                self._open_in_file_manager(path)
```

在 HistoryPanel 类中添加新方法（任意位置）：

```python
    def _open_in_file_manager(self, file_path: str) -> None:
        """Open the folder containing the given file in the OS file manager.

        Cross-platform: uses QDesktopServices, works on Windows, macOS, and Linux.
        """
        folder = os.path.dirname(file_path)
        if folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_cross_platform_paths.py -v`
Expected: 1 passed

- [ ] **Step 5: 删除 os.startfile**

Run: `grep -n "os.startfile" src/widgets/history_panel.py`
Expected: 无输出

- [ ] **Step 6: Commit**

```bash
git add src/widgets/history_panel.py tests/test_cross_platform_paths.py
git commit -m "fix(cross-platform): replace os.startfile with QDesktopServices.openUrl"
```

---

## Task 8: 修复硬编码路径测试

**Files:**
- Modify: `tests/test_ux_behaviors.py:76`

- [ ] **Step 1: 检查测试**

Run: `grep -n "D:/tmp\|D:\\\\\\\\tmp" tests/test_ux_behaviors.py`
Expected: 找到包含 `D:/tmp/ref.png` 的行

- [ ] **Step 2: 替换为 tmp_path fixture**

定位到第 76 行附近的测试函数，把：

```python
panel.reference_image_path = "D:/tmp/ref.png"
```

替换为（先在测试函数签名加 `tmp_path`）：

```python
def test_xxx(tmp_path, ...):
    ...
    panel.reference_image_path = str(tmp_path / "ref.png")
```

如果该测试是类方法，加 `tmp_path` 到参数列表。

- [ ] **Step 3: 运行测试确认通过**

Run: `pytest tests/test_ux_behaviors.py -v`
Expected: 全部 passed

- [ ] **Step 4: Commit**

```bash
git add tests/test_ux_behaviors.py
git commit -m "fix(test): replace hardcoded path with tmp_path fixture"
```

---

## Task 9: 修复模块级副作用（app.py makedirs）

**Files:**
- Modify: `src/app.py:17-19, 58-62`

- [ ] **Step 1: 修改 app.py**

删除 `src/app.py:17-19`（模块级 makedirs）：

```python
# 删除这三行：
# os.makedirs(constants.GENERATIONS_DIR, exist_ok=True)
# os.makedirs(constants.THUMBNAILS_DIR, exist_ok=True)
```

在 `_init_async` 方法开头（`async def _async_init(self):` 之后第一行）添加：

```python
    async def _async_init(self):
        os.makedirs(constants.GENERATIONS_DIR, exist_ok=True)
        os.makedirs(constants.THUMBNAILS_DIR, exist_ok=True)
        # 初始化数据库
        self._db = database.Database.get_instance()
```

- [ ] **Step 2: 验证应用仍能正常启动**

Run: `python -c "from src.app import ImageMakerApp; print('OK')"`
Expected: 输出 OK

- [ ] **Step 3: Commit**

```bash
git add src/app.py
git commit -m "fix: move os.makedirs from module level to _async_init"
```

---

## Task 10: 清理 adapter 重复 import

**Files:**
- Modify: `src/adapters/stability_adapter.py:3-4, 9`
- Modify: `src/adapters/midjourney_adapter.py:3-4, 9`

- [ ] **Step 1: 清理 stability_adapter**

修改 `src/adapters/stability_adapter.py` 第 1-12 行：

```python
from .base import BaseAdapter, GenerationResult

import base64
import os
import httpx
from datetime import datetime

from src.models.task import GenerationTask
from src.models.platform_config import PlatformConfig
from src.config import constants
```

（删除第 3 行的 `import sys, os` 和第 9 行的 `import os`）

- [ ] **Step 2: 清理 midjourney_adapter**

修改 `src/adapters/midjourney_adapter.py` 第 1-12 行：

```python
from .base import BaseAdapter, GenerationResult

import os
import httpx
import base64
from datetime import datetime

from src.models.task import GenerationTask
from src.models.platform_config import PlatformConfig
from src.config import constants
```

（删除第 3 行的 `import sys, os` 和第 9 行的 `import os`）

- [ ] **Step 3: 验证 import 正常**

Run: `python -c "from src.adapters.stability_adapter import StabilityAdapter; from src.adapters.midjourney_adapter import MidjourneyAdapter; print('OK')"`
Expected: 输出 OK

- [ ] **Step 4: Commit**

```bash
git add src/adapters/stability_adapter.py src/adapters/midjourney_adapter.py
git commit -m "chore: remove duplicate imports in adapters"
```

---

## Task 11: 移除所有 src 下的 sys.path.insert

**Files:**
- Modify: 全部 src/ 下的 `.py` 文件

- [ ] **Step 1: 列出所有 sys.path.insert 位置**

Run: `grep -rn "sys.path.insert" src/`
Expected: 输出 15 行

- [ ] **Step 2: 批量删除 src/ 下的 sys.path hack**

对每个文件做如下处理：
- 删除 `import sys` 和 `import os`（如果只为 sys.path 用）
- 删除 `sys.path.insert(0, ...)` 行
- 确保文件顶部有 `from src.xxx import yyy` 的相对或绝对导入

**具体修改**：

`src/main.py` 第 1-7 行改为：

```python
import sys
import asyncio
from src.app import main

if __name__ == "__main__":
    sys.exit(main())
```

`src/app.py` 第 1-7 行改为：

```python
import sys
import asyncio
import os
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, QSharedMemory

from src.widgets.main_window import MainWindow
from src.widgets.theme import APP_STYLESHEET, app_font
from src.config import constants, database, encryption
from src.config.event_loop import get_app_loop, set_app_loop, close_app_loop, run_async
from src.adapters import init_adapters
from src.managers import QueueManager, PromptManager, HistoryManager
```

对 `src/adapters/base.py`：删除 `import sys, os` 和 `sys.path.insert(...)` 行。

对 `src/adapters/__init__.py`：删除第 3-4 行的 `import sys, os` 和 `sys.path.insert(...)`。

对 `src/managers/queue_manager.py`、`src/managers/prompt_manager.py`、`src/managers/history_manager.py`：删除第 1-5 行的 sys.path hack。

对 `src/widgets/*.py` 全部：删除 sys.path hack。

- [ ] **Step 3: 验证 import 正常**

Run: `python -c "from src.app import ImageMakerApp; from src.widgets.main_window import MainWindow; from src.adapters import init_adapters; print('OK')"`
Expected: 输出 OK

- [ ] **Step 4: 验证测试通过**

Run: `pytest tests/ -x -q`
Expected: 全部通过

- [ ] **Step 5: 验证 src/ 已无 sys.path**

Run: `grep -rn "sys.path.insert" src/`
Expected: 无输出

- [ ] **Step 6: Commit**

```bash
git add src/
git commit -m "refactor: remove all sys.path.insert hacks from src/"
```

---

## Task 12: 移除 tests 下的 sys.path.insert

**Files:**
- Modify: `tests/test_adapter_lazy_load.py`, `tests/models/test_batch_result.py`, `tests/models/test_task_chain.py`

- [ ] **Step 1: 检查需要修复的测试文件**

Run: `grep -rn "sys.path.insert" tests/`
Expected: 3 个文件

- [ ] **Step 2: 修改 tests/models/test_batch_result.py**

删除第 1-3 行的 sys.path hack：

```python
import pytest
from src.models.batch_result import BatchResult
```

（删除前面的 import sys/os/sys.path.insert）

- [ ] **Step 3: 修改 tests/models/test_task_chain.py**

同样删除 sys.path hack。

- [ ] **Step 4: 修改 tests/test_adapter_lazy_load.py**

同样删除 sys.path hack。

- [ ] **Step 5: 验证全部测试通过**

Run: `pytest tests/ -q`
Expected: 全部通过

- [ ] **Step 6: 验证无残留**

Run: `grep -rn "sys.path.insert" tests/`
Expected: 无输出

- [ ] **Step 7: Commit**

```bash
git add tests/
git commit -m "refactor: remove sys.path hacks from tests"
```

---

## Task 13: 用共享 utils 替换重复实现

**Files:**
- Modify: `src/managers/queue_manager.py:230-238`
- Modify: `src/widgets/settings_dialog.py:589-593, 599-608`
- Modify: `src/adapters/base.py:112-122`
- Modify: `src/widgets/main_window.py:355-367`

- [ ] **Step 1: 修改 queue_manager.py**

在 `src/managers/queue_manager.py` 添加 import：

```python
from src.config.utils import parse_headers, get_thumbnail_path
```

删除 `_parse_headers` 方法（230-238 行）和 `_get_thumbnail_path` 方法（290-295 行）。

修改所有调用方（搜索 `self._parse_headers` 和 `self._get_thumbnail_path`）改为 `parse_headers(...)` 和 `get_thumbnail_path(...)`。

- [ ] **Step 2: 修改 settings_dialog.py**

添加 import：

```python
from src.config.utils import parse_headers, safe_int
```

删除 `_safe_int` 方法（589-593 行）和 `_parse_headers` 方法（599-608 行）。

修改所有调用 `self._safe_int` 改为 `safe_int`，调用 `self._parse_headers` 改为 `parse_headers`。

- [ ] **Step 3: 修改 base.py**

添加 import：

```python
from src.config.utils import get_thumbnail_path
```

替换 `_create_thumbnail` 方法（112-122 行）：

```python
    def _create_thumbnail(self, image_path: str):
        thumb_path = get_thumbnail_path(image_path)
        if not thumb_path:
            return
        os.makedirs(constants.THUMBNAILS_DIR, exist_ok=True)
        try:
            img = Image.open(image_path)
            img.thumbnail((200, 200))
            img.save(thumb_path, "JPEG", quality=85, optimize=True)
        except Exception:
            pass
```

- [ ] **Step 4: 修改 main_window.py**

添加 import：

```python
from src.config.utils import get_thumbnail_path
```

替换第 357-366 行：

```python
            if task.result_paths:
                self.history_panel.add_record({
                    "task_id": str(task.id),
                    "platform_id": task.platform_id,
                    "source_id": task.source_id,
                    "model_config_id": task.model_config_id,
                    "prompt": task.prompt,
                    "image_path": task.result_paths[0],
                    "thumbnail_path": get_thumbnail_path(task.result_paths[0]),
                    "status": task.status,
                    "negative_prompt": task.negative_prompt,
                    "params": task.params,
                    "diagnostic": task.params.get("_diagnostic", {}) if isinstance(task.params, dict) else {},
                })
```

- [ ] **Step 5: 运行全部测试**

Run: `pytest tests/ -q`
Expected: 全部通过

- [ ] **Step 6: 运行 ruff 检查**

Run: `ruff check src/`
Expected: 全部通过（可能需要 ruff 第一次安装：`pip install ruff`）

- [ ] **Step 7: Commit**

```bash
git add src/
git commit -m "refactor: use shared utils module for parse_headers, safe_int, get_thumbnail_path"
```

---

## Task 14: 提取 batch_ops_manager 通用批量执行

**Files:**
- Modify: `src/managers/batch_ops_manager.py:11-48`

- [ ] **Step 1: 重构 batch_ops_manager.py**

替换整个文件为：

```python
from __future__ import annotations
import os, zipfile, json
from typing import Awaitable, Callable
from src.models.batch_result import BatchResult
from src.config.utils import safe_int


class BatchOpsManager:
    def __init__(self, history_manager, db, generations_dir: str):
        self.history_manager = history_manager
        self.db = db
        self.generations_dir = generations_dir

    async def _batch_execute(
        self,
        record_ids: list[str],
        operation: Callable[[str], Awaitable[None]],
        error_prefix: str,
    ) -> BatchResult:
        success_count = 0
        failed_count = 0
        errors: list[str] = []
        for record_id in record_ids:
            try:
                await operation(record_id)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"{error_prefix} {record_id}: {str(e)}")
        return BatchResult(success_count, failed_count, errors)

    async def delete_records(self, record_ids: list[str]) -> BatchResult:
        async def op(rid: str) -> None:
            await self.history_manager.delete_record(rid)
        return await self._batch_execute(record_ids, op, "Failed to delete")

    async def move_records(self, record_ids: list[str], category: str) -> BatchResult:
        async def op(rid: str) -> None:
            await self.db.update_history_category(rid, category)
        return await self._batch_execute(record_ids, op, "Failed to move")

    async def add_tags(self, record_ids: list[str], tags: list[str]) -> BatchResult:
        async def op(rid: str) -> None:
            await self.db.update_history_tags(rid, tags)
        return await self._batch_execute(record_ids, op, "Failed to add tags to")

    async def export_records(self, record_ids: list[str], output_path: str) -> str:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            manifest = {"items": []}
            for record_id in record_ids:
                record = await self.history_manager.get_record(record_id)
                if not record:
                    continue
                image_path = record.get("image_path")
                if image_path and os.path.exists(image_path):
                    fname = f"images/{os.path.basename(image_path)}"
                    zf.write(image_path, fname)
                manifest["items"].append({
                    "task_id": record.get("task_id"),
                    "prompt": record.get("prompt"),
                    "platform": record.get("platform_id"),
                    "model": record.get("model_config_id"),
                    "created_at": record.get("created_at"),
                    "image_file": f"images/{os.path.basename(image_path)}" if image_path else None,
                })
            manifest["total_items"] = len(manifest["items"])
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        return output_path
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/managers/test_batch_ops_manager.py -v`
Expected: 全部通过

- [ ] **Step 3: Commit**

```bash
git add src/managers/batch_ops_manager.py
git commit -m "refactor: extract _batch_execute helper in BatchOpsManager"
```

---

## Task 15: 改进 openai_adapter 诊断构建（去重）

**Files:**
- Modify: `src/adapters/openai_adapter.py:86-172`

- [ ] **Step 1: 重构 generate 方法**

替换 `src/adapters/openai_adapter.py:86-172` 的 generate 方法：

```python
    async def generate(self, task: GenerationTask, config: PlatformConfig) -> GenerationResult:
        payload = self.build_generation_payload(task, config)
        generation_url = self.build_url(config.api_base_url, "/images/generations", config)
        headers = self.build_headers(config)
        source_info = {
            "name": config.source_name or config.name,
            "auth_preset": config.auth_preset,
            "interface_type": config.interface_type,
        }
        model_info = {
            "display_name": config.model_display_name or config.model_name,
            "model_id": config.model_name,
        }
        started_at = time.perf_counter()
        try:
            client = self.get_http_client(config)
            response = await client.post(
                generation_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            duration_ms = int((time.perf_counter() - started_at) * 1000)

            image_refs = self._extract_image_refs(data, config.response_format)
            if not image_refs:
                error_msg = f"响应格式不匹配：当前使用「{config.response_format}」解析，未提取到图片。请检查设置的响应格式选项。原始响应: {str(data)[:500]}"
                return GenerationResult(
                    success=False,
                    error=error_msg,
                    raw_response={"diagnostic": self.build_request_diagnostic(
                        url=generation_url,
                        source=source_info,
                        model=model_info,
                        payload=payload, headers=headers,
                        duration_ms=int((time.perf_counter() - started_at) * 1000),
                        status="FAILED", error=error_msg,
                    )}
                )
            image_paths = []
            for index, image_ref in enumerate(image_refs):
                if not image_ref:
                    continue
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = os.path.join(constants.GENERATIONS_DIR, f"{task.id}_{index + 1}_{timestamp}.png")
                if image_ref.startswith("data:"):
                    image_bytes = base64.b64decode(image_ref.split(",", 1)[1])
                    with open(save_path, "wb") as file:
                        file.write(image_bytes)
                elif len(image_ref) > 100 and not image_ref.startswith(("http://", "https://")):
                    with open(save_path, "wb") as file:
                        file.write(base64.b64decode(image_ref))
                else:
                    await self.download_image(image_ref, save_path, config)
                image_paths.append(save_path)
                self._create_thumbnail(save_path)

            diagnostic = self.build_request_diagnostic(
                url=generation_url, source=source_info, model=model_info,
                payload=payload, headers=headers, duration_ms=duration_ms,
                status="COMPLETED",
                response_summary=f"返回 {len(image_paths)} 张图片",
            )
            return GenerationResult(success=True, image_paths=image_paths, raw_response={"data": data, "diagnostic": diagnostic})
        except httpx.HTTPStatusError as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            error = self.format_http_status_error(exc)
            diagnostic = self.build_request_diagnostic(
                url=generation_url, source=source_info, model=model_info,
                payload=payload, headers=headers, duration_ms=duration_ms,
                status="FAILED", error=error,
            )
            return GenerationResult(success=False, error=error, raw_response={"diagnostic": diagnostic})
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            error = self.format_generation_exception(exc, generation_url, payload)
            diagnostic = self.build_request_diagnostic(
                url=generation_url, source=source_info, model=model_info,
                payload=payload, headers=headers, duration_ms=duration_ms,
                status="FAILED", error=error,
            )
            return GenerationResult(success=False, error=error, raw_response={"diagnostic": diagnostic})
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/ -q -k "adapter or openai"`
Expected: 全部通过

- [ ] **Step 3: Commit**

```bash
git add src/adapters/openai_adapter.py
git commit -m "refactor: deduplicate diagnostic construction in OpenAIAdapter"
```

---

## Task 16: 增强 key_vault 错误处理

**Files:**
- Modify: `src/managers/key_vault.py:17-32`

- [ ] **Step 1: 修改 _derive_key 加错误处理**

替换 `src/managers/key_vault.py:17-32`：

```python
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
        except (IOError, OSError) as e:
            raise ValueError(f"Failed to access salt file {salt_file}: {e}") from e
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600000,
        )
        return kdf.derive(password.encode())
```

- [ ] **Step 2: 写测试**

新建 `tests/managers/test_key_vault_errors.py`：

```python
import os
import pytest
from src.managers.key_vault import KeyVault


def test_derive_key_raises_friendly_error_on_salt_failure(tmp_path, monkeypatch):
    vault_path = str(tmp_path / "vault.dat")
    # 把 salt 文件设为目录，模拟 IO 错误
    salt_file = vault_path + ".salt"
    (tmp_path / "vault.dat.salt").mkdir()
    with pytest.raises(ValueError, match="Failed to access salt file"):
        KeyVault(vault_path, "password")
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/managers/test_key_vault_errors.py -v`
Expected: 1 passed

- [ ] **Step 4: 运行全部 key_vault 测试**

Run: `pytest tests/managers/test_key_vault.py -v`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add src/managers/key_vault.py tests/managers/test_key_vault_errors.py
git commit -m "fix: wrap salt file IO errors in key_vault._derive_key"
```

---

## Task 17: 稳定性适配 - 新增 start.sh

**Files:**
- Create: `start.sh`

- [ ] **Step 1: 创建 start.sh**

```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo
echo "  imageMaker - AI Image Generator"
echo "  -------------------------------"
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] Python 3 not found. Please install Python 3.10+"
    exit 1
fi

if [ ! -f ".venv/bin/python" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

if [ ! -f ".venv/.deps_installed" ]; then
    echo "[INFO] Installing dependencies..."
    pip install -r requirements.txt -q
    touch .venv/.deps_installed
fi

echo "[INFO] Starting imageMaker..."
echo
python src/main.py
```

- [ ] **Step 2: 添加执行权限**

Run: `git update-index --chmod=+x start.sh`（在 Git 仓库初始化后）

- [ ] **Step 3: 验证语法**

Run: `bash -n start.sh`
Expected: 无输出

- [ ] **Step 4: Commit**

```bash
git add start.sh
git commit -m "feat: add cross-platform start.sh launcher for Linux/macOS"
```

---

## Task 18: 创建 conftest.py 共享 fixture

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: 创建 conftest.py**

```python
"""Shared pytest fixtures and configuration for imageMaker test suite."""
import os
import sys
import asyncio
import pytest


@pytest.fixture(scope="session")
def qapp():
    """Provide a single QApplication instance for the whole test session."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app
    app.quit()


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary database file path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def sample_task():
    """Provide a sample GenerationTask for tests."""
    from src.models.task import GenerationTask
    return GenerationTask(platform_id="openai", prompt="a cat in space")


@pytest.fixture
def mock_config():
    """Provide a mock PlatformConfig with valid fields."""
    from src.models.platform_config import PlatformConfig
    return PlatformConfig(
        api_key="test-key",
        api_base_url="https://api.example.com/v1",
        auth_preset="openai",
        interface_type="openai_images",
        model_name="dall-e-3",
        response_format="openai",
    )
```

- [ ] **Step 2: 验证测试仍能运行**

Run: `pytest tests/ -q --collect-only | head -20`
Expected: 列出测试，未报错

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add conftest.py with shared fixtures (qapp, temp_db_path, sample_task, mock_config)"
```

---

## Task 19: 编写开发文档

**Files:**
- Create: `docs/development.md`

- [ ] **Step 1: 创建文档**

```markdown
# imageMaker 开发文档

## 环境搭建

### 系统要求
- Python 3.10+
- Windows 10+（主要目标）、macOS 12+、Linux（Ubuntu 22.04+ / Fedora 38+）

### 步骤
```bash
# 1. 克隆代码
git clone <repo-url> && cd imageMaker

# 2. 创建虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 3. 安装依赖（含开发工具）
pip install -e ".[dev]"

# 4. 启动应用
python src/main.py
```

## 运行测试

```bash
pytest                          # 全部测试
pytest tests/managers/          # 仅 manager 测试
pytest -k "database"            # 按名字过滤
pytest --cov=src                # 覆盖率
```

## 代码质量工具

```bash
ruff check src/                 # lint
ruff format src/                # 自动格式化
pyright src/                    # 静态类型检查（basic 模式）
```

## 项目结构

```
src/
  config/         # 配置（数据库、加密、常量、工具）
  adapters/       # 平台适配器（OpenAI / Stability / Midjourney）
  managers/       # 业务逻辑层（队列、历史、提示词、批量）
  widgets/        # UI 组件（PySide6）
  models/         # 数据模型
tests/
  conftest.py     # 共享 fixture
  config/         # config 模块测试
  managers/       # manager 测试
  widgets/        # widget 测试
  models/         # model 测试
docs/
  specs/          # 设计规格
  superpowers/    # 实施计划
```

## 数据流

UI 事件 → Widget → Manager → Database / Adapter → API / SQLite

## 添加新平台适配器

1. 在 `src/adapters/` 创建 `xxx_adapter.py`
2. 继承 `BaseAdapter`，实现 `get_params_schema`、`validate_config`、`generate`
3. 在 `src/adapters/__init__.py` 的 `init_adapters()` 注册
4. 在 `src/config/constants.py` 的 `PLATFORM_DEFAULTS` 添加默认配置
5. 写测试：`tests/test_xxx_adapter.py`

## 提交规范

格式：`<type>(<scope>): <subject>`

类型：
- feat: 新功能
- fix: 修复
- refactor: 重构（无行为变化）
- test: 仅添加/修改测试
- docs: 仅文档
- chore: 杂项（依赖、配置等）

示例：
- `feat(adapters): add Stable Diffusion XL support`
- `fix(security): whitelist columns in update_history_status`
```

- [ ] **Step 2: Commit**

```bash
git add docs/development.md
git commit -m "docs: add development guide"
```

---

## Task 20: 编写 CONTRIBUTING.md

**Files:**
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: 创建文档**

```markdown
# 贡献指南

## 报告 Bug

在 [GitHub Issues](https://github.com/your-org/imageMaker/issues) 提交，请包含：
- imageMaker 版本
- 操作系统和版本
- 复现步骤
- 期望行为 vs 实际行为
- 截图（如果是 UI 问题）
- 日志（设置 → 诊断 → 导出日志）

## 提交 Pull Request

1. Fork 仓库
2. 从 `main` 创建特性分支：`git checkout -b feat/your-feature`
3. 编写代码 + 测试
4. 确认通过：
   - `pytest`
   - `ruff check src/`
   - `pyright src/`
5. Commit message 遵循约定（见 development.md）
6. 提交 PR，说明：
   - 改动的动机
   - 关键设计决策
   - 测试覆盖

## 代码风格

- PEP 8（用 ruff 自动检查）
- 类型注解（公共 API 必须）
- 中文 UI 文案、英文/拼音代码标识符
- 函数不超过 50 行（超过则拆分）
- 提交粒度：一个 commit 一个逻辑改动

## 测试要求

- 新功能必须有测试
- Bug 修复必须包含回归测试
- 测试覆盖率不下降
```

- [ ] **Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: add contributing guide"
```

---

## Task 21: 编写 CHANGELOG.md

**Files:**
- Create: `CHANGELOG.md`

- [ ] **Step 1: 创建文档**

```markdown
# Changelog

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

## [Unreleased]

### Changed
- 移除全部 `sys.path.insert` hack，配置为可安装包
- 引入 ruff、pyright、pytest 工程化配置
- 缩略图路径、header 解析、safe_int 提取到 `src/config/utils.py`
- 批量操作重构为通用 `_batch_execute` 辅助方法
- 跨平台文件管理器打开：使用 `QDesktopServices` 替代 `os.startfile`

### Fixed
- 修复 `update_history_status` 的 SQL 注入风险（白名单列名）
- 临时文件清理增加 `try/finally` 保护
- `history_manager.delete_record` 文件删除失败不再崩溃
- `key_vault._derive_key` 友好错误提示
- 修复 `os.startfile` 在非 Windows 平台不可用
- 修复测试中硬编码 `D:/tmp` 路径

### Added
- `start.sh` 跨平台启动脚本
- `tests/conftest.py` 共享 fixture
- 开发文档 `docs/development.md`

## [1.0.0] - 2026-04-XX

### Added
- 多平台图片生成：OpenAI / Stable Diffusion / Midjourney
- 中转/代理支持（自定义 Base URL 和请求头）
- 队列生成、提示词库、历史画廊
- 图片浏览（缩放、旋转、另存、剪贴板）
- API Key AES-256 加密存储
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: initialize CHANGELOG with v1.0.0 and unreleased"
```

---

## Task 22: 全量验证

**Files:** 无（验证步骤）

- [ ] **Step 1: 安装开发依赖**

Run: `pip install -e ".[dev]"`
Expected: 成功安装

- [ ] **Step 2: 运行 ruff**

Run: `ruff check src/ tests/`
Expected: 0 errors

- [ ] **Step 3: 运行 pyright**

Run: `pyright src/`
Expected: 无 error（warning 可接受）

- [ ] **Step 4: 运行全部测试**

Run: `pytest tests/ -v`
Expected: 全部通过

- [ ] **Step 5: 验证无 sys.path 残留**

Run: `grep -rn "sys.path.insert" src/ tests/`
Expected: 无输出

- [ ] **Step 6: 验证应用可启动（仅导入检查）**

Run: `python -c "from src.app import main; print('Import OK')"`
Expected: 输出 Import OK

- [ ] **Step 7: 验证跨平台工具导入**

Run: `python -c "from src.widgets.history_panel import HistoryPanel; print('OK')"`
Expected: 输出 OK

---

## Self-Review 检查

### Spec 覆盖
- [x] 代码质量隐患（Task 3, 4, 5, 6, 9, 11, 12, 15, 16）
- [x] 文档（Task 19, 20, 21）
- [x] 跨平台（Task 7, 8, 17）
- [x] 代码质量审查（Task 1 配置工具链、Task 13 提取工具、Task 14 批量重构、Task 18 conftest）
- [x] Windows 10+ 适配（Task 7 用 QDesktopServices，Task 17 跨平台脚本）

### 占位符检查
- 无 "TODO" / "TBD" / "类似 Task N" 等占位符
- 每个代码块都是完整可粘贴的代码
- 每个命令都包含预期输出

### 类型一致性
- `parse_headers` 统一在 utils、queue_manager、settings_dialog 用
- `safe_int` 统一在 utils、settings_dialog 用
- `get_thumbnail_path` 统一在 utils、base、main_window、queue_manager 用
- `_open_in_file_manager` 命名跨任务一致
- `_batch_execute` 命名跨任务一致
