# imageMaker 设计规格书

> 创建日期: 2026-04-27

## 概述

imageMaker 是一款 Windows 桌面端轻量化图片生成工具，通过调用多平台图片生成 API（DALL·E、Stable Diffusion、Midjourney）生成图片。核心诉求：填入 API Key 和请求地址即可使用，支持中转/代理服务。

## 技术栈

| 层面 | 技术 | 说明 |
|------|------|------|
| UI 框架 | PySide6 (Qt 6) | 原生桌面控件，非网页 |
| HTTP 客户端 | httpx | 支持代理、自定义 headers |
| 图片处理 | Pillow | 缩略图生成 |
| 加密存储 | cryptography (AES-256-GCM) | API Key 安全存储 |
| 数据存储 | SQLite (aiosqlite) | 配置、模板、历史记录 |
| 打包 | PyInstaller | 生成单文件 .exe (~45-60MB) |

**加密密钥来源**: 首次启动时根据机器指纹（CPU 序列号 + 主板 UUID）派生主密钥，无需用户设置密码。重装系统后密钥变化，需重新输入 API Key。

## 功能需求

1. 多平台聚合: DALL·E 3、Stable Diffusion API、Midjourney API
2. 配置极简: 每个平台独立配置面板，填入 API Key + Base URL 即可
3. 网络适配: HTTP 代理、自定义请求头（支持中转/relay）
4. 队列生成: 连续添加任务，后台顺序执行
5. Prompt 管理: 提示词库（分类/标签/模板）+ 参数面板
6. 生成能力: Text-to-image + Image-to-image
7. 图片管理: 内置历史画廊（缩略图）+ 手动保存到指定目录
8. 图片浏览: 放大、旋转、查看元数据、重命名为 prompt
9. 安全存储: API Key AES-256 加密
10. 全中文界面

## 架构设计

### 模块分层

```
┌─────────────────────────────────────────┐
│                 UI 层                     │
│  main_window      → 三栏主窗口            │
│  prompt_panel     → 左侧提示词库          │
│  generation_panel → 中间生成区            │
│  history_panel    → 右侧历史画廊          │
│  settings_dialog  → 平台设置对话框        │
│  image_viewer     → 图片浏览器弹窗        │
├─────────────────────────────────────────┤
│               业务层                       │
│  queue_manager    → 生成队列管理器         │
│  prompt_manager   → 提示词模板 CRUD       │
│  history_manager  → 历史记录 CRUD         │
├─────────────────────────────────────────┤
│              API 适配层                    │
│  BaseAdapter      → 抽象基类              │
│  OpenAIAdapter    → DALL·E 适配器         │
│  StabilityAdapter → SD API 适配器         │
│  MidjourneyAdapter→ MJ 适配器             │
│  (注册制扩展)                              │
├─────────────────────────────────────────┤
│               存储层                       │
│  key_store        → API Key 加密存储      │
│  config_db        → SQLite 配置/模板/历史 │
│  file_store       → 本地图片文件读写       │
└─────────────────────────────────────────┘
```

### BaseAdapter 接口

```python
class BaseAdapter(ABC):
    @property
    @abstractmethod
    def platform_id(self) -> str: ...

    @abstractmethod
    def get_params_schema(self) -> dict: ...

    @abstractmethod
    async def validate_config(self, config: PlatformConfig) -> bool: ...

    @abstractmethod
    async def generate(self, task: GenerationTask, config: PlatformConfig) -> GenerationResult: ...
```

### 适配器注册机制

```python
ADAPTER_REGISTRY: dict[str, BaseAdapter] = {}

def register_adapter(adapter: BaseAdapter):
    ADAPTER_REGISTRY[adapter.platform_id] = adapter
```

UI 启动时遍历注册表，自动创建平台标签页和设置页。

## UI 布局

### 主窗口（三栏布局）

```
┌──────────────┬──────────────────────────────┬──────────────┐
│  📁 提示词库   │  🎨 生成区                   │ 🕐 历史记录   │
│              │  [DALL·E 3][SD][Midjourney]   │              │
│  分类标签      │                              │ 缩略图网格    │
│  ├ 人像 🔥    │  ┌──────────┐ ┌──────────┐  │  ■ ■ ■       │
│  ├ 风景       │  │ Prompt   │ │ Negative │  │  ■ ■ ■       │
│  └ ...       │  │ 描述...   │ │ 排除...   │  │              │
│              │  └──────────┘ └──────────┘  │ 共 N 张       │
│  模板卡片      │                              │              │
│  ┌──────┐    │  [尺寸▼][质量▼][数量▼][Seed]  │              │
│  │写真风 │    │  [+ 高级参数]                 │              │
│  └──────┘    │                              │              │
│              │  🖼 以图生图 💾 保存模板        │              │
│ + 新建       │          加入队列  [立即生成] │              │
├──────────────┼──────────────────────────────┼──────────────┤
│              │  生成队列 (N)                 │              │
│              │  ✓ 完成 │ 🔄 生成中 │ ⌛ 等待   │              │
└──────────────┴──────────────────────────────┴──────────────┘
```

### 设置对话框

- API Base URL: 默认填官方地址，用户可改为中转地址
- API Key: 密码框，加密存储
- 自定义请求头: Key-Value 表格，支持中转鉴权
- 代理: 复选框 + HTTP 代理地址输入
- 验证按钮: 测试当前配置是否可用

## 数据流

1. 用户选择平台标签页 → 切换对应 adapter + 参数面板
2. 填写 prompt + 参数 → 实时验证
3. 点击"加入队列" → 创建 WAITING 任务 → 加入 queue_manager
4. 队列自动消费 → 调用 adapter.generate()
5. adapter 使用 httpx 发送请求（带 proxy + custom_headers）
6. 收到响应 → 下载图片 → 保存到本地 → 生成缩略图 → 写入 history_db
7. 状态变为 COMPLETED → UI 更新
8. 用户点击历史图片 → 弹出 image_viewer

## 错误处理

| 场景 | 策略 |
|------|------|
| API Key 无效 | 弹窗提示，一键跳转到该平台设置 |
| 网络超时 | 3 次指数退避重试 |
| 代理连接失败 | 立即标记 FAILED，不重试 |
| API 速率限制 | 读取 Retry-After，自动排队等待 |
| 图片下载失败 | 标记 FAILED，保留 error 日志 |
| 参考图过大 | 前端自动压缩到平台限制尺寸 |
| 自定义 Headers 格式错误 | 保存时正则验证，拒绝保存 |

## 数据库 Schema

```sql
CREATE TABLE platform_configs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    api_base_url TEXT NOT NULL,
    api_key_encrypted BLOB,
    custom_headers TEXT,
    proxy TEXT,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE prompt_templates (
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

CREATE TABLE generation_history (
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

CREATE TABLE reference_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE,
    path TEXT,
    width INTEGER,
    height INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 验证计划

1. **手动测试**: 运行 `python src/main.py`，检查主窗口正常打开
2. **配置测试**: 在设置面板填入 API Key 和 Base URL，点击"验证"
3. **生成测试**: 输入 prompt 点击"立即生成"，确认队列运行、图片下载、历史画廊更新
4. **中转测试**: 将 Base URL 改为中转地址，添加自定义 Header，验证请求正常发出
5. **打包测试**: 运行 `python build.py`，生成 .exe 后在干净 Windows 环境运行
6. **并发测试**: 连续添加 5 个任务，确认队列顺序执行无异常