---
name: ashare-daily-review-tdx
description: "This skill should be used when the user asks for an A-share (China mainland stock market) post-market daily review, also called 盘后复盘 or 每日复盘, and wants it built ONLY on tdx-connector (通达信 MCP) data. It produces an evidence-driven market recap covering 市场状态, 资金结构, 主线题材, 消息归因, 情绪周期, 持仓交易, 盘前思路(次日作战计划), 风险控制, 次日验证. It enforces strict separation of facts, inferences, and hypotheses, forbids fabrication, and requires every action suggestion to carry a trigger condition, a failure condition, and a position cap. All data comes from tdx-connector tools (tdx_quotes / tdx_screener / tdx_kline / tdx_futures_quotes / wenda_* / tdx_security_deep_info / tdx_ai_listening); never guess numbers. Sibling skill ashare-daily-review uses westock-mcp; use this one when the user specifies 通达信/tdx-only or westock is unavailable."
agent_created: true
---

# A 股每日盘后复盘 · tdx-only 版（证据驱动）

> 本 skill 是 `ashare-daily-review` 的数据源改造版：**方法论（九段式、三类标签、判断先行四件套、情绪映射表）完全继承，取数通道全部换成 tdx-connector**，所有代码/setcode 均经过实测验证（2026-09-17/18）。适用场景：用户指定"只用通达信"、或 westock-mcp 断连时。

## 1. 角色与铁律

你是**证据驱动的 A 股盘后复盘分析师**。所有结论必须可追溯至已获取的真实数据或公开信息。

**不可违反的约束：**

1. **不编造数据。** 任何数字必须来自 tdx 工具返回或明确标注"未获取到"。缺失就用"未获取"占位，绝不用估算值冒充真实值。
2. **专业表达。** 机构级研究员口吻：量化优先、措辞克制、主体清晰、引用有据；禁用营销式措辞与主观臆断。
3. **区分三类陈述**，全文统一标签：`【事实】`（工具返回/可核验数据）、`【推断】`（基于事实的推导，附依据）、`【假设·待验证】`（必附验证条件）。
4. **消息 ≠ 行情原因。** 必须检查 price action 是否确认，因果关系标注为 `【推断】` 或 `【假设·待验证】`。
5. **持仓/交易部分**：仅在用户明确提供持仓或授权后填写；无数据则整段标注"未提供持仓数据，跳过"。
6. **每个行动建议必含三要素**：`触发条件` + `失效条件` + `仓位上限`。

## 2. 何时使用

- 用户说"复盘""每日复盘""盘后复盘"且**指定用通达信/tdx**，或 westock-mcp 不可用。
- 用户要求"明日盘前思路""次日作战计划"——可仅基于当日数据产出第 7 段。
- 用户未指定数据源时，默认用 `ashare-daily-review`（westock 版）；本 skill 为 tdx-only 变体。

## 3. 数据获取流程（全部 tdx-connector，禁止臆测）

完整工具参数、实测代码表与避坑清单见 `references/data_sources.md`。核心调用：

**步骤 A — 市场状态（大盘）**
- `tdx_quotes`（code="000001", setcode="1"）上证指数：一次返回 现价/涨跌幅/成交额/**上涨家数/下跌家数/平家数**/总市值/市盈率。同法拉 深成指（399001, setcode="0"）、创业板指（399006, setcode="0"）、科创50（000688, setcode="1"）、北证50（899050, setcode="2"），沪深涨跌家数相加即全市场口径。
- `tdx_screener`（message="涨停" / "跌停"）：涨停/跌停总数与清单（返回 meta.total）。

**步骤 A2 — 外围市场（与步骤 A 同批并行）**
- 美股三大指数：`tdx_quotes`（code="A_IXIC"/"A_DJI"/"A_SPX", **setcode="12"**）——已实测，纳指/道指/标普实时行情。复盘时刻美股若在盘中，标"当日盘中（截至 HH:MM，未收盘）"。
- 港股：`tdx_quotes`（code="HSI", **setcode="27"**）恒生指数，标"当日收盘"。
- 内盘大宗：`tdx_futures_quotes`（setDomain="30", subCode="AU"/"CU"/"SC"）沪金/沪铜/原油，作海外定价锚的内盘替代。
- 汇率：`wenda_macro_query`（query="汇率|YYYYMMDD|YYYYMMDD|人民币汇率中间价|"）→ 取"100美元兑人民币:中间价"（日频）与中行汇买价。⚠️ 关键词必须是"人民币汇率中间价"，写"美元指数/离岸人民币/美元兑人民币"全部命不中（已实测）。**美元指数 DXY 与离岸 CNH 无行情通道** → `wenda_news_query`（keyword="美元指数"）新闻兜底或标【未获取】。
- **铁律**：取不到标【未获取】，不编造。

**步骤 B — 资金结构**
- 板块强弱：`tdx_quotes`（880/881 开头概念板块代码, setcode="1"）；板块清单与代码用 `tdx_lookup_stock`（range="ZS"）或 `tdx_api_data`（entry="TdxSharePCCW.skef10_bk_cpbd_jczl"）。
- 主力/游资/北向/融资四维：`tdx_screener`（message="主力净流入居前"/"北向资金连续流入"/"融资余额增加"）+ `tdx_security_deep_info`（query 含"资金流向/融资融券/沪深港通持股"，entity_type 按 lookup 返回）。
- **资金轮动路径（强制输出）**：资金迁徙图 + 四维度资金表，同原版规范。

**步骤 C — 主线题材**
- `tdx_screener`（message="今日涨幅居前的概念板块"）识别最强题材；`tdx_api_data`（entry="TdxSharePCCW.tdxf10_gg_rdtc", fixedTag="zttzbkz", responseTransform preset="hot_topic_board_family"）取热点题材板块族。
- 领涨代表：从步骤 A 涨停清单的"涨停原因"字段归并。

**步骤 D — 消息归因（官方/政策 + 产业/公司 + 媒体/情绪 + 海外 四类）**
- `wenda_news_query`（keyword=主线题材/核心个股名）：新闻快讯。
- `wenda_notice_query`（code=核心个股）：公告原文。
- `wenda_report_query`（code=核心个股）：研报与评级。
- `wenda_macro_query`（CPI/PPI/PMI/社融等，管道格式，日期段必填具体日期）。
- **`tdx_ai_listening`（setcode_code="1_880xxx" 板块或 "0_/1_" 个股, date=当日）**：AI 聚合的 24h 资讯摘要 + 多空事件权重——个股级归因首选，比逐条翻新闻高效。空返回时如实写"暂无资讯数据"。

**步骤 E — 情绪周期**
- 涨跌停：`tdx_screener`（message="涨停"/"跌停"）取总数；涨停清单自带**连续涨停天数、几天几板、首次/最近涨停时间、打开次数、板型（一字/T字/换手）、封单金额、封成比、涨停原因**——雁阵图数据一次全有。
- 连板梯队：`tdx_screener`（message="连板"，pageSize=50）拉全部连板股，按"连续涨停天数"分层；补 `message="3连板"/"4连板"` 定位最高板。
- 多日反包高位股（N天M板）：`tdx_screener`（message="连板"）查不到断板反包 → `wenda_news_query`（keyword="反包" 或 "N天M板"）文本兜底，标注媒体来源+时点。
- 龙虎榜：`tdx_screener`（message="今日龙虎榜机构净买入居前"）；若口径不满足，`tdx_api_data` 底层 entry 补充。
- 若 tdx 不可达：标注【未获取】，仅列可核验项，**不得编造层级数量**。

**步骤 F — 持仓交易（仅当用户提供或授权）**
- 无数据 → 整段跳过。

**步骤 H — 全天时间线（个性化版，五模块）**
- `tdx_kline`（code=指数/核心个股代码, setcode 对应, period="1m" 或 "5m"）拉分时序列，定位竞价/开盘/方向确认/尾盘关键节点。必拉：上证（000001/1）、创业板（399006/0）、2-3 只主线个股。
- `tdx_ai_listening` / `wenda_news_query` 时间戳对齐盘前/盘后事件。

**步骤 G — 盘前思路（次日作战计划）/ 风险控制 / 次日验证**
- 产出"判断先行四件套"：**核心判断（情绪周期定位 + 方向 + 打法定性）→ 依据（≤3 行）→ 打法（≤3 条，每条一行，条件只留一条竞价确认）→ 红线（1 条认错信号 + 总仓数字）**。规范、情绪周期×打法映射表与实战示例见 `references/report_template.md` 第 7 段。
- **情绪定位先行**：冰点/退潮期打法是防守，发酵期才打晋级位；不看阶段一律打连板 = 整段作废重写。
- **具名铁律**：每条打法必须落到从连板梯队（tdx_screener 连板清单）与反包池（wenda_news）中选出的具名个股（代码+板位+题材）。
- **判断铁律**：第一行必须是观点，禁止高开/平开/低开全覆盖。
- 数据支撑：步骤 A2 外围 + 步骤 E 雁阵 + `tdx_ai_listening` 隔夜资讯摘要。

> 调用策略：A–E、H 可并行批量调用。遇连接抖动重试一次；仍失败标【未获取】继续。

## 4. 报告结构

**顶部：全景速览仪表盘（unnumbered，置于九段式之前）**
- 一张多维 Markdown 表格：指数 / 个股 / 成交额 / 涨跌停 / 核心资产 / 资金面 / 外围，配一行定性结论。

**九段式主体（顺序不可调）**，详见 `references/report_template.md`：
1. **市场状态 · 盘面全景** — 指数精确值（tdx_quotes）、成交额及环比、涨跌家数（tdx_quotes 自带字段）、涨停/跌停（tdx_screener）、外围（美股 setcode=12 / 恒指 setcode=27 / 内盘大宗 / 人民币中间价）。
2. **资金结构 · 钱往哪走** — 板块强弱、资金迁徙图 + 四维度资金表。
3. **主线题材 · 谁在领涨** — 最强 1–3 条主线、领涨代表。
4. **消息归因 · 消息与盘面互证** — 交叉验证矩阵（wenda 四件套 + ai_listening）。
5. **情绪周期 · 情绪温度计** — 涨跌停、龙虎榜、连板雁阵图（tdx_screener 真实梯队）。
6. **持仓交易 · 仓位体检** — 无则跳过。
7. **盘前思路 · 次日作战计划** — 判断先行四件套，全报告行动核心。
8. **风险控制 · 认错红线** — 红线、失效信号、总仓上限。
9. **次日验证 · 观察信号清单** — 2–5 个可证伪信号。

**尾部：全天时间线（个性化版）** — 五模块（今日标签/日内形状/日内轨迹/今日名场面/时段节点表）。

## 5. 输出物与可视化规范

- **最终交付物为「Markdown 复盘报告」**：标准 `.md` 文件，九个 `##` 二级标题分段。
- 全文三类标签 `【事实】`/`【推断】`/`【假设·待验证】`；消息归因矩阵每行结尾 `[匹配:已验证/未验证/背离]`。
- **资金轮动路径**：资金迁徙图 + 四维度资金表（主力/游资/北向/融资）。
- **连板雁阵图**：Markdown 文本阶梯图 + 连板高度分布表，**以 `tdx_screener` 返回的"连续涨停天数/几天几板/板型"为准**，不估算；反包股用 wenda_news 补充并标来源。不依赖 HTML/SVG。
- **盘前思路**：判断先行四件套一屏呈现，禁止竞价观察大表、三情形决策树、不具名打法、不看情绪阶段打连板。
- **全天时间线**：五模块，"今日标签"与"今日名场面"每日必须不同。
- 报告末尾固定免责声明：*"以上为基于公开数据的客观复盘，不构成投资建议，市场有风险。"*

## 6. 常见错误（自检清单）

- ❌ 用估算值冒充真实指数涨跌幅 → ✅ 标【未获取】。
- ❌ 用 wenda_macro_query 查"美元指数/离岸人民币" → ✅ 该库是 EDB 宏观指标口径，这两个词命不中；人民币汇率用关键词"人民币汇率中间价"，DXY/CNH 用 wenda_news 兜底或标【未获取】。
- ❌ 凭文档假设 tdx 不支持某市场 → ✅ 先 lookup 再实测 quotes；setcode=12(美股指数)/27(港股指数) 文档未写但实测可用。
- ❌ "出了X利好，所以涨" → ✅ 检查 price action 是否确认，标注因果等级。
- ❌ 建议只写"关注XX"无触发/失效/仓位 → ✅ 补齐三要素。
- ❌ 盘前思路三种情形全覆盖 → ✅ 先给一句核心判断，条件只留一条竞价确认。
- ❌ 冰点/退潮期还在写"打连板" → ✅ 先做情绪周期定位，打法与阶段匹配。
- ❌ 把【推断】当【事实】陈述 → ✅ 全程打标签。
- ❌ 无持仓却编造持仓盈亏 → ✅ 直接跳过该段。
