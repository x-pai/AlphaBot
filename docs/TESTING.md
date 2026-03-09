# AlphaBot 已完成功能测试说明

本目录下的测试对应 [ROADMAP.md](./ROADMAP.md) 中 **Phase 0～Phase 3** 已实现功能的验收。

## 测试范围

| Phase | 文件 | 覆盖内容 |
|-------|------|----------|
| Phase 0 | `app/tests/test_phase0_config_llm.py` | 配置 LLM_*、LLMRegistry、LiteLLMService chat_completion/stream |
| Phase 1 | `app/tests/test_phase1_portfolio.py` | Position/TradeLog 模型与 Service，REST：/user/positions、/user/trades、/user/portfolio/summary、/user/portfolio/health |
| Phase 2 | `app/tests/test_phase2_alert.py` | AlertService 规则 CRUD、条件引擎、evaluate_all_rules，REST：/user/alerts、/user/alerts/triggers/unread |
| Phase 3 | `app/tests/test_phase3_memory.py` | MemoryService add/search（按 user_id 隔离） |

## 运行方式

在 **backend** 目录下，使用已安装项目依赖的虚拟环境执行：

```bash
cd backend
# 若使用 venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt pytest-asyncio
python -m pytest app/tests/test_phase0_config_llm.py app/tests/test_phase1_portfolio.py app/tests/test_phase2_alert.py app/tests/test_phase3_memory.py -v
```

仅运行某一 Phase：

```bash
python -m pytest app/tests/test_phase1_portfolio.py -v
```

## 环境说明

- 接口测试使用 **内存 SQLite**（`conftest.py` 中 `get_test_db`），不读写本地数据库文件。
- 需先有可用用户与 Token：`conftest.py` 提供 `test_user`、`auth_headers`，会创建邀请码并注册高积分测试用户。
- 若出现 `litellm` 或 `pydantic` 相关导入错误，请确保 `pip install -r requirements.txt` 在干净虚拟环境中执行，或升级/对齐依赖版本后再跑测试。

## 验收对照

- **M0**：切换 LLM 后 Agent 正常 → Phase 0 测试 LLMRegistry / LiteLLMService。
- **M1**：说「记录买入」完成录入、问持仓得到真实数据 → Phase 1 测试 add_trade、get_positions、REST。
- **M2**：创建预警、触发后会话内提醒 → Phase 2 测试 AlertService 与 REST。
- **M3**：偏好记忆、体检组合 → Phase 3 测试 MemoryService；组合体检在 Phase 1 的 portfolio/health 中覆盖。
