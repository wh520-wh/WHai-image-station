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
