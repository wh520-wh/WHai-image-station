# 字段级错误诊断（Field-Level Error Diagnostics）

- **状态**：设计中
- **日期**：2026-06-08
- **范围**：核心生成流程（adapter → QueueManager → MainWindow → GenerationPanel）

## 背景与动机

核心生成流程在失败时只暴露一行文本（"生成失败：401 Unauthorized" 或 "请检查配置或网络连接"）。`_classify_error` 已能粗粒度分类（auth / rate / network / server / size），但用户拿不到"哪个参数错了"、"哪段 URL 段返 401"、"是 token 问题还是网络问题"。

用户调研结论：等待中最希望的是**响应及时 + 不阉断**——失败时立刻看到原因 + 关键字段，而不是延迟的、技术化的"请检查配置"。

## 目标

1. 失败时按字段粒度提示：分类 + 关键字段（参数 / 头 / URL 段）+ 原文。
2. 不阉断：始终保留原始错误消息可一键复制。
3. 错误信息全程结构化、可单测、可持久化。

## 非目标

- 不引入自动重试
- 不做预测性提示（"API 变慢"）
- 不改 SQLite schema
- 不改历史表结构

## 架构

### 新增 / 改动文件

| 文件 | 改动 |
|---|---|
| `src/adapters/errors.py`（新建） | `Category` 枚举、`Field` / `Diagnostic` 不可变 dataclass、`AdapterError` |
| `src/adapters/base.py` | `report_error()` 助手；`catch_http` 上下文管理器统一捕获 `httpx` 异常 + 按状态码选 `Category` |
| `src/adapters/{openai,stability,midjourney}_adapter.py` | 现有 `raise RuntimeError(...)` 改为 `raise self.report_error(...)` |
| `src/models/task.py` | `params['_diagnostic']` 类型注解改为 `Diagnostic \| None`；保留 `to_dict/from_dict` 兼容老数据 |
| `src/managers/queue_manager.py` | `_handle_task_exception` 区分 `AdapterError` 与普通异常；把 `Diagnostic` 写入 `task.params['_diagnostic']` |
| `src/widgets/generation_panel.py` | 新增内部 `_DiagnosticCard(QFrame)`；`update_diagnostic(d, expand)` 改为消费 `Diagnostic` 对象 |
| `src/widgets/main_window.py` | 删除 `_classify_error`（被 `Diagnostic.category` 替代）；`_on_queue_status_changed` 失败分支只取 `task.error` 字段 |
| `src/widgets/settings_dialog.py` | "验证配置"失败复用 `_DiagnosticCard`（只读版本） |
| `tests/adapters/test_errors.py`（新建） | `Diagnostic` 序列化、降级、枚举稳定性 |
| `tests/widgets/test_diagnostic_card.py`（新建） | 渲染 / 复制 / 边界 |
| `tests/adapters/test_*_adapter.py` | 现有 `pytest.raises(RuntimeError)` 改 `AdapterError` + 字段断言 |

## 数据结构

```python
class Category(str, Enum):
    AUTH = "auth"            # 401 / 403
    RATE_LIMIT = "rate"      # 429
    NETWORK = "network"      # timeout / connect refused
    SERVER = "server"        # 5xx
    BAD_REQUEST = "bad_req"  # 其它 4xx
    CONTENT = "content"      # 尺寸 / 格式错误
    UNKNOWN = "unknown"      # 兜底

@dataclass(frozen=True)
class Field:
    name: str
    value: str
    issue: str
    redact: bool = False  # True 时序列化输出 "***"

@dataclass(frozen=True)
class Diagnostic:
    category: Category
    fields: tuple[Field, ...] = ()
    hint: str | None = None
    original: str = ""
    platform: str = ""
    source_id: str = ""

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "Diagnostic":
        # 缺字段 / 错类型 → UNKNOWN + 原文兜底，绝不抛
        ...

class AdapterError(Exception):
    diagnostic: Diagnostic
    def __init__(self, message: str, diagnostic: Diagnostic):
        super().__init__(message)
        self.diagnostic = diagnostic
```

## 错误流

```
adapter.generate(...)
  ↓ raise AdapterError(message, diagnostic)
QueueManager._handle_task_exception(task, exc)
  ↓ 若是 AdapterError: task.params['_diagnostic'] = exc.diagnostic
  ↓ 否则: 走 _classify_error 兜底 → 包成 Diagnostic(UNKNOWN, original=...)
task.error = str(exc)            # SQLite 老列兼容
QueueManager 推 "failed" 事件
  ↓
MainWindow._on_queue_status_changed(task, "failed")
  ↓ 取 task.params['_diagnostic']
GenerationPanel.update_diagnostic(d, expand=True)
  ↓ 渲染 _DiagnosticCard
```

## 组件

### `BaseAdapter.report_error()`

```python
def report_error(
    self,
    category: Category,
    *,
    original: str = "",
    fields: list[Field] | None = None,
    hint: str | None = None,
) -> "AdapterError":
    return AdapterError(
        str(Diagnostic(category, tuple(fields or ()), hint, original, self.platform, ...)),
        Diagnostic(category, tuple(fields or ()), hint, original, self.platform, ...),
    )
```

### `BaseAdapter.catch_http()`

上下文管理器，统一捕获 `httpx.HTTPError` / `asyncio.TimeoutError`：

- `__exit__` 校验 `response.status_code`
- 按状态码自动选 `Category`：401/403→AUTH, 429→RATE_LIMIT, 5xx→SERVER, 4xx→BAD_REQUEST
- 把 url / method / redacted headers 注入 `fields`
- 网络层异常→NETWORK

### `_DiagnosticCard(QFrame)`（`generation_panel.py` 内部）

- 顶部：彩色徽章（`Category` 决定颜色）
- 字段表：每行 `name: value — issue`；超过 4 行折叠为"更多(N)"
- hint 行：蓝色提示文本
- 底部：折叠原文按钮、"📋 复制诊断"按钮、`AUTH`/`RATE_LIMIT` 时多一个"⚙ 打开设置"按钮
- 复制内容：`json.dumps(d.to_dict(), ensure_ascii=False, indent=2)`

## 数据持久化

- SQLite `history.params` 列继续以 JSON 存。
- `Diagnostic.to_dict()` 写入，`from_dict()` 读出。
- 老数据（`params['_diagnostic']` 是 `dict` 或缺失）通过 `from_dict` 降级到 `UNKNOWN`。
- 无需新数据库迁移。

## 错误处理

| 场景 | 行为 |
|---|---|
| `AdapterError` 没传 `fields` | 渲染只显示 category + 原文 + hint，不报错 |
| `category` 是 `UNKNOWN` | 徽章灰色，hint 提示"请复制诊断发给开发者" |
| `original` 极长 (>2KB) | 折叠默认收起 |
| `Field.value` 是 `Path` / bytes | 渲染前统一 `str()` |
| 老历史 `params['_diagnostic']` 是 `dict` | `from_dict` 降级到 `UNKNOWN` |
| 异常不是 `AdapterError` | 走 `_classify_error` 兜底 |
| `from_dict` 抛 `ValueError` | 视为 `UNKNOWN` + 原文兜底 |
| 渲染过程中抛异常 | try/except 兜底显示"诊断不可用"，原 `task.error` 仍可见 |

## 安全

- `Diagnostic` 字段全部 dataclass + enum，序列化走 `json.dumps`，**不** 用 `eval` / `pickle`。
- 复制诊断按钮：JSON 字符串。`Field.redact=True` 时序列化输出 `"***"`；**默认不脱敏**，由 adapter 在明确知道是密钥时才标记。
- 日志路径：兜底异常仍 `print` 一行，保持现有风格，不引入新依赖。

## 测试

### 单元测试（`tests/adapters/test_errors.py`，新建）

- `Diagnostic.to_dict/from_dict` 往返
- `from_dict` 缺字段 → `UNKNOWN` 兜底
- `from_dict` 旧 dict（`{message: "..."}`）→ 仍能加载，`message` 进 `original`
- `Field` 序列化稳定（字段顺序）
- `AdapterError.__str__` 单行摘要
- `Category` 枚举 8 个值稳定

### 现有测试改造

- `pytest.raises(RuntimeError)` → `pytest.raises(AdapterError)` + 断言 `e.diagnostic.category` / `e.diagnostic.fields`
- 错误文本硬编码断言 → 字段断言

### Widget 测试（`tests/widgets/test_diagnostic_card.py`，新建）

- 渲染：category 颜色 / fields 表 / hint / 折叠
- 复制：剪贴板内容是 JSON；`redact=True` → `"***"`
- 边界：None → 隐藏；`fields=()` → 不渲染表；老 dict 降级不崩

### 手工验证

- 真实 OpenAI / Stability / Midjourney 触发 401 / 429 / 5xx，肉眼检查字段表
- 复制诊断 JSON 粘到 issue 模板可读

## 验收标准

1. 任何 `adapter.generate()` 失败都能拿到 `Diagnostic`（哪怕是 `UNKNOWN`）
2. UI 失败时立刻显示 `_DiagnosticCard`，不再只显示一行分类文本
3. 复制诊断按钮可用，剪贴板内容是合法 JSON
4. 现有 50+ 测试不破坏；新增 ≥ 10 条覆盖 `Diagnostic` / `_DiagnosticCard`
5. 老历史数据加载不崩
