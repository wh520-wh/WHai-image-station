# imageMaker 开源准备 — 代码质量与跨平台适配 SPEC

> 创建日期: 2026-06-06
> 状态: 待实施

## 概述

本 SPEC 覆盖 imageMaker 开源前的四项核心工作：代码质量隐患修复、文档补全、跨平台适配（Windows 10+ 全版本）、以及系统性代码质量审查。目标是让项目达到可公开发布的工程水准。

---

## 一、代码质量隐患

### 1.1 消除 sys.path.insert hack（20 处）

**现状**: 项目中 20 处 `sys.path.insert(0, ...)` 绕过包管理，分布在 `src/` 和 `tests/` 的几乎每个模块。

**方案**:
- 在 `pyproject.toml` 中配置 `[tool.hatch.build]` 包发现，使 `src/` 成为可安装包
- 开发环境用 `pip install -e .` 安装，消除所有 path hack
- 测试通过 `conftest.py` 中的 `sys.path` 配置或 `pytest.ini_options` 的 `pythonpath` 解决

**涉及文件**: 全部 `src/` 下的 `.py` 文件（15 处）+ 3 个测试文件

**验收标准**:
- `grep -r "sys.path.insert" src/` 返回空
- `pip install -e . && python -c "from src.app import ImageMakerApp"` 成功
- `pytest tests/` 全部通过

### 1.2 修复 SQL 注入风险（1 处）

**现状**: `src/config/database.py:451` 的 `update_history_status` 方法，`**kwargs` 的键名直接拼入 SQL：

```python
f"UPDATE generation_history SET {', '.join(sets)} WHERE task_id = ?"
```

**方案**:
- 将 `**kwargs` 改为显式参数或白名单校验
- 只允许已知列名（`status`, `error`, `completed_at`, `image_path` 等）拼入 SQL

**验收标准**: 传入非法键名时抛出 `ValueError` 而非拼入 SQL

### 1.3 补充错误处理（10+ 处关键位置）

按优先级排列：

| 优先级 | 位置 | 问题 | 修复方案 |
|--------|------|------|----------|
| P0 | `base.py:97-110` `download_image` | 网络请求 + 文件写入无 try/except | 捕获 `httpx.HTTPError` 和 `IOError`，返回带原因的错误 |
| P0 | `history_manager.py:46-59` `delete_record` | `os.remove` 文件被占用时崩溃 | 捕获 `PermissionError`/`OSError`，记录日志继续 |
| P0 | `migration_manager.py:70-73` | 临时文件无 `finally` 保证清理 | 用 `try/finally` 确保 `os.remove` |
| P1 | `key_vault.py:20-25` `_derive_key` | salt 文件读写无保护 | 捕获 `OSError`，给出友好提示 |
| P1 | `stability_adapter.py:110-111` | 参考图读取在 try 块外 | 移入 try 块，给出明确错误信息 |
| P1 | `openai_adapter.py:124-128` | base64 解码失败无针对性提示 | 单独捕获 `binascii.Error` |
| P2 | `database.py:147-149` `execute` | 数据库锁定异常直接传播 | 捕获 `aiosqlite.OperationalError`，重试或提示 |

### 1.4 消除代码重复（6 组）

| 重复项 | 出现位置 | 提取方案 |
|--------|----------|----------|
| `_parse_headers` | `queue_manager.py:230`, `settings_dialog.py:599` | 提取到 `src/config/utils.py`，统一异常处理 |
| `_safe_int` | `database.py:274`, `settings_dialog.py:589` | 提取到 `src/config/utils.py` |
| 缩略图路径计算 | `base.py:114`, `queue_manager.py:293`, `main_window.py:357` | 提取 `get_thumbnail_path()` 到 `constants.py` |
| `os.makedirs` 调用 | `app.py` + 3 个 adapter + `history_manager.py`（5 处） | 仅保留 `app.py` 启动时调用，删除 adapter 中冗余调用 |
| 诊断构建代码 | `openai_adapter.py` 三处相同 `build_request_diagnostic` | 提前计算 source/model dict，复用变量 |
| 批量操作循环 | `batch_ops_manager.py` 三个方法结构相同 | 提取通用 `_batch_execute` 辅助方法 |

### 1.5 修复模块级副作用

**现状**: `src/app.py:18-19` 在模块顶层执行 `os.makedirs`，import 时即触发。

**方案**: 移入 `_init_async` 方法内，在数据库初始化之前执行。

### 1.6 清理重复 import

**现状**: `stability_adapter.py` 和 `midjourney_adapter.py` 各有重复的 `import os`。

**方案**: 删除冗余 import。

---

## 二、文档补全

### 2.1 开发文档（新建 `docs/development.md`）

内容：
- 环境搭建：Python 版本、虚拟环境、`pip install -e .`
- 运行测试：`pytest` 命令、测试结构说明
- 代码规范：格式化工具（ruff）、类型检查（pyright）
- 提交规范：commit message 格式
- 架构概览：模块分层图 + 数据流

### 2.2 用户文档（扩展 README.md）

内容：
- 功能截图/GIF 演示（至少 3 张：主界面、设置、历史画廊）
- 详细安装步骤（含 Python 安装指引）
- 常见问题 FAQ（API Key 配置、中转设置、图片保存位置）
- 支持的平台/模型列表

### 2.3 贡献指南（新建 `CONTRIBUTING.md`）

内容：
- 如何报告 bug
- 如何提交 PR
- 代码风格要求
- 测试要求

### 2.4 版本记录（新建 `CHANGELOG.md`）

内容：
- v1.0.0 初始版本功能列表
- 后续按 Keep a Changelog 格式维护

---

## 三、跨平台适配

### 3.1 目标平台

| 平台 | 最低版本 | 说明 |
|------|----------|------|
| Windows | 10 (Build 1903+) | 主要目标平台，覆盖 Windows 10/11 全版本 |
| macOS | 12 Monterey+ | 次要目标，PySide6 原生支持 |
| Linux | Ubuntu 22.04+ / Fedora 38+ | 次要目标，X11/Wayland |

### 3.2 Windows 10+ 适配清单

| 问题 | 位置 | 修复方案 |
|------|------|----------|
| `os.startfile` 仅 Windows 可用 | `history_panel.py:369` | 用 `QDesktopServices.openUrl()` 替代，跨平台 |
| 硬编码路径 `D:/tmp/ref.png` | `test_ux_behaviors.py:76` | 改用 `tmp_path` fixture |
| `start.bat` 仅 Windows | 项目根目录 | 新增 `start.sh`（Linux/macOS） |
| 路径分隔符 | `constants.py` 全部用 `os.path.join` | 已兼容，无需修改 |
| 数据目录 | `~/.imageMaker/` | 已兼容，无需修改 |
| Windows 10 特定测试 | 无 | 需在 CI 中加入 Windows 10 矩阵 |

### 3.3 跨平台启动脚本

**现状**: 仅有 `start.bat`。

**方案**:
- 新增 `start.sh`（bash 脚本，逻辑与 `start.bat` 对等）
- README 中说明各平台启动方式

### 3.4 文件管理器打开功能

**现状**: `history_panel.py:369` 使用 `os.startfile(os.path.dirname(path))`。

**方案**:
```python
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))
```

---

## 四、代码质量审查

### 4.1 审查范围

对 `src/` 下全部 41 个 `.py` 文件进行系统性审查。

### 4.2 审查维度

| 维度 | 检查项 | 工具/方法 |
|------|--------|-----------|
| 类型安全 | 函数签名缺少类型注解 | pyright 静态分析 |
| 代码风格 | PEP 8 合规、import 排序 | ruff check + ruff format |
| 安全性 | SQL 注点、密钥泄露、路径遍历 | 人工审查 + bandit |
| 异常处理 | 未捕获异常、吞掉异常 | 人工审查 |
| 资源管理 | 文件句柄、连接未关闭 | 人工审查 |
| 性能 | N+1 查询、不必要的全表扫描 | 人工审查 |

### 4.3 类型注解补充

**现状**: 约 20+ 个函数缺少返回值注解，`database.py` 的 `params` 参数无类型。

**方案**:
- 为核心模块补充类型注解：`database.py`、`app.py`、`history_manager.py`、`queue_manager.py`
- 配置 pyright，逐步消除类型错误
- 不要求 100% 覆盖，但公共 API（非 `_` 前缀方法）必须有完整注解

### 4.4 引入代码质量工具

在 `pyproject.toml` 中添加配置：

```toml
[tool.ruff]
target-version = "py310"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B"]

[tool.pyright]
pythonVersion = "3.10"
typeCheckingMode = "basic"
```

### 4.5 引入测试配置

在 `pyproject.toml` 中添加：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

新建 `tests/conftest.py` 提供共享 fixture。

---

## 五、实施计划

### 阶段一：代码质量修复（核心）

1. 消除 `sys.path.insert`，配置可安装包
2. 修复 SQL 注入
3. 补充关键错误处理
4. 消除代码重复
5. 修复模块级副作用

### 阶段二：跨平台适配

6. 替换 `os.startfile` 为跨平台方案
7. 新增 `start.sh`
8. 修复测试中的硬编码路径

### 阶段三：工程化配置

9. 配置 ruff + pyright + pytest
10. 新建 `conftest.py`
11. 补充核心模块类型注解

### 阶段四：文档

12. 编写开发文档
13. 扩展 README（截图、FAQ）
14. 编写 CONTRIBUTING.md
15. 编写 CHANGELOG.md

### 阶段五：审查验收

16. 全量 ruff check 通过
17. pyright 基本模式通过
18. pytest 全部通过
19. 手动测试 Windows 10/11 启动

---

## 六、不在本 SPEC 范围内

- CI/CD 配置（GitHub Actions）— 后续单独 SPEC
- LICENSE / .gitignore — 开源收尾工作
- 打包优化（PyInstaller 体积）— 后续迭代
- 功能新增 — 本 SPEC 仅处理工程质量问题
