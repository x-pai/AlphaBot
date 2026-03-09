# AlphaBot 快速体验指南

> Phase 0～6 已实现并测试通过后，按以下步骤本地体验。

---

## 一、环境准备

### 1. 后端（backend）

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置 .env

在 `backend/.env` 中至少配置：

- **数据库**：`DATABASE_URL=sqlite:///./stock_assistant.db`（默认即可）
- **LLM**：`OPENAI_API_KEY`、`OPENAI_MODEL`、`OPENAI_API_BASE`（或使用 `LLM_*` 变量）
- **数据源**：`DEFAULT_DATA_SOURCE=akshare`（无需 key）或 alphavantage/tushare 并填写对应 key

可选：联网搜索需 `SEARCH_API_ENABLED=True`、`SEARCH_ENGINE=serpapi`、`SERPAPI_API_KEY`。

### 3. 初始化数据库与默认用户

```bash
cd backend
# 若项目提供 init 脚本（如 app/cli 或 init_db）
python -m app.cli.init_db   # 或按项目实际命令创建库表、默认管理员
```

若没有单独 init 命令，直接启动后端会在首次启动时建表；默认账户见项目根 README（如 admin/admin123）。

---

## 二、启动服务

### 方式 A：前后端分离（推荐）

**终端 1 - 后端**

```bash
cd backend
source venv/bin/activate
python run.py
# 或: uvicorn app.main:app --reload --port 8000
```

**终端 2 - 前端**

```bash
cd frontend
npm install
npm run dev
```

- 前端：http://localhost:3000  
- 后端 API 文档：http://localhost:8000/api/v1/docs  

### 方式 B：Docker 一键

```bash
./deploy.sh   # 或 deploy.ps1（Windows）
```

---

## 三、体验「个人投资助理」核心流程

1. **登录**  
   使用默认或已创建账号登录前端（如 admin/admin123）。

2. **打开智能助手**  
   在首页点击「智能助手」进入对话界面。

3. **对话录入与查询**  
   - 说：「记录一笔买入 AAPL 100 股 180 美元」→ 应调用 `add_trade` 并确认成功。  
   - 问：「我现在的持仓怎么样？」→ 应调用 `get_my_positions` 并展示持仓与盈亏。

4. **预警**  
   - 说：「AAPL 跌超 5% 提醒我」→ 创建预警。  
   - 问：「我有哪些预警？」→ 列出规则。  
   - （等待定时任务触发或手动触发后）在会话内看到「您有一条新预警：...」。

5. **记忆与体检**  
   - 说：「我偏好保守」或「保存：我偏好保守」→ 写入长期记忆。  
   - 再问：「给我一些投资建议」→ 回答中应体现保守倾向。  
   - 问：「帮我体检一下我的组合」→ 调用 `get_portfolio_health` 展示体检结果。

6. **导入交易（可选）**  
   - 说：「导入交易」并粘贴券商 CSV 文本 → 解析并写入 `trade_log`，可再问「我最近交易胜率如何」等。

---

## 四、通过 MCP 在 Cursor / Claude Desktop 中体验

1. **安装 MCP 依赖**  
   `pip install mcp`（若 backend 已装全量依赖通常已包含）。

2. **启动 MCP Server**（在 backend 目录下）  
   ```bash
   cd backend
   export MCP_USER_ID=1   # 对应用户 ID，确保该用户在 DB 中存在
   python -m app.mcp_server
   ```
   或：`uv run --with mcp python -m app.mcp_server`

3. **在 Cursor / Claude Desktop 中配置 AlphaBot MCP**  
   将上述 MCP Server 以 stdio 或 streamable-http 方式接入，即可在对话中调用 `get_my_positions`、`add_trade`、`get_portfolio_health` 等工具。

---

## 五、跑一遍自动化测试（可选）

```bash
cd backend
python -m pytest app/tests/test_phase0_config_llm.py app/tests/test_phase1_portfolio.py \
  app/tests/test_phase2_alert.py app/tests/test_phase3_memory.py \
  app/tests/test_phase4_import_trades.py app/tests/test_phase5_registries.py \
  app/tests/test_phase6_services.py -v
```

单 Phase：`python -m pytest app/tests/test_phase1_portfolio.py -v`  
详见 [TESTING.md](./TESTING.md)。

---

## 六、常见问题

- **401 / 未登录**：先在前端登录或用 API 获取 Token，请求头带 `Authorization: Bearer <token>`。  
- **MCP 报错「用户不存在」**：检查 `MCP_USER_ID` 与数据库中 `user.id` 一致，或先通过前端注册/创建对应用户。  
- **Agent 不调工具**：确认 LLM 配置正确、未禁用对应工具（`ENABLED_AGENT_TOOLS` 为空表示全部启用）。  
- **数据源报错**：AKShare 无需 key；Alpha Vantage / Tushare 需在 `.env` 中配置有效 key。

---

## 七、检阅与可选优化建议

架构已按 ROADMAP 实现并测试，以下为可选增强，非必须：

| 类型 | 建议 | 说明 |
|------|------|------|
| 文档 | 根目录 README 增加「个人投资助理」与 QUICKSTART 链接 | 新用户可快速从「股票分析」过渡到「持仓/预警/记忆」体验 |
| 文档 | 保留 `backend/README.md` 中的 LLM_* 与 ENABLED_AGENT_TOOLS 说明 | 与 Phase 0/5 一致，便于切换模型与工具 |
| 体验 | 首次登录后引导一句示例（如「试试说：我现在的持仓怎么样」） | 降低冷启动门槛 |
| 运维 | 生产环境将 `CORS_ORIGINS` 中的 `"*"` 改为具体前端域名 | 安全最佳实践 |
| 可选 | 提供 `.env.example`（不含真实 key） | 便于克隆后快速配置 |

当前实现已满足 ROADMAP 验收（M0～M6），可按 QUICKSTART 直接体验与迭代。
