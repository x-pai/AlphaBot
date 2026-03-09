# AlphaBot 实施路线图

> 可执行任务路径，供 Agent 或人工按序实现。详见 [README.md](./README.md) 产品与架构。

---

## 一、设计原则

- **单一对话框**：所有功能通过自然语言完成，无独立表单页
- **MCP 工具**：录入、查询、预警、体检均通过 Agent 调用工具；同一套工具供 Web 与 Cursor/Claude 等接入
- **提醒**：预警触发 → 会话内插入消息，无独立「我的预警」页面

---

## 二、Phase 总览

```
Phase 0: 能力标准化基础 (P0)     ──►  Week 1-2
Phase 1: 个人数据底座 (P1)        ──►  Week 3-4
Phase 2: 主动预警 (P1)            ──►  Week 5-6
Phase 3: 长期记忆 + 组合体检 (P1)  ──►  Week 7-8
Phase 4: 交易分析 + 用户痛点 (P1-P2) ──►  Week 9-10
Phase 5: 能力标准化扩展 (P2)     ──►  Week 11-12
Phase 6: 增强能力 (P2-P3)        ──►  Week 13+
```

---

## 三、任务清单（按执行顺序）

### Phase 0：能力标准化基础 [P0]

| ID | 任务 | 产出 | 验收 |
|----|------|------|------|
| T0.4 | 依赖与配置 | requirements.txt + litellm；config.py + LLM_* | `LLM_MODEL` 生效 |
| T0.1 | LiteLLM 集成 | litellm_service.py | chat_completion/stream 与 OpenAIService 兼容 |
| T0.2 | LLM 注册表 | llm_registry.py | LLMRegistry.get() 按配置返回 |
| T0.3 | 替换调用点 | AgentService、AIService、ai_tasks、agent 路由 | 切换模型后功能正常 |

### Phase 1：个人数据底座 [P1]

| ID | 任务 | 产出 | 验收 |
|----|------|------|------|
| T1.1 | 数据表 | position、trade_log 表 + 迁移 | alembic upgrade head 成功 |
| T1.2 | Service | PositionService、TradeLogService | get_positions_with_pnl 返回持仓+浮盈浮亏 |
| T1.3 | REST API | POST /user/positions、/user/trades | 录入通过对话 + add_trade 完成 |
| T1.4 | Agent 工具 | get_my_positions、get_my_trades、add_trade、get_portfolio_summary | 问持仓→调工具；说记录→add_trade |
| T1.5 | System prompt | 明确「涉及持仓/盈亏必须先调工具」 | 问持仓时 Agent 先调 get_my_positions |

### Phase 2：主动预警 [P1]

| ID | 任务 | 产出 | 验收 |
|----|------|------|------|
| T2.1 | 数据表 | alert_rule、alert_trigger | 表结构符合 README |
| T2.2 | AlertService | 条件引擎：price_change_pct、price_vs_ma、volume_spike | evaluate_rules 返回触发列表 |
| T2.3 | 定时任务 | 每 5 分钟 evaluate_all_rules | 触发后 alert_trigger 有记录 |
| T2.4 | Agent 工具 | set_price_alert、list_my_alerts、delete_alert | 说「TSLA 跌超 5% 提醒我」→ 创建规则 |
| T2.5 | 提醒推送 | 触发 → 会话内插入消息 | 对话框内出现「您有一条新预警：...」 |

### Phase 3：长期记忆 + 组合体检 [P1]

| ID | 任务 | 产出 | 验收 |
|----|------|------|------|
| T3.1 | MemoryService | add、search，按 user_id 隔离 | 写入后能检索到 |
| T3.2 | Context 集成 | 每次回答前 memory.search 注入 | 说「我偏好保守」后下次问策略能引用 |
| T3.3 | save_investment_note | 保存投资笔记到向量记忆 | 说「保存：对 TSLA 的逻辑是...」→ 写入 |
| T3.4 | get_portfolio_health | 基于 Position/SavedStock 体检 | 问「体检我的组合」→ 趋势/估值标签+点评 |

### Phase 4：交易分析 + 用户痛点 [P1-P2]

| ID | 任务 | 产出 | 验收 |
|----|------|------|------|
| T4.1 | import_trades | 粘贴 CSV 解析写入 | 说「导入交易」+粘贴 CSV → 写入 |
| T4.2 | 交易模式分析 | 识别高频短线、单股亏损、行业亏损等 | 写入向量记忆 |
| T4.3 | 相似历史提醒 | 检索到亏损模式时注入提醒 | 问类似操作时带「过去亏损过」提醒 |
| T4.4 | 行为干预 | 清仓前二次确认 | 有恐慌割肉记忆时先确认 |
| T4.5 | 克制提醒 | 追涨前提醒「先研究再决策」 | 有追涨亏损历史时带提醒 |

### Phase 5：能力标准化扩展 [P2]

| ID | 任务 | 产出 | 验收 |
|----|------|------|------|
| T5.1 | AnalysisModeRegistry | rule/ml/llm 可配置切换 | |
| T5.2 | ToolRegistry | 配置启用/禁用工具 | |
| T5.3 | SearchRegistry | 搜索引擎可配置切换 | |

### Phase 6：增强能力 [P2-P3]

| ID | 任务 | 产出 | 验收 |
|----|------|------|------|
| T6.0 | MCP Server | 暴露工具供 Cursor/Claude 接入 | |
| T6.1 | 舆情监控 | 对接 TrendRadar 或自建 | 持仓股重大新闻时提醒 |
| T6.2 | 策略回测 | 简单规则回测 | |
| T6.3 | 模拟交易 | 虚拟资金 + 实盘行情 | |
| T6.4 | 风控提醒 | 单股/行业超限、单日亏损超阈值 | |
| T6.5 | 目标量化 / 定投提醒 | user_profile 目标、定投提醒 | |

---

## 四、任务依赖（DAG）

```
T0.4 ──┬──► T0.1 ──► T0.2 ──► T0.3
       │
T1.1 ──► T1.2 ──┬──► T1.3
                ├──► T1.4 ──► T1.5
                └──► T3.4

T2.1 ──► T2.2 ──┬──► T2.3
                ├──► T2.4
                └──► T2.5

T3.1 ──┬──► T3.2 ──► T3.3
       ├──► T4.3
       └──► T4.4, T4.5

T1.2 ──► T4.1 ──► T4.2 ──► T4.3

T1.4, T2.4, T3.3, T3.4 ──► T6.0
```

---

## 五、验收里程碑

| 里程碑 | 验收标准 |
|--------|----------|
| M0 | 切换 LLM 模型后 Agent 与股票分析正常 |
| M1 | 说「记录买入 TSLA 100 股」完成录入；问「我现在的持仓怎么样」得到基于真实数据的回答 |
| M2 | 说「TSLA 跌超 5% 提醒我」创建预警；触发后会话内收到提醒 |
| M3 | 说「我偏好保守」保存后，下次问策略能引用；说「体检我的组合」得到结果 |
| M4 | 导入交易后，类似操作时能收到「过去亏损过」提醒 |
| M5 | 分析模式、工具、搜索可配置切换 |
| M6 | MCP Server 可被 Cursor/Claude 接入；舆情、回测、模拟交易等增强可用 |

---

## 六、执行顺序（Copy-Paste）

```
T0.4 T0.1 T0.2 T0.3
T1.1 T1.2 T1.3 T1.4 T1.5
T2.1 T2.2 T2.3 T2.4 T2.5
T3.1 T3.2 T3.3 T3.4
T4.1 T4.2 T4.3 T4.4 T4.5
T5.1 T5.2 T5.3
T6.0 T6.1 T6.2 T6.3 T6.4 T6.5
```

---

## 七、进度 Checklist

- **Phase 0：能力标准化基础**
  - [x] T0.4 依赖与配置
  - [x] T0.1 LiteLLM 集成
  - [x] T0.2 LLM 注册表
  - [x] T0.3 替换调用点

- **Phase 1：个人数据底座**
  - [x] T1.1 数据表（position、trade_log）
  - [x] T1.2 PositionService / TradeLogService
  - [x] T1.3 REST API（/user/positions、/user/trades）
  - [x] T1.4 Agent 工具（get_my_positions 等）
  - [x] T1.5 System prompt 更新

- **Phase 2：主动预警**
  - [x] T2.1 数据表（alert_rule、alert_trigger）
  - [x] T2.2 AlertService
  - [x] T2.3 定时任务（evaluate_all_rules）
  - [x] T2.4 Agent 工具（预警相关）
  - [x] T2.5 会话内提醒推送

- **Phase 3：长期记忆 + 组合体检**
  - [x] T3.1 MemoryService
  - [x] T3.2 Context 集成记忆检索
  - [x] T3.3 save_investment_note 工具
  - [x] T3.4 get_portfolio_health 工具

- **Phase 4：交易分析 + 用户痛点**
  - [x] T4.1 import_trades（CSV 导入）
  - [x] T4.2 交易模式分析
  - [x] T4.3 相似历史提醒
  - [x] T4.4 行为干预（二次确认）
  - [x] T4.5 克制提醒（FOMO）

- **Phase 5：能力标准化扩展**
  - [x] T5.1 AnalysisModeRegistry
  - [x] T5.2 ToolRegistry
  - [x] T5.3 SearchRegistry

- **Phase 6：增强能力**
  - [x] T6.0 MCP Server
  - [x] T6.1 舆情监控
  - [x] T6.2 策略回测
  - [x] T6.3 模拟交易
  - [x] T6.4 风控提醒
  - [x] T6.5 目标量化 / 定投提醒
