# AlphaBot：个人投资助理

> **懂你的持仓、记住你的习惯、在关键时刻主动提醒你。**

---

## 一、产品定位

| 对比 | 通用股票助手 | 个人投资助理 |
|------|--------------|--------------|
| 身份 | 谁问都一样 | **我的**助理，只服务我 |
| 知识 | 通用市场知识 | 通用 + **我的持仓、交易、偏好** |
| 行为 | 被动回答 | 被动 + **主动监控、主动提醒** |
| 记忆 | 无 / 仅会话 | **长期记忆**，越用越懂我 |

**核心**：助理必须知道「我是谁、我有什么、我要什么」，才能给出真正有用的建议。

**交互原则**：前端永远只有一个对话框。所有能力通过自然语言对话 + **MCP 工具**完成，不设独立表单页。工具同时暴露给 MCP Server，供 Cursor、Claude Desktop 等接入。

---

## 二、数据底座

| 数据 | 说明 |
|------|------|
| SavedStock | 我关心的股票（已有） |
| Position | 我实际持有的股票、数量、成本 |
| TradeLog | 我的买卖历史 |
| AlertRule | 我设置的盯盘条件 |
| UserProfile + 向量记忆 | 我的偏好、习惯、投资逻辑 |

**数据录入**：对话 + `add_trade`（P0）→ CSV 导入 `import_trades`（P1）→ 券商 API（P3）

---

## 三、核心能力

### 3.1 Agent 工具（同时暴露为 MCP Tools）

| 工具 | 说明 |
|------|------|
| get_my_positions | 持仓 + 当前价 + 浮盈浮亏 |
| get_my_trades | 交易记录 |
| add_trade | 记录买卖 |
| get_portfolio_summary | 组合总览 |
| get_portfolio_health | 组合体检 |
| set_price_alert / list_my_alerts / delete_alert | 预警管理 |
| save_investment_note | 保存投资笔记到向量记忆 |
| import_trades | 导入 CSV |
| quick_stock_research / search_web | 研究、搜索 |

**System Prompt**：涉及「我的持仓」「我的盈亏」时，**必须先调用工具**获取真实数据，不得臆测。

### 3.2 长期记忆（向量库）

| 记忆类型 | 示例 |
|----------|------|
| 用户画像 | 风险偏好：保守；单股仓位上限 10% |
| 投资逻辑 | 对 TSLA 的逻辑：关注自动驾驶，估值区间 XX |
| 交易模式 | 过去科技股高位追涨 3 次均亏损 |
| 对话摘要 | 偏好中长线，不炒短线 |

**实现**：Chroma / pgvector，`MemoryService.add(user_id, text, tags)`、`search(user_id, query, top_k)`。在 Agent Context 阶段注入检索结果。

### 3.3 主动预警

- 价格预警：涨跌幅、均线、成交量
- 持仓预警：单只浮亏、组合回撤超阈值
- 舆情简报：持仓股重大新闻
- 提醒通道：V1 站内会话内插入

---

## 四、数据模型（核心表）

**position**：user_id, stock_id, symbol, quantity, cost_price, currency, source(manual/import/broker)

**trade_log**：user_id, stock_id, symbol, side(buy/sell), quantity, price, amount, fee, trade_time, source

**alert_rule**：user_id, symbol, rule_type(price_change_pct/price_vs_ma/volume_spike), params_json, enabled

**alert_trigger**：alert_rule_id, user_id, symbol, triggered_at, message, is_read

**user_profile**（可选）：risk_level, max_single_position_pct, preferred_horizon, excluded_sectors

---

## 五、架构与能力标准化

```
┌─────────────────────────────────────────────────────────────────┐
│  Intake / Context / Think / Act / Reply                          │
│  Context = 用户 + Position + TradeLog + AlertRule + 向量记忆检索   │
└─────────────────────────────────────────────────────────────────┘
        │
        ├── 个人数据层：Position, TradeLog, AlertRule, SavedStock
        ├── 记忆层：向量库 MemoryService
        └── 市场数据层：DataSource（行情/新闻/基本面）
```

**能力标准化**：参考 [LiteLLM](https://github.com/BerriAI/litellm)，各能力通过**标准接口 + 注册表**实现热插拔，配置即切换 LLM、数据源、分析模式、工具、搜索、记忆、预警。

---

## 六、风险与合规

| 风险 | 缓解 |
|------|------|
| 数据隐私 | 按 user_id 隔离，敏感数据加密 |
| 合规 | 所有输出标注「不构成投资建议」；不接实盘下单 |
| 提醒轰炸 | 同一规则同一自然日只触发一次 |
| 数据源限流 | 每用户最多 20 条规则等 |

---

## 七、增强方向（简要）

完成核心能力后，可参考 **OpenClaw**（仓位管理、风控、压力测试）、**VNPy**（回测、模拟交易、风控）、**TrendRadar**（舆情监控）扩展：

- **P1**：策略回测、模拟交易、仓位建议、风控提醒、舆情监控
- **P2**：WebSocket 实时行情、扩展数据源、交易行为报告
- **P3**：期权/衍生品、算法交易模拟

**用户痛点**：行为干预（清仓前二次确认）、数据整合（CSV 导入）、克制提醒（FOMO）、目标量化、定投提醒。

---

**实施路线**：见 [ROADMAP.md](./ROADMAP.md)  
**快速体验**：见 [QUICKSTART.md](./QUICKSTART.md)
