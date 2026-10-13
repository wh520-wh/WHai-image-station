# WHai Image Station 开发文档

## 环境搭建

### 系统要求
- Python 3.10+
- Windows 10+（主要目标）、macOS 12+、Linux（Ubuntu 22.04+ / Fedora 38+）

### 步骤
```bash
# 1. 克隆代码
git clone https://github.com/wh520-wh/WHai-image-station.git && cd WHai-image-station

# 2. 创建虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 3. 安装依赖（含开发工具）
pip install -e ".[dev]"

# 4. 启动应用
python -m src.main
```

## 运行测试

```bash
python -m pytest                         # 全部测试
python -m pytest tests/managers/          # 仅 manager 测试
python -m pytest -k "database"            # 按名字过滤
python -m pytest --cov=src                # 覆盖率
```

## 代码质量工具

```bash
python -m ruff check src build.py tools    # lint
python -m ruff format src/                # 自动格式化
```

Windows PowerShell 的类型检查使用实际解释器路径，确保 Pyright 读取同一个环境中安装的依赖：

```powershell
$pythonExecutable = (python -c "import sys; print(sys.executable)").Trim()
& $pythonExecutable -m pyright --pythonpath $pythonExecutable src
```

## CI 与打包验证

`.github/workflows/checks.yml` 在 Windows、Python 3.12 环境安装 `.[dev,build]`，解析一次 `sys.executable`，随后通过该绝对路径运行安装、Ruff、Pyright、离线测试和 `build.py`。`--pythonpath` 也传入实际解释器路径，避免将 `python` 当成相对文件路径解析。

CI 使用 `QT_QPA_PLATFORM=offscreen` 和 `QT_QUICK_BACKEND=software`。测试通过后构建便携 EXE，再以 `--smoke-test=<临时目录>` 隐藏启动并等待退出；超过 30 秒、退出码非零、报告未就绪、图标未加载、六个页面不完整或出现 QML 警告都会失败。报告作为 `packaged-startup-report` 保存 7 天，便于排查打包问题。这些检查使用隔离数据，不调用真实生图 API，也不创建或发布 Release。

目前依赖按 `pyproject.toml` 的版本范围安装，尚未锁定具体版本；CI 验证的是当次解析出的环境，不能替代依赖锁定。

## 项目结构

```
src/
  config/         # 配置（数据库、加密、常量、工具）
  adapters/       # 图像适配器（OpenAI / Gemini / FLUX / MiniMax / 自定义）
  managers/       # 业务逻辑层（队列、历史、提示词、批量）
  ui/             # Qt Quick 页面和共用组件
  desktop.py      # QML 属性、信号、槽与 Python 服务桥接
  widgets/        # 旧 Widgets 对照界面
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

QML 事件 → StudioBridge → Manager → Database / Adapter → API / SQLite

QML 页面通过 Loader 切换，持久化和草稿状态保留在 StudioBridge。作品库使用增量 QAbstractListModel 和 GridView 复用委托；不要把全尺寸图片或全量控件常驻内存。异步 UI 操作使用 schedule_async，耗时文件处理使用 asyncio.to_thread，生图请求交由 QueueManager 的工作线程。

## 添加新平台适配器

1. 在 `src/adapters/` 创建 `xxx_adapter.py`
2. 继承 `BaseAdapter`，实现 `get_params_schema`、`validate_config`、`generate`
3. 在 `src/adapters/__init__.py` 的 `init_adapters()` 注册
4. 在 `src/config/providers.py` 添加来源预置和模型能力，并先核对服务商官方文档
5. 写测试：`tests/test_xxx_adapter.py`

新增 QML 模块时同步更新 tools/pyinstaller_hooks/hook-PySide6.QtQml.py 的模块列表，并对打包程序进行离线启动检查。该列表当前包含 QtQml、QtQuick、Controls Basic、Templates、Layouts、Window 与 Shapes。

Qt 运行版本固定为 PySide6 6.11.1。升级时先在隔离环境完成全部测试及打包程序的正常退出检查，再同时更新 pyproject.toml 与 requirements.txt，避免开发机和 CI 自动选到不同的 Qt 版本。

Windows 打包使用 build.py：它优先选择解释器与系统 DLL，spec 排除外部工具提供的 ICU。Qt 需要 Windows 自带的 ICU ABI；Conda、Poppler 等工具的同名 ICU DLL 不能代替它。可用 `--smoke-test=<隔离目录>` 检查打包应用，自动初始化无密钥测试数据、切换六个页面、关闭并写入 report.json。测试不会请求生图服务。

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
