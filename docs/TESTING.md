# AlphaBot 已完成功能测试说明

本目录下的测试对应 [ROADMAP.md](./ROADMAP.md) 中 **Phase 0～Phase 6** 已实现功能的验收。

## 测试范围

| Phase | 文件 | 覆盖内容 |
|-------|------|----------|
| Phase 0 | `app/tests/test_phase0_config_llm.py` | 配置 LLM_*、LLMRegistry、LiteLLMService chat_completion/stream |
| Phase 1 | `app/tests/test_phase1_portfolio.py` | Position/TradeLog 模型与 Service，REST：/user/positions、/user/trades、/user/portfolio/summary、/user/portfolio/health |
| Phase 2 | `app/tests/test_phase2_alert.py` | AlertService 规则 CRUD、条件引擎、evaluate_all_rules，REST：/user/alerts、/user/alerts/triggers/unread |
| Phase 3 | `app/tests/test_phase3_memory.py` | MemoryService add/search（按 user_id 隔离） |
| Phase 4 | `app/tests/test_phase4_import_trades.py` | import_from_csv、POST /user/trades/import、TradeAnalysisService 交易模式分析 |
| Phase 5 | `app/tests/test_phase5_registries.py` | AnalysisModeRegistry、ToolRegistry、SearchRegistry 配置切换 |
| Phase 6 | `app/tests/test_phase6_services.py` | SimTradeService、BacktestService、RiskControlService、用户画像/模拟/回测/风控 REST |
| 整体集成 | `app/tests/test_integration.py` | 应用启动、/health、API 文档、认证与持仓/组合/画像/预警/风控等关键接口串联 |
| MCP Server | `app/tests/test_mcp_server.py` | MCP_USER_ID、_execute 与 AgentService 桥接、FastMCP 构建（需 fastmcp 包） |

## 运行方式

在 **backend** 目录下，使用已安装项目依赖的虚拟环境执行：

```bash
cd backend
# 若使用 venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt pytest-asyncio
python -m pytest app/tests/test_phase0_config_llm.py app/tests/test_phase1_portfolio.py app/tests/test_phase2_alert.py app/tests/test_phase3_memory.py app/tests/test_phase4_import_trades.py app/tests/test_phase5_registries.py app/tests/test_phase6_services.py -v
```

**整体测试（功能 + 集成，推荐）**：

```bash
python -m pytest app/tests/ -v
```

仅运行集成测试：

```bash
python -m pytest app/tests/test_integration.py -v
```

仅运行某一 Phase：

```bash
python -m pytest app/tests/test_phase1_portfolio.py -v
```

**MCP Server 测试**：

```bash
# 单元/桥接测试（不依赖 fastmcp 包）
python -m pytest app/tests/test_mcp_server.py -v
# 安装 fastmcp 后可跑完整测试（含 FastMCP 应用构建）
pip install fastmcp
python -m pytest app/tests/test_mcp_server.py -v
```

## MCP Server 手动/联调测试

1. **启动 MCP 服务**（backend 目录，需已存在用户 ID=1 或设置 `MCP_USER_ID`）：
   ```bash
   pip install fastmcp
   export MCP_USER_ID=1
   python -m app.mcp_server
   ```
   默认以 `streamable-http` 方式启动，便于 Cursor / MCP Inspector 连接。

2. **用 MCP Inspector 测试**：打开 [MCP Inspector](https://github.com/modelcontextprotocol/inspector)，添加 Server 并连接当前端点，在界面中调用 `get_my_positions`、`get_stock_info` 等工具。

3. **在 Cursor 中配置**：在 Cursor 的 MCP 配置里添加本 Server 的 transport 地址，即可在对话中通过工具调用持仓、交易、预警等能力。

## 环境说明

- 接口测试使用 **内存 SQLite**（`conftest.py` 中 `get_test_db`），不读写本地数据库文件。
- 需先有可用用户与 Token：`conftest.py` 提供 `test_user`、`auth_headers`，会创建邀请码并注册高积分测试用户。
- 若出现 `litellm` 或 `pydantic` 相关导入错误，请确保 `pip install -r requirements.txt` 在干净虚拟环境中执行，或升级/对齐依赖版本后再跑测试。

## 验收对照

- **M0**：切换 LLM 后 Agent 正常 → Phase 0 测试 LLMRegistry / LiteLLMService。
- **M1**：说「记录买入」完成录入、问持仓得到真实数据 → Phase 1 测试 add_trade、get_positions、REST。
- **M2**：创建预警、触发后会话内提醒 → Phase 2 测试 AlertService 与 REST。
- **M3**：偏好记忆、体检组合 → Phase 3 测试 MemoryService；组合体检在 Phase 1 的 portfolio/health 中覆盖。
- **M4**：导入交易、类似操作时「过去亏损过」提醒 → Phase 4 测试 import_trades、交易模式分析。
- **M5**：分析模式、工具、搜索可配置切换 → Phase 5 测试三大 Registry。
- **M6**：模拟交易、回测、风控、用户画像/定投 → Phase 6 测试 Sim/Backtest/Risk/Profile API。
