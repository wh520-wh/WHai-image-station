# Changelog

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

## [Unreleased]

- 收拢参考图字段兼容与迁移、本地处理历史记录的职责；启动迁移只执行一次，明确图片元数据类型及模块扩展契约。
- 减少参考图重复读取和导出校验，复用处理中的图片生成缩略图；同步副本发布，修正照片方向与灰度透明图处理。
- 本地处理记录复用进入图片工具，避免影响生图草稿；流程保存失败时保留原有内存配置。

- 队列改为入队、额度变更和完成事件唤醒；流程通过完成通知等待，QML 与 Widgets 使用 Qt 事件接收状态，耗时计时仅在进行中的预览启用。
- 新增托管参考图副本、内容去重和旧引用迁移；备份 v3 携带并重定位参考图，导入失败回滚新增文件，保留已有素材。
- 工具页新增本地格式转换、等比例缩小和压缩，保持整体主题并支持深色和小窗口；原图保留，结果存入作品库，可对比、另存、复制与作为参考图。
- 打包程序启动检查增加实际 WebP 缩放和作品库保存，验证图片插件与后台处理可用。

- 创作预览跟随选中的队列任务，显示阶段与耗时；多图缩略带、复制、另存和参考图操作对应当前选中图片。
- 作品库筛选不再阻止新结果出现在创作预览；详情浮层打开时禁止快捷键提交后台任务。
- 统一生成参数规范化，兼容来源正确发送 seed；模板与流程保留受支持参数和参考图，编辑保留模型绑定与失败策略。
- 流程在执行前校验全部步骤，并使用已规范化参数；保留旧流程的 steps/guidance 等额外配置。
- 修正 Windows CI 的解释器定位，增加 EXE 打包、六页离线启动与正常退出检查。
- 修复 Qt 6.12 中多行占位文字引发的滚动区域尺寸循环；旧历史缺少完成时间时不显示推算耗时。
- 固定 Qt 运行依赖为已验证的 PySide6 6.11.1，避免安装时自动切换未完成验证的 Qt 版本。

## [1.1.0] - 2026-10-13

- 新增以图片画框和生成光芒为主题的 Logo，统一侧栏、开屏、设置页、窗口与 EXE 图标。
- 默认前端迁移为 QML / Qt Quick，新增独立工具页、深色外观、开屏与骨架屏、可减少的动态效果；保留 Widgets 对照入口。
- 新增 OpenAI GPT Image、Gemini、FLUX.2、MiniMax 官方来源预置及能力对应的参数。
- 修复队列并发分派、等待任务取消、模型与来源关联、模板恢复、历史日期与状态显示。
- 作品库采用分页和按视口创建控件；搜索在数据库中执行，避免遗漏早期记录。
- 备份携带实际图片与模型配置，支持跨机器密码加密密钥；批量导出包含全部结果图片。
- UI 异步操作不再阻塞 Qt 绘制；数据库事务隔离并发操作，工作线程分别使用独立连接。
- 打包入口统一，包含 QML 资源，改为无需每次解压的目录分发。

本版本通过离线测试和模拟 HTTP 验证，不包含真实付费生图验证。

## [Earlier changes]

### Added
- 失败时显示结构化诊断卡（`DiagnosticCard`）：分类徽章 + 字段表 + 可折叠原文 + 一键复制 JSON
- API Key 等敏感字段可标记 `redact=True`，复制时输出 `"***"`
- 设置页新增 `_show_validation_diagnostic` 辅助方法，验证失败时可渲染诊断卡

### Changed
- 项目对外展示名统一为 `WHai Image Station`（包名 `whai-image-station`、exe `WHai-image-station`），与 GitHub 仓库一致；数据目录与内部代码标识保持不变
- 移除全部 `sys.path.insert` hack，配置为可安装包
- 引入 ruff、pyright、pytest 工程化配置
- 缩略图路径、header 解析、safe_int 提取到 `src/config/utils.py`
- 批量操作重构为通用 `_batch_execute` 辅助方法
- 跨平台文件管理器打开：使用 `QDesktopServices` 替代 `os.startfile`
- `start.bat` / `start.sh` 首次运行执行 `pip install -e .`，确保 `src` 包可导入

### Fixed
- 修复 `update_history_status` 的 SQL 注入风险（白名单列名）
- 临时文件清理增加 `try/finally` 保护
- `history_manager.delete_record` 文件删除失败不再崩溃
- `key_vault._derive_key` 友好错误提示
- 修复 `os.startfile` 在非 Windows 平台不可用
- 修复测试中硬编码 `D:/tmp` 路径
- 修复 `python src/main.py` 报 `ModuleNotFoundError: No module named 'src'`（依赖 `pip install -e .`）

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
