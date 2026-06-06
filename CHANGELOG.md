# Changelog

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

## [Unreleased]

### Changed
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
