# imageMaker UI 诊断审计报告

> 审计日期：2026-05-05
> 审计方法：纯代码静态启发式审计（不运行应用）
> WCAG 标准：2.1 AA（正文 ≥ 4.5:1，大号文字/UI 组件 ≥ 3:1）

---

## 1. 设计系统总览

### 1.1 配色体系

`theme.py` 定义了 21 个色值，分为中性色（text/muted/subtle/panel/background）、功能色（primary/accent/success/warning/danger）及各自的 soft 变体。整体采用暖橙+天蓝的"落日"配色，视觉辨识度高。

**核心问题：大面积低对比度。** 在 32 个关键前景/背景组合中，仅 3 个通过 WCAG AA 正文标准（4.5:1），其余 29 个全部不达标。即使是 UI 组件标准（3:1），也只有 6 个通过。

| 严重程度 | 问题 |
|----------|------|
| Critical | `subtle` (#9BA9A8) 在任何背景上均 < 2.3:1，完全不可读 |
| Critical | `primary` (#FF8A3D) 在 `panel` 上仅 2.22:1，标签/链接不可读 |
| Critical | 按钮文字 `panel` (#FFF8EC) 在 `primary` (#FF8A3D) 上仅 2.22:1 |
| Warning | `muted` (#65767A) 在 `panel` 上仅 4.49:1，差 0.01 未达 AA |
| Warning | 所有 `xxx_on_xxx_soft` 组合均 < 3:1（状态标签不可读） |

### 1.2 字体层级

`app_font()` 默认 10pt，`label_style` 定义了 4 级：title(15px/700)、section(12px/700)、muted(11px/normal)、body(12px/normal)。

| 问题 | 说明 |
|------|------|
| Warning | 默认 10pt 偏小，Windows 125% DPI 缩放后等效 8pt，低于可读性下限 |
| Suggestion | title 与 section 均为 bold，层级区分仅靠字号差(15 vs 12)，缺少字重对比 |

### 1.3 间距与圆角

`RADIUS` 定义 4 级：pill(8)、control(12)、card(18)、dialog(22)。实际使用中存在不一致：

| 位置 | 使用值 | 期望值 | 问题 |
|------|--------|--------|------|
| `generation_panel.py:71` config_hint_frame | 12px | control=12 | 一致 |
| `generation_panel.py:188` 缩略图 frame | 16px | card=18 | 偏小 |
| `prompt_card.py:83` TaskCard frame | 12px | card=18 | 混用 control 与 card |
| `settings_dialog.py:85` source_list | 12px | control=12 | 一致 |
| `settings_dialog.py:284` header_table | 12px | control=12 | 一致 |

### 1.4 全局边距不统一

| 面板 | ContentsMargins | Spacing |
|------|-----------------|---------|
| MainWindow | 16, 16, 16, 16 | 10 |
| GenerationPanel | 0, 0, 0, 0 | 12 |
| HistoryPanel | 14, 14, 14, 14 | 12 |
| PromptPanel | 14, 14, 14, 14 | 12 |
| ImageViewer | 16, 16, 16, 16 | 12 |
| SettingsDialog | 22, 22, 22, 18 | 16 |

6 个面板使用了 5 种不同的边距方案，缺乏统一规范。

---

## 2. 分面板诊断

### 2.1 主窗口 (`main_window.py`)

| # | 严重度 | 问题 | 位置 |
|---|--------|------|------|
| 1 | Warning | 渐变背景 `qlineargradient` 从 `sky_soft` 经 `background` 到 `sunset_soft`，在三个面板背后形成明暗不均的底色，面板卡片边缘处可见色差 | `:32-38` |
| 2 | Suggestion | 工具栏仅一个"设置"按钮，右对齐后左侧大面积留白，视觉失衡 | `:45-53` |
| 3 | Suggestion | Splitter 初始尺寸 `[250, 660, 340]` 总和 1250 > 最小窗口 1200，窄窗口下初始布局可能溢出 | `:71` |
| 4 | Suggestion | 三栏的 `setStretchFactor` 为 (0, 1, 0)，中间栏弹性伸缩但两侧固定，在宽屏下中间栏过宽、两侧过窄 | `:68-70` |

### 2.2 生成面板 (`generation_panel.py`)

| # | 严重度 | 问题 | 位置 |
|---|--------|------|------|
| 1 | **Critical** | 顶部纵向堆叠过密：标题栏(26) → 配置提示框(~40) → 状态提示框(~36) → 来源模型选择器(~56) = 约 158px 非内容区，在 700px 最小高度下占 22%，输入区被严重压缩 | `:49-123` |
| 2 | **Critical** | `config_hint_frame` 的 warning 文字 (#D67A2E) 在 `warning_soft` (#FFE8CC) 背景上对比度仅 2.64:1，不可读 | `:66-82` |
| 3 | **Critical** | `config_hint_frame` 的边框 `border_strong` (#E3B987) 在 `warning_soft` (#FFE8CC) 背景上对比度仅 1.53:1，边框几乎不可见 | `:69` |
| 4 | Warning | 来源/模型下拉框固定宽度 180/190px，长来源名或模型名会被截断，无 tooltip 提示完整内容 | `:105, 110` |
| 5 | Warning | 状态提示框 `status_frame` 无最大高度限制，长错误信息会无限撑高，挤压下方内容 | `:85-97` |
| 6 | Warning | 参数行(尺寸/质量/数量/Seed)固定宽度 124/112/72/104px，中文标签+英文值混排时可能对齐错位 | `:163-189` |
| 7 | Suggestion | Prompt 与 Negative Prompt 并排等宽，但 Negative Prompt 使用频率远低于 Prompt，空间分配不合理 | `:131-154` |
| 8 | Suggestion | 队列区域在面板底部，需滚动才能看到，不利于监控生成状态 | `:260-288` |

### 2.3 历史面板 (`history_panel.py`)

| # | 严重度 | 问题 | 位置 |
|---|--------|------|------|
| 1 | **Critical** | 宫格缩略图 `setFixedSize(108, 136)`，在面板最小宽度 320px 下，减去 margins(14*2) + right margin(14) = 278px 可用宽度，仅能放 2 张（108*2 + 14间距 = 230），空间利用率低 | `:183` |
| 2 | **Critical** | 缩略图按钮行"预览"+"复用"两个 ghost 按钮在 108px 宽度内挤放，按钮文字可能被截断 | `:218-227` |
| 3 | Warning | 诊断历史区域即使无内容也显示"诊断历史"标题和"展开"按钮，占用面板底部空间 | `:86-100` |
| 4 | Warning | 网格 `ContentsMargins(0, 0, 14, 0)` 左右不对称，右边距 14px 但左边距 0px，视觉偏移 | `:81` |
| 5 | Warning | 诊断项错误文字 `danger` (#C95855) 在 `panel_alt` (#FFF0D6) 背景上对比度 3.45:1，仅过 UI 组件标准，作为 10px 正文不达标 | `:263` |
| 6 | Suggestion | 缩略图 placeholder 仅显示"图片"二字，视觉信息不足 | `:213` |

### 2.4 提示词面板 (`prompt_panel.py`)

| # | 严重度 | 问题 | 位置 |
|---|--------|------|------|
| 1 | **Critical** | 未选中分类按钮文字 `muted` (#65767A) 在 `panel_alt` (#FFF0D6) 背景上对比度 4.22:1，不达 AA 标准 | `:123-137` |
| 2 | **Critical** | 空状态文字 `subtle` (#9BA9A8) 在 `panel` (#FFF8EC) 背景上对比度 2.30:1，完全不可读 | `:152` |
| 3 | Warning | 分类栏 `setFixedHeight(38)`，分类名过长时文字被截断且无省略号提示 | `:50` |
| 4 | Warning | "+" 按钮仅 30x30px，低于 WCAG 推荐最小触摸目标 44x44px | `:42` |
| 5 | Suggestion | 面板最小宽度 220px，减去 margins(14*2) = 192px 可用宽度，PromptCard 内再减 margins(12*2) = 168px，有效内容区极窄 | `main_window.py:57` |

### 2.5 设置对话框 (`settings_dialog.py`)

| # | 严重度 | 问题 | 位置 |
|---|--------|------|------|
| 1 | **Critical** | 右侧表单区在 `QScrollArea` 内，但 `right_scroll` 的 `setWidget(right)` 将整个 right frame 直接放入，意味着滚动时表单标签和输入框会一起滚动，大量表单项（6 个字段 + URL 预览 + Headers 表格 + 模型表格）在 760px 高度内需频繁滚动 | `:126-130` |
| 2 | Warning | 左侧来源列表 `setFixedWidth(245)`，长来源名被截断，无水平滚动或 tooltip | `:70` |
| 3 | Warning | 底部按钮区"取消"+"保存"靠右排列，左侧大面积留白，与其他面板的操作按钮布局不一致 | `:249-261` |
| 4 | Warning | Headers 表格 `setMinimumHeight(150)` + 模型表格 `setMinimumHeight(210)` = 360px，在 760px 对话框中占比过大，挤压来源详情表单 | `:207, 236` |
| 5 | Warning | 表格 Header 文字 `muted` (#65767A) 在 `panel_alt` (#FFF0D6) 背景上对比度 4.22:1，不达标 | `:293` |
| 6 | Suggestion | 4 个来源操作按钮（新增/删除/备份/重置）水平排列无间距区分，"删除"和"重置"危险操作与"新增"视觉权重相同 | `:100-117` |
| 7 | Suggestion | URL 预览标签 `muted` 在 `panel_alt` 背景上低对比度，且字体仅 11px | `:198` |

### 2.6 图片查看器 (`image_viewer.py`)

| # | 严重度 | 问题 | 位置 |
|---|--------|------|------|
| 1 | Warning | 底部操作栏 7 个控件水平排列（−/适应/原始/缩放%/+/旋转/元数据/另存为/复制），在 860px 最小宽度下空间紧张，元数据文字可能被截断 | `:78-130` |
| 2 | Warning | 标题截断至 64 字符，中文 prompt 64 字 ≈ 2 行，但 `QLabel` 无最大行数限制 | `:33` |
| 3 | Warning | 图片占位文字 `border_strong` (#E3B987) 在渐变背景上几乎不可见 | `:67` |
| 4 | Suggestion | 操作按钮全部使用 `secondary` 样式，"另存为"作为主要操作应使用 `primary` 以突出（当前已使用 primary，但"复制"与缩放按钮视觉同级，主次不分明） | `:119-128` |

### 2.7 可复用组件 (`components/prompt_card.py`)

**PromptCard：**

| # | 严重度 | 问题 | 位置 |
|---|--------|------|------|
| 1 | **Critical** | `prompt_preview` 使用 `muted` 色在 `panel` 背景上，对比度 4.49:1，差 0.01 未达 AA，实际显示偏淡 | `:45` |
| 2 | Warning | `setMaximumHeight(44)` 限制预览文字高度，长 prompt 被截断但无省略号或"展开"提示 | `:46` |
| 3 | Warning | 删除按钮 "×" 仅 24x24px，低于触摸目标最小值 | `:36` |
| 4 | Suggestion | "使用"按钮高度 32px，在卡片内显得拥挤 | `:50` |

**TaskCard：**

| # | 严重度 | 问题 | 位置 |
|---|--------|------|------|
| 5 | **Critical** | `WAITING` 状态标签使用 `subtle` (#9BA9A8) 在 `panel_alt` (#FFF0D6) 背景上，对比度 2.16:1，完全不可读 | `:140` |
| 6 | Warning | `platform_label` 使用 `subtle` 10px，任何背景上均不可读 | `:107` |
| 7 | Warning | `prompt_label` 使用 `muted` 11px 在 `panel_alt` 背景上，对比度 4.22:1，不达标 | `:114` |
| 8 | Warning | 固定最小尺寸 210x118px，在生成面板中间栏窄窗口下可能被压缩 | `:76` |
| 9 | Suggestion | 取消按钮 "×" 仅 20x20px | `:98` |

---

## 3. 跨面板系统性问题

### 3.1 对比度全面不足

这是本次审计最严重的发现。**当前配色系统中，几乎所有"彩色文字 on 浅色背景"的组合均不满足 WCAG AA 标准。**

**根本原因：** `primary` (#FF8A3D)、`accent` (#48C6F0)、`success` (#43A889)、`warning` (#D67A2E)、`info` (#2EA8D7) 均为中等明度色彩，在浅色面板（luminance > 0.85）上无法提供足够对比度。这些颜色作为背景色搭配白色文字时，同样不达标。

**受影响的高频场景：**

| 场景 | 色值组合 | 对比度 | 出现位置 |
|------|----------|--------|----------|
| 主按钮文字 | panel on primary | 2.22:1 | 全局所有 primary 按钮 |
| 成功按钮文字 | panel on success | 2.76:1 | 所有 success 按钮 |
| 状态标签 | primary on primary_soft | 1.89:1 | Tab hover、分类选中、队列计数 |
| 状态标签 | accent on accent_soft | 1.77:1 | 缩略图 hover |
| 配置提示 | warning on warning_soft | 2.64:1 | 生成面板配置提示框 |
| 禁用按钮 | text_disabled on panel_disabled | 1.36:1 | 所有 disabled 按钮 |
| 次要文字 | subtle on panel | 2.30:1 | 空状态、placeholder、平台标签 |
| 边框 | border on panel | 1.29:1 | 所有卡片边框 |

### 3.2 `subtle` 色值不可用

`subtle` (#9BA9A8) 在任何项目使用的背景上对比度均 < 2.3:1，作为文字颜色完全不满足可读性要求。但该色值被广泛使用：

- 空状态提示文字（`prompt_panel.py:152`、`history_panel.py:146`）
- TaskCard 平台标签（`prompt_card.py:107`）
- 缩略图 placeholder（`history_panel.py:214`）

### 3.3 拥挤模式

多个面板存在相同的拥挤模式：

**模式 A：标题行信息密度过高**
- 标题 + 计数标签 + 操作按钮挤在同一行，如"历史画廊 共 0 张 [宫格][单列][清空]"
- 出现位置：`history_panel.py:33-43`、`generation_panel.py:54-63`

**模式 B：固定宽度控件导致空间浪费**
- `setFixedWidth` 在响应式布局中阻碍自适应，如来源/模型选择器(180/190px)、参数行(124/112/72/104px)
- 出现位置：`generation_panel.py:105,110,167,175,182,188`、`settings_dialog.py:70`

**模式 C：纵向堆叠过多非内容区**
- 生成面板顶部 4 层非内容区（标题+配置提示+状态+选择器）占 22% 垂直空间
- 设置对话框表单区需频繁滚动

### 3.4 边距/间距不一致

详见 1.4 节表格。5 种边距方案缺乏统一规范，导致面板间视觉节奏不统一。

### 3.5 触摸目标过小

| 控件 | 尺寸 | 位置 | WCAG 推荐 |
|------|------|------|-----------|
| "+" 添加模板按钮 | 30x30 | `prompt_panel.py:42` | ≥ 44x44 |
| 删除模板 "×" | 24x24 | `prompt_card.py:36` | ≥ 44x44 |
| 取消任务 "×" | 20x20 | `prompt_card.py:98` | ≥ 44x44 |
| 缩略图内按钮 | h=24 | `history_panel.py:219,224` | ≥ 44 高 |
| 缩放 "−"/"+" 按钮 | 36x36 | `image_viewer.py:79,103` | ≥ 44x44 |

---

## 4. 问题汇总表

### Critical（影响可用性）

| # | 问题 | 面板 | 位置 | 建议 |
|---|------|------|------|------|
| C1 | `subtle` 色在任何背景上 < 2.3:1，作为文字不可读 | 全局 | `theme.py:31` | 加深至至少 #6B7B7A（预计对比度 ~4.5:1） |
| C2 | 按钮文字 panel on primary 对比度 2.22:1 | 全局 | `theme.py:146-158` | 将 primary 加深至 #D06A1A 或按钮文字改用 #FFFFFF |
| C3 | `primary` on `primary_soft` 对比度 1.89:1 | Tab/分类/队列 | `theme.py:226-234` | `primary_soft` 改浅或 `primary` 改深 |
| C4 | 生成面板顶部 4 层非内容区占 22% 垂直空间 | 生成面板 | `generation_panel.py:49-123` | 合并配置提示与状态提示，或使用 overlay |
| C5 | 空状态文字 `subtle` 不可读 | 提示词/历史 | `prompt_panel.py:152`, `history_panel.py:146` | 改用 `muted` 色 |
| C6 | WAITING 状态标签 subtle 不可读 | TaskCard | `prompt_card.py:140` | 使用 `muted` 或 `text` 色 |
| C7 | 宫格缩略图 108px 宽度内双按钮拥挤 | 历史 | `history_panel.py:218-227` | 改用图标按钮或右键菜单 |
| C8 | config_hint 文字/边框在 warning_soft 上不可读 | 生成面板 | `generation_panel.py:66-82` | 加深文字至 #A85A10，边框至 #C8963A |

### Warning（体验不佳）

| # | 问题 | 面板 | 位置 | 建议 |
|---|------|------|------|------|
| W1 | `muted` on `panel` 对比度 4.49:1，差 0.01 未达 AA | 全局 | `theme.py:30` | 略加深至 #5E6E72（~4.6:1） |
| W2 | 所有 `xxx_on_xxx_soft` 状态标签 < 3:1 | 全局 | 多处 | 加深各功能色或改浅 soft 背景 |
| W3 | 来源/模型下拉框固定宽度，长文字截断 | 生成/设置 | `generation_panel.py:105,110` | 改用 `setMinimumWidth` + 自适应 |
| W4 | 状态提示框无最大高度 | 生成面板 | `generation_panel.py:85-97` | 添加 `setMaximumHeight` |
| W5 | 分类栏固定高度 38px，长文字截断 | 提示词 | `prompt_panel.py:50` | 允许换行或添加 tooltip |
| W6 | 诊断历史区无内容时仍显示标题 | 历史 | `history_panel.py:86-100` | 无诊断时隐藏整个区域 |
| W7 | 网格左右边距不对称 (0 vs 14) | 历史 | `history_panel.py:81` | 统一为 (0, 0, 0, 0) 或 (14, 0, 14, 0) |
| W8 | 设置对话框左侧来源列表固定宽度 245px | 设置 | `settings_dialog.py:70` | 改用 `setMinimumWidth` + Splitter |
| W9 | 设置表格 Header 文字低对比度 | 设置 | `settings_dialog.py:293` | 使用 `text` 色替代 `muted` |
| W10 | 图片查看器底部 7 控件水平拥挤 | 查看器 | `image_viewer.py:78-130` | 分两行或使用工具栏 |
| W11 | PromptCard 删除按钮 24x24 过小 | 提示词 | `prompt_card.py:36` | 增大至 32x32 |
| W12 | TaskCard 取消按钮 20x20 过小 | TaskCard | `prompt_card.py:98` | 增大至 28x28 |
| W13 | 诊断错误文字 10px danger 在 panel_alt 上 3.45:1 | 历史 | `history_panel.py:263` | 增大字号至 11px 或加深色值 |
| W14 | 禁用按钮文字对比度 1.36:1 | 全局 | `theme.py:158,208` | 加深 disabled 背景至 #D4C4AE |

### Suggestion（可优化）

| # | 问题 | 面板 | 位置 | 建议 |
|---|------|------|------|------|
| S1 | 默认字体 10pt 在 125% DPI 下偏小 | 全局 | `theme.py:52` | 默认 11pt |
| S2 | 渐变背景在面板边缘可见色差 | 主窗口 | `main_window.py:32-38` | 改为纯色或仅顶部渐变 |
| S3 | 工具栏仅一个按钮，左空右密 | 主窗口 | `main_window.py:45-53` | 添加应用名/Logo 至左侧 |
| S4 | Splitter 初始尺寸总和 > 最小窗口宽度 | 主窗口 | `main_window.py:71` | 调整为 [240, 640, 320] |
| S5 | Prompt 与 Negative Prompt 等宽 | 生成面板 | `generation_panel.py:131-154` | Prompt 2:1 比例 |
| S6 | 队列区在面板底部需滚动 | 生成面板 | `generation_panel.py:260-288` | 移至侧边或固定底部 |
| S7 | 缩略图 placeholder 仅"图片"二字 | 历史 | `history_panel.py:213` | 使用图标或灰色占位图 |
| S8 | 5 种边距方案不统一 | 全局 | 多处 | 定义 2-3 种标准边距 |
| S9 | 设置对话框 4 个来源按钮无分组 | 设置 | `settings_dialog.py:100-117` | 危险操作右移或分隔 |
| S10 | 图片查看器"另存为"与"复制"主次不分 | 查看器 | `image_viewer.py:119-128` | "复制"降为 ghost 样式 |

---

## 5. 附录：关键色值对比度计算表

| 前景 | 背景 | 对比度 | AA 正文 | AA UI |
|------|------|--------|---------|-------|
| text #2F3538 | panel #FFF8EC | 11.79:1 | PASS | PASS |
| text #2F3538 | panel_alt #FFF0D6 | 11.08:1 | PASS | PASS |
| text #2F3538 | background #F7EFE2 | 10.91:1 | PASS | PASS |
| muted #65767A | panel #FFF8EC | **4.49:1** | **FAIL** | PASS |
| muted #65767A | panel_alt #FFF0D6 | **4.22:1** | **FAIL** | PASS |
| subtle #9BA9A8 | panel #FFF8EC | **2.30:1** | **FAIL** | **FAIL** |
| subtle #9BA9A8 | panel_alt #FFF0D6 | **2.16:1** | **FAIL** | **FAIL** |
| subtle #9BA9A8 | background #F7EFE2 | **2.13:1** | **FAIL** | **FAIL** |
| primary #FF8A3D | primary_soft #FFE2C8 | **1.89:1** | **FAIL** | **FAIL** |
| primary #FF8A3D | panel #FFF8EC | **2.22:1** | **FAIL** | **FAIL** |
| primary #FF8A3D | panel_alt #FFF0D6 | **2.09:1** | **FAIL** | **FAIL** |
| accent #48C6F0 | accent_soft #DDF7FC | **1.77:1** | **FAIL** | **FAIL** |
| accent #48C6F0 | panel #FFF8EC | **1.87:1** | **FAIL** | **FAIL** |
| warning #D67A2E | warning_soft #FFE8CC | **2.64:1** | **FAIL** | **FAIL** |
| warning #D67A2E | panel #FFF8EC | **2.98:1** | **FAIL** | **FAIL** |
| danger #C95855 | danger_soft #FFE3DF | **3.45:1** | **FAIL** | PASS |
| danger #C95855 | panel #FFF8EC | **3.97:1** | **FAIL** | PASS |
| success #43A889 | success_soft #DDF5EB | **2.55:1** | **FAIL** | **FAIL** |
| success #43A889 | panel #FFF8EC | **2.76:1** | **FAIL** | **FAIL** |
| info #2EA8D7 | info_soft #DDF7FC | **2.44:1** | **FAIL** | **FAIL** |
| info #2EA8D7 | panel #FFF8EC | **2.58:1** | **FAIL** | **FAIL** |
| border #F0D9BD | panel #FFF8EC | **1.29:1** | **FAIL** | **FAIL** |
| border_strong #E3B987 | panel_alt #FFF0D6 | **1.62:1** | **FAIL** | **FAIL** |
| panel #FFF8EC | primary #FF8A3D | **2.22:1** | **FAIL** | **FAIL** |
| panel #FFF8EC | success #43A889 | **2.76:1** | **FAIL** | **FAIL** |
| #FFF8EC | #E6D5C0 (disabled) | **1.36:1** | **FAIL** | **FAIL** |

**统计：** 32 个组合中仅 3 个通过 AA 正文标准（9.4%），6 个通过 AA UI 组件标准（18.8%）。
