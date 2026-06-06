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
