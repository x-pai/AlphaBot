# 贡献指南 | Contributing Guide

[English](#contributing-guide) | [中文](#贡献指南 )

---

## 贡献指南 

感谢关注 AlphaBot！欢迎提交代码、文档、反馈与建议。

### 分支与提交
- 从 `main` 创建分支：
  - 功能：`feat/<scope>-<short-desc>`
  - 修复：`fix/<scope>-<issue-or-desc>`
  - 文档：`docs/<scope>-<short-desc>`
- 提交信息语义化：`feat:` / `fix:` / `docs:` / `refactor:` / `chore:`

### 开发检查
- 后端（Python）
  - 遵循 PEP8，建议使用 `ruff`/`flake8`，避免未使用代码/依赖
  - 运行必要的单元测试（如配置）
- 前端（TypeScript/React）
  - 遵循 ESLint/Prettier；建议执行 `npm run lint`、`npm test`（如配置）

### Pull Request 要求
- 关联 Issue（如有）
- 说明动机、主要变更、测试方式与影响范围
- 涉及接口/用法变更时同步更新文档

### 报告问题（Issues）
- 提供环境（OS、Python/Node、依赖版本）
- 复现步骤、期望/实际行为
- 日志/截图或最小复现示例

### 安全披露
- 涉及安全漏洞请勿公开 Issue，优先私信或通过安全邮箱联系维护者

---

## Contributing Guide

Thank you for your interest in AlphaBot! Contributions of code, docs, feedback and ideas are welcome.

### Branching & Commits
- Branch from `main`:
  - Feature: `feat/<scope>-<short-desc>`
  - Fix: `fix/<scope>-<issue-or-desc>`
  - Docs: `docs/<scope>-<short-desc>`
- Use semantic commits: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`

### Development Checks
- Backend (Python): follow PEP8, use `ruff/flake8`, run unit tests where applicable
- Frontend (TypeScript/React): ESLint/Prettier; run `npm run lint` and `npm test` when applicable

### Pull Requests
- Link related issues (if any)
- Describe motivation, key changes, testing and impact
- Update docs if APIs or usage change

### Reporting Issues
- Provide environment (OS, Python/Node, dependency versions)
- Repro steps, expected vs actual behavior
- Logs/screenshots or a minimal repro if possible

### Security
- For vulnerabilities, please avoid public issues; contact maintainers privately first

---

感谢你的贡献 / Thank you for contributing!
