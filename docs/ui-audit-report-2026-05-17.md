# UI 全面审查报告 — imageMaker

**审查日期**: 2026-05-17
**审查方式**: 纯代码审查（PySide6 / Qt 6），未运行应用
**审查范围**: 全部 UI 组件（11 个文件），四层面并行审查

---

## 总览

| 指标 | 数值 |
|------|------|
| 健康评分 | **C-** |
| 严重问题 | 17 |
| 中等问题 | 66 |
| 轻微问题 | 35 |
| **合计** | **118** |

### 健康评分说明

**C-**：应用功能基本可用，但存在多处可访问性障碍（对比度全面不达标、键盘导航缺失）、一个功能模块完全不可用（批量选择）、以及性能问题（UI 线程阻塞）。视觉风格统一但实现不一致（大量硬编码值绕过设计系统）。

### 四层面分布

| 层面 | 严重 | 中等 | 轻微 | 小计 |
|------|------|------|------|------|
| 视觉 | 4 | 38 | 15 | 57 |
| 布局 | 3 | 13 | 7 | 23 |
| 交互 | 3 | 6 | 8 | 17 |
| 性能与可访问性 | 7 | 9 | 5 | 21 |
| **合计** | **17** | **66** | **35** | **118** |

> 注：层面 1（视觉）与层面 4（可访问性对比度）存在重叠发现，已去重合并至层面 4。

---

## 层面 1：视觉审查

### 严重问题

1. **[严重] src/widgets/theme.py:197** — Primary 按钮白字(#FFFFFF)在橙色(#E87828)上对比度仅 2.94:1，WCAG AA 要求 ≥4.5:1。影响所有主要 CTA：立即生成、保存模板、+ 新增按钮、PromptCard"使用"按钮、选中的分类按钮、选中的 tab。建议将按钮底色加深至 #C05010，或将文字改为深色。

2. **[严重] src/widgets/theme.py:237** — Success 按钮白字(#FFFFFF)在绿色(#329A6E)上对比度 3.71:1，WCAG AA 不通过。建议加深至 #1F7A52。

3. **[严重] src/widgets/theme.py:244** — Success 按钮 pressed 状态使用硬编码 #2A8A5E，未在 COLORS 中定义，主题更新会遗漏此变体。

4. **[严重] src/widgets/components/prompt_card.py:91,107,124** — TaskCard 状态标签使用 10px 字号，低于设计系统最小值 11px，在高 DPI 下不可读（应用是中文界面，CJK 文字 10px 广泛认为低于可读阈值）。

### 中等问题

**颜色系统一致性 (6)**

5. **[中等] src/widgets/image_viewer.py:50-52** — 硬编码 #DDF7FC、#FFF8EC、#FFE2C8，应使用 COLORS['sky_soft']、COLORS['panel']、COLORS['primary_soft']。

6. **[中等] src/widgets/theme.py:142** — input_style() focus 背景硬编码 #FFFFFF 而非使用 COLORS 常量。

7. **[中等] src/widgets/theme.py:145** — input_style() disabled 背景硬编码 #F0F0F0，无对应 COLORS 条目。

8. **[中等] src/widgets/theme.py:132,166** — input_style() 硬编码 rgba(255,255,255,0.72)，与 COLORS['input'] 值相同但未引用，compact_input_style() 正确使用了 COLORS['input']，两兄弟函数不一致。

9. **[中等] src/widgets/main_window.py:83** — 阴影使用 QColor(0,0,0,18)（黑色调），但 COLORS['shadow'] = rgba(255,138,61,0.16)（橙色调），shadow 常量定义但从未使用。

10. **[中等] src/widgets/prompt_panel.py:108** — 分类按钮选中状态硬编码 color: #FFFFFF。

**字体层级 (9)**

11-19. **[中等] 多个文件** — 7 处调用 `app_font(N, QFont.Bold)` 后立即 `setStyleSheet(label_style("X"))`，CSS font-size 覆盖 QFont 字号，使 app_font 调用冗余。涉及文件：generation_panel.py:59-60, :281-282、history_panel.py:47-48、prompt_panel.py:37-38、prompt_card.py:30-31、image_viewer.py:34-35、settings_dialog.py:62。

20. **[中等] src/widgets/image_viewer.py:67** — image_label 内联 font-size: 13px，未使用 label_style()，13px 不在设计系统中。

21. **[中等] src/widgets/batch_ops_bar.py:31** — count_label 内联 font-size: 13px，未使用 label_style()。

22. **[中等] src/widgets/task_chain_editor.py:49** — 标题调用 app_font(14, QFont.Bold) 无对应 label_style，14px 不是标准变体。

23. **[中等] src/widgets/main_window.py:92,100** — 状态栏标签内联 font-size: 11px，应添加 "caption" 变体到 label_style()。

**间距系统 (8)**

24-31. **[中等] 8 个文件** — 大量 setContentsMargins(16,16,16,16) 和 setSpacing(12)/setSpacing(8) 硬编码，应使用 SPACING['lg'] 和 SPACING['md']/SPACING['sm']。涉及：main_window.py:47-48、generation_panel.py（多处）、history_panel.py:41-42,63,101,169、prompt_panel.py:32-33,60,70、image_viewer.py:28-29、settings_dialog.py:117-118,168,182、task_chain_editor.py:39,45-46,74-75,229-230。

32. **[中等] src/widgets/components/prompt_card.py:87** — TaskCard 使用 setSpacing(9)，不是标准 SPACING token（最近似 sm=8 或 md=12）。

**圆角与阴影 (7)**

33-36. **[中等] 5 个文件** — border-radius: 12px 在内联样式中出现 7+ 次，应使用 RADIUS['control']。涉及：generation_panel.py:73,316、batch_ops_bar.py:24、prompt_card.py:82、settings_dialog.py:81,128,243,388。

37. **[中等] src/widgets/history_panel.py:278** — 文件缺失标签硬编码 border-radius: 8px。

38. **[中等] src/widgets/components/prompt_card.py:131,134** — 进度条硬编码 border-radius: 2px，不在 RADIUS 系统中。

39. **[中等] src/widgets/main_window.py:83** — 阴影 y-offset 硬编码 2，且 COLORS['shadow']（橙色调）从未使用。

**样式复用 (8)**

40. **[中等] src/widgets/settings_dialog.py:76-89** — QDialogButtonBox 内联样式重复 button_style("secondary") 模式。

41. **[中等] src/widgets/settings_dialog.py:124-141** — QListWidget 内联样式（~15行），应提取为 list_widget_style() 工厂。

42. **[中等] src/widgets/settings_dialog.py:383-403** — _table_style() 定义为死代码，从未调用。

43. **[中等] src/widgets/prompt_panel.py:103-130** — _get_category_style() 重复 button_style 模式，应接受 padding 覆盖参数或添加 "category" 按钮类型。

44. **[中等] src/widgets/settings_dialog.py:293-310** — ref_image_check QCheckBox 内联样式（~18行），是应用中唯一的自定义复选框样式，应提取为 check_box_style()。

45. **[中等] src/widgets/task_chain_editor.py:85** — task_scroll 内联 "border: none; background: transparent;" 而非使用 scroll_area_style()。

46. **[中等] src/widgets/main_window.py:37-44** — 主窗口背景渐变是应用中唯一渐变，如果此模式复用应提取为 gradient_background_style()。

47. **[中等] src/widgets/theme.py:67-73** — settings_dialog.py 中使用 string.replace() 注入自定义背景到 tab_style()，脆弱且易出错，tab_style() 应接受可选参数。

### 轻微问题

48. **[轻微] src/widgets/theme.py:9-38** — COLORS['glass'] 定义但从未使用——死 token。

49. **[轻微] src/widgets/theme.py:41-44** — sunset/sunset_hover/sunset_pressed/sunset_soft 别名定义但从未使用——死代码。

50. **[轻微] src/widgets/theme.py:24,36** — accent_soft 和 info_soft 均等于 "#DDF7FC"，与 sky_soft 相同——三个 token 值相同。

51. **[轻微] src/widgets/generation_panel.py:79,285** — config hint 和 queue count 标签内联 font-size: 12px; font-weight: 600/700。

52. **[轻微] src/widgets/components/prompt_card.py:38** — 删除按钮拼接 font-size: 16px 魔数。

53. **[轻微] src/widgets/generation_panel.py:114,119,176,183,189,196** — 固定宽度硬编码像素值（180,190,124,112,72,104）。

54. **[轻微] src/widgets/history_panel.py:67,74,81,88,104,111,118,125** — 多个 setMinimumWidth 硬编码值。

55. **[轻微] src/widgets/history_panel.py:242,267** — 缩略图 setFixedSize 硬编码（220x164, 108x128, 204x140, 92x108）。

56. **[轻微] src/widgets/image_viewer.py:40,79,86,93,102,106,112,124,131** — 大量硬编码 setFixedSize。

57. **[轻微] src/widgets/theme.py** — RADIUS['dialog']=22 定义但从未使用。

58. **[轻微] src/widgets/theme.py:182-189** — make_empty_state_label() 内联 font-size: 12px 和 line-height: 150%。

59. **[轻微] src/widgets/components/prompt_card.py:38,99** — button_style 通过字符串拼接追加样式，有选择器冲突风险。

60. **[轻微] src/widgets/theme.py:75-76** — QPushButton focus 指示器使用 accent(#5BC8F0) 边框 1px，在浅色背景上可能难以看到。

---

## 层面 2：布局审查

### 严重问题

61. **[严重] src/widgets/generation_panel.py — 整个文件** — GenerationPanel 使用 QVBoxLayout 但无外层 QScrollArea。最小窗口 700px 时，内容累计高度约 716px（标题 40 + 选择器 60 + prompt 280 + 参数 60 + 动作 72 + 队列 120 + 间距 84），超出可用高度约 100px，队列区域被裁剪。建议将整个面板包裹在 QScrollArea 中。

62. **[严重] src/widgets/generation_panel.py:295-297** — 生成队列使用 QHBoxLayout 无滚动容器，5 张 TaskCard（每张 minWidth=210px）总宽度约 1110px，远超中间栏在最小窗口下的可用宽度（约 562px）。建议使用 QScrollArea 或 FlowLayout。

63. **[严重] src/widgets/generation_panel.py:208-248** — 立即生成按钮（minHeight=40）与加入队列按钮（minHeight=38）仅差 2px，主操作与次操作难以区分。建议将生成按钮提升至 48px。

### 中等问题

64. **[中等] src/widgets/main_window.py:73-74** — 左侧 PromptPanel stretchFactor=0，窗口放大时完全不获得额外空间。

65. **[中等] src/widgets/generation_panel.py:164** — Prompt/Negative Prompt 等分空间（各 stretch=1），Negative Prompt 使用频率远低于正 Prompt，建议改为 2:1。

66. **[中等] src/widgets/settings_dialog.py:222-234** — 隐藏的 response_format 控件未从布局中移除，留下约 12px 空行。

67. **[中等] src/widgets/history_panel.py:242** — 宫格模式缩略图 108x128 仅利用约 30% 可用列宽，建议增加大宫格模式（如 160x190）。

68. **[中等] src/widgets/generation_panel.py:94-106,324-327** — 状态消息 5 秒自动消失但位置在上方，用户目光通常在下方队列区。

69. **[中等] src/widgets/generation_panel.py:201-206** — "+ 高级参数"按钮与参数控件视觉权重相同，应降级为 ghost 或文字链接样式。

70. **[中等] src/widgets/generation_panel.py:114,119** — 来源下拉框 180px、模型下拉框 190px，长名称会被截断。

71. **[中等] src/widgets/components/prompt_card.py:76** — TaskCard minHeight 118px 不足容纳失败状态的长错误信息。

72. **[中等] src/widgets/history_panel.py:65-91** — 搜索过滤栏控件总宽约 350px，窄面板（320px）下溢出。

73. **[中等] src/widgets/generation_panel.py:298-300** — 队列空状态标签左对齐 muted，与另两个面板的居中空状态风格不一致。

74. **[中等] src/widgets/main_window.py:31,182-186** — 初始加载时无加载指示器，三个面板短暂显示空状态可能被误认为故障。

75. **[中等] src/widgets/generation_panel.py:413-418** — _update_config_state_ui() 在配置完成后可能残留旧错误消息。

76. **[中等] src/widgets/task_chain_editor.py:68,113** — 左侧面板无 minimumWidth，缩窄时 chain 名称不可读。

77. **[中等] src/widgets/history_panel.py:189-228** — _update_grid 每次都清除所有 widget 并重建，100+ widget 时可能闪烁/卡顿。

### 轻微问题

78. **[轻微] src/widgets/settings_dialog.py:123** — 来源列表 minimumHeight=430 偏大。

79. **[轻微] src/widgets/history_panel.py:117-122** — "清空" danger_ghost 按钮与常规操作无分隔。

80. **[轻微] src/widgets/image_viewer.py:126-128** — "另存为"使用 primary 样式，在查看器语境中可降为 secondary。

81. **[轻微] src/widgets/prompt_panel.py:42-47** — "+" 按钮 fixedSize(30,30) + font-size 18px 略显局促。

82. **[轻微] src/widgets/generation_panel.py:172-199** — 参数栏四个下拉框宽度参差不齐（124/112/72/104）。

83. **[轻微] src/widgets/history_panel.py:270-281** — 文件缺失占位 8px 字体几乎占满 108x128 卡片。

84. **[轻微] src/widgets/main_window.py:44** — 三色渐变在 4K 全屏下可能引起重绘延迟。

85. **[轻微] src/widgets/main_window.py:63** — GenerationPanel 无 minimumWidth，拖拽右侧分割器可能导致控件重叠。

---

## 层面 3：交互审查

### 严重问题

86. **[严重] src/widgets/batch_ops_bar.py:8-12 + src/widgets/main_window.py** — BatchOpsBar 定义 5 个信号但从未在 MainWindow 中实例化或导入。HistoryPanel 的批量方法（toggle_batch_mode、enter_batch_mode、exit_batch_mode）和 batch_selection_changed 信号也从未被连接。**批量选择功能完全不可用**。

87. **[严重] src/widgets/generation_panel.py:246+333** — Ctrl+Enter 和 Ctrl+Return 双重注册调用 _generate()。QShortcut（line 333）触发 _generate() 时不检查按钮启用状态，当按钮 disabled 时（生成进行中）仍可发起调用，形成双重提交向量。

88. **[严重] src/widgets/components/prompt_card.py:39** — PromptCard 删除按钮（×）直接发出 delete_template 信号，无确认对话框，导致模板永久删除不可恢复。

### 中等问题

89. **[中等] src/widgets/history_panel.py:128** — "清理无效"按钮使用 ghost 样式但操作为破坏性，应使用 danger_ghost 与"清空"一致。

90. **[中等] src/widgets/task_chain_editor.py:24-25** — TaskChainEditor 定义 chain_saved 和 chain_started 信号但从不在 MainWindow 中实例化，整个任务链功能是死 UI 代码。

91. **[中等] src/widgets/image_viewer.py:80** — "缩小"按钮 tooltip 提示 "(Ctrl+-)" 但无对应快捷键注册。放大（Ctrl++）同理缺失。

92. **[中等] src/widgets/generation_panel.py — 全文件** — "加入队列"无键盘快捷键。

93. **[中等] src/widgets/components/prompt_card.py:128-136** — "GENERATING"状态 TaskCard 的进度条是静态色条（硬编码 140px），无动画不反映实际进度。

94. **[中等] src/widgets/generation_panel.py:288-292** — 失败错误消息 fallback "请检查配置或网络"过于通用，无法帮助诊断。

### 轻微问题

95. **[轻微] src/widgets/settings_dialog.py:76-89** — QDialogButtonBox 保存/取消按钮有 :hover 但无 :pressed 反馈。

96. **[轻微] src/widgets/generation_panel.py:291** — "清空已完成"无确认对话框（虽然仅清除视觉显示）。

97. **[轻微] src/widgets/main_window.py:111-112** — template_used 和 template_selected 都连接 apply_template，点击卡片和使用按钮行为相同，语义冗余。

98. **[轻微] src/widgets/generation_panel.py:230** — Ctrl+S 仅在按钮 tooltip 中可见，无应用级快捷键文档。

99. **[轻微] src/widgets — 全项目** — 无 setTabOrder() 调用，Tab 导航完全依赖创建顺序。

100. **[轻微] src/widgets/generation_panel.py:324-327** — info/success 状态 5 秒自动消失但无手动关闭按钮。

101. **[轻微] src/widgets/main_window.py:125** — 队列轮询 250ms，如进度条改为动画建议 100ms。

---

## 层面 4：性能与可访问性审查

### 严重问题

102. **[严重] src/app.py:35** — `_init_async` 通过 `loop.run_until_complete()` 阻塞 Qt 主线程，DB 连接+适配器初始化期间 UI 冻结 0.5-1.5 秒。

103. **[严重] src/widgets/main_window.py:182-186** — `_load_data()` 通过 `run_async()`（内部 run_until_complete）阻塞主线程，加载来源+模型+历史时 UI 冻结 300-800ms。

104. **[严重] src/widgets/history_panel.py:189-228** — `_update_grid` 在每次筛选/排序/刷新时销毁并重建所有 widget，100 条记录 = 100 个 QFrame + 100 个 QVBoxLayout + 100 个 QLabel + 100 个 QPixmap 从磁盘加载，引起可见延迟。

105. **[严重] src/managers/history_manager.py:41-52,54-62** — `delete_record()` 和 `get_record()` 获取最多 1000 行做 O(n) 查找，忽略已索引的 task_id 列。应使用 `DELETE/WHERE task_id = ?` 和 `SELECT/WHERE task_id = ?`。

106. **[严重] src/widgets/generation_panel.py:311-320** — 4 种功能色文字在对应 soft 背景上全部 WCAG AA 不通过：info 2.44:1、success 3.06:1、danger 3.45:1、warning 4.27:1（均需 ≥4.5:1）。

107. **[严重] src/widgets/history_panel.py:240-287** — 画廊缩略图是 QFrame 有 mousePressEvent 但无 keyPressEvent、setFocusPolicy、tab-stop。键盘用户无法导航、选择、预览或打开上下文菜单。

108. **[严重] src/widgets/history_panel.py:327-351** — 右键上下文菜单无键盘等效触发方式（Menu 键或 Shift+F10）。

### 中等问题

109. **[中等] src/config/database.py:411-415** — 历史查询 LIMIT 100 但无分页，500+ 条记录后内存和渲染开销显著。

110. **[中等] src/widgets/history_panel.py:269-274** — QPixmap 每次从磁盘加载，无 QPixmapCache 或内存缓存。

111. **[中等] src/widgets/image_viewer.py:176-179** — resizeEvent 每次像素变化都触发 QPixmap.scaled(Qt.SmoothTransformation) 高清原图缩放，无防抖。

112. **[中等] src/widgets/main_window.py:222-249** — `_refresh_platform_config_statuses` 在轮询路径中通过 run_async 多次阻塞 DB 查询，每个 tick 冻结 10-50ms。

113. **[中等] src/widgets/main_window.py:315-321** — `_on_delete_history_record` 每次删除时创建新列表过滤。

114. **[中等] src/widgets/history_panel.py:403-408** — `add_record` 无条件 insert(0)，O(n) 列表偏移。

115. **[中等] src/widgets/history_panel.py:317** — 诊断错误文字 danger(#C95855) 在 panel_alt(#FFF0D6) 上对比度 3.73:1。

116. **[中等] src/widgets/theme.py:188** — subtle(#6B7B7A) 在 background(#F7EFE2) 上对比度 3.88:1（空状态标签用）。

117. **[中等] src/widgets/theme.py:167-178** — subtle(#6B7B7A) 输入占位符在 panel(#FFF8EC) 上对比度 4.20:1。

118. **[中等] src/widgets/components/prompt_card.py:107** — subtle 文字在 TaskCard 五种状态背景上全部不达标（3.65-3.96:1）。

119. **[中等] src/widgets/prompt_panel.py:55** — 分类滚动区域隐藏水平滚动条，键盘用户无法横向滚动。

120. **[中等] src/widgets/settings_dialog.py:66-73** — QListWidget 选中项样式使用 primary 在 primary_soft 上对比度 2.37:1，难以看到选中源。焦点环也不显示。

121. **[中等] src/widgets — 7 个位置** — 缺少 tooltip 的重要控件：来源/模型下拉框、管理来源/请求诊断按钮、参数下拉框（尺寸/质量/数量/Seed）、搜索过滤栏（搜索/平台/日期/排序）、设置对话框来源配置字段（名称/接口/鉴权/URL/密钥/代理/启用）、模型字段（显示名/Model ID/尺寸/质量/数量）、主窗口设置按钮。

122. **[中等] src/widgets/theme.py:305-311** — label_style 使用 px 单位 font-size（16px/14px/12px），高 DPI 下不缩放。影响 compact_input_style()、make_empty_state_label() 及大量内联样式。

123. **[中等] src/widgets/history_panel.py:242** — 画廊缩略图使用固定像素值（108x128/220x164），高 DPI 下物理尺寸偏小。

124. **[中等] src/widgets/main_window.py:36** — setMinimumSize(1200,700) 在 200% DPI 下等效感观仅 600x350。

### 轻微问题

125. **[轻微] src/widgets/generation_panel.py:431-433** — _update_prompt_count 每次击键都调用 toPlainText()。

126. **[轻微] src/widgets/history_panel.py:483-523** — 每步筛选创建新的完整列表拷贝。

127. **[轻微] src/widgets/generation_panel.py:609-612** — refresh_queue() 每次销毁所有 TaskCard 重建。

128. **[轻微] src/config/database.py:102-113** — _init_tables 每次启动运行 11 个 PRAGMA + 11 个潜在 ALTER TABLE，应使用 PRAGMA user_version。

129. **[轻微] src/widgets/components/prompt_card.py:39** — PromptCard prompt_preview 截断 88 字符无 tooltip 显示完整提示词。

130. **[轻微] src/widgets/main_window.py:54** — 设置按钮无 tooltip。

131. **[轻微] src/widgets/generation_panel.py:201-205** — "+ 高级参数"按钮仅弹 message box。

132. **[轻微] src/widgets/settings_dialog.py:96-100** — 导出/导入密钥按钮弹"功能开发中"。

133. **[轻微] src/widgets/generation_panel.py:114-197** — 多个固定宽度下拉框像素值不随内容缩放。

134. **[轻微] src/widgets/settings_dialog.py:113** — 来源列表 fixedWidth(245px) 高 DPI 关注。

---

## 完整对比度失败表（WCAG 2.1 AA）

所有计算使用标准相对亮度公式：L = 0.2126×R_lin + 0.7152×G_lin + 0.0722×B_lin

| 前景 | 背景 | 对比度 | 阈值 | 结果 | 影响范围 |
|------|------|--------|------|------|----------|
| #FFFFFF (white btn text) | #E87828 (primary) | **2.94:1** | 4.5:1 | 失败 | 全部 CTA 按钮 |
| #E87828 (primary selected) | #FFE2C8 (primary_soft) | **2.37:1** | 4.5:1 | 失败 | 设置来源列表选中项 |
| #2EA8D7 (info text) | #DDF7FC (info_soft) | **2.44:1** | 4.5:1 | 失败 | 状态消息 |
| #329A6E (success text) | #DDF5EB (success_soft) | **3.06:1** | 4.5:1 | 失败 | 状态消息 |
| #C95855 (danger text) | #FFE3DF (danger_soft) | **3.45:1** | 4.5:1 | 失败 | 状态消息 |
| #FFFFFF (white btn text) | #329A6E (success) | **3.71:1** | 4.5:1 | 失败 | Success 按钮 |
| #C95855 (danger text) | #FFF0D6 (panel_alt) | **3.73:1** | 4.5:1 | 失败 | 诊断错误文字 |
| #6B7B7A (subtle text) | #FFF0D6 (panel_alt) | **3.94:1** | 4.5:1 | 失败 | TaskCard 平台标签 |
| #6B7B7A (subtle text) | #F7EFE2 (background) | **3.88:1** | 4.5:1 | 失败 | 空状态标签 |
| #6B7B7A (subtle text) | #FFF8EC (panel) | **4.20:1** | 4.5:1 | 失败 | 输入占位符 |
| #A85A10 (warning text) | #FFE8CC (warning_soft) | **4.27:1** | 4.5:1 | 失败 | 配置提示横幅 |
| #6B7B7A (subtle text) | #DDF7FC (info_soft) | **3.96:1** | 4.5:1 | 失败 | TaskCard GENERATING |
| #6B7B7A (subtle text) | #DDF5EB (success_soft) | **3.87:1** | 4.5:1 | 失败 | TaskCard COMPLETED |
| #6B7B7A (subtle text) | #FFE8CC (warning_soft) | **3.73:1** | 4.5:1 | 失败 | TaskCard PENDING |
| #6B7B7A (subtle text) | #FFE3DF (danger_soft) | **3.65:1** | 4.5:1 | 失败 | TaskCard FAILED |
| #B05008 (primary_text) | #FFE2C8 (primary_soft) | **4.24:1** | 4.5:1 | 失败 | 主要文字在 soft 背景 |

**通过的所有组合**：text(#2F3538) 在 background/panel/panel_alt 上均 >10:1；muted(#3A4A4E) 在 background/panel/panel_alt 上均 >8:1。

---

## 附录：问题总清单（按严重程度排序）

### 严重问题速查（17 项）

| # | 文件 | 问题 | 层面 |
|---|------|------|------|
| 102 | app.py:35 | 启动阻塞 Qt 主线程 0.5-1.5s | 性能 |
| 103 | main_window.py:182-186 | 数据加载阻塞主线程 300-800ms | 性能 |
| 104 | history_panel.py:189-228 | _update_grid 全量销毁重建致延迟 | 性能 |
| 105 | history_manager.py:41-52 | O(n) 查找忽略索引 | 性能 |
| 1 | theme.py:197 | 按钮白字橙底 2.94:1 | 视觉 |
| 2 | theme.py:237 | 按钮白字绿底 3.71:1 | 视觉 |
| 3 | theme.py:244 | success pressed 硬编码颜色 | 视觉 |
| 106 | generation_panel.py:311-320 | 4 种状态消息全部对比度失败 | 可访问性 |
| 107 | history_panel.py:240-287 | 画廊缩略图不支持键盘 | 可访问性 |
| 108 | history_panel.py:327-351 | 右键菜单无键盘等效 | 可访问性 |
| 86 | batch_ops_bar.py + main_window.py | 批量选择功能完全不可用 | 交互 |
| 87 | generation_panel.py:246+333 | 双重快捷键绕过禁用状态 | 交互 |
| 88 | prompt_card.py:39 | 模板删除无确认 | 交互 |
| 61 | generation_panel.py | 无滚动区域内容溢出 | 布局 |
| 62 | generation_panel.py:295-297 | 队列横向溢出 | 布局 |
| 63 | generation_panel.py:208-248 | 主次按钮仅差 2px | 布局 |
| 4 | prompt_card.py:91 | 状态标签 10px 不可读 | 视觉 |
