# 数据源手册（ashare-daily-review-tdx · 全部 tdx-connector）

本文件列出复盘可用的全部 tdx 工具、实测参数与避坑清单。**所有代码/setcode/关键词均经过 2026-09-17/18 实测验证**，与 connector 官方文档不一致处以本文件实测为准。

---

## A. 行情类

### tdx_quotes —— 实时行情快照（市场状态 + 外围核心）

参数：`code`（纯数字或指数字母代码）+ `setcode`（市场代码，必须与 code 匹配）。可选 `hasCwInfo="1"` 附带 PE/PB/ROE。

**实测可用的 setcode 总表（含文档未记载项）：**

| setcode | 市场 | 实测代码示例 |
|---|---|---|
| 1 | 沪市/概念板块(880/881) | 000001 上证指数、600519、000688 科创50、880564 板块 |
| 0 | 深市 | 399001 深成指、399006 创业板指、000001 平安银行 |
| 2 | 北交所 | 899050 北证50 |
| **12** | **美股指数（文档未写，实测可用）** | A_IXIC 纳斯达克、A_DJI 道琼斯、A_SPX 标普500 |
| **27** | **港股指数（文档未写，实测可用）** | HSI 恒生指数、HZ5017 恒生科技、HZ5014 恒生中国企业 |
| 31 | 港股个股 | 00700 腾讯 |
| 62 | 中证指数 | 000300 沪深300 |

**指数返回自带的关键字段**（复盘直接取用，无需另查）：
- `上涨家数` / `下跌家数` / `平家数` —— 上证+深证相加即全市场涨跌分布
- `Amount` 成交额、`Close` 昨收（算环比）、`LB` 量比、`HSL` 换手率
- ExtInfo：`ZSZ` 总市值、`SYL` 市盈率

**避坑**：code 与 setcode 不匹配时返回空而非报错；期货合约 quotes 只返名称无行情（用 tdx_futures_quotes）。

### tdx_kline —— K 线（全天时间线）

参数：`code` + `setcode` + `period`（`1m`/`5m`/`day`/`week`/`month`）+ `count`。用于步骤 H 分时轨迹：period="1m" 取竞价/开盘/方向确认/尾盘代表时点，每标的只拉一次。

### tdx_futures_quotes —— 期货多合约行情（内盘大宗锚）

参数：`setDomain` + `subCode`。常用 setDomain：30=上期所/上能源、29=大商所、28=郑商所、47=中金所、66=广期所、60=主力合约。
- 黄金 `setDomain="30", subCode="AU"`；铜 `CU`；原油 `SC`；白银 `AG`；碳酸锂 `setDomain="66", subCode="LC"`。
- 只有中文品种名时先 `tdx_lookup_stock(query="黄金", range="QH")` 拿参数。
- `tdx_futures_deep_info`（query 自然语言，须含品种代码）可查基差/持仓排行/资金流。

### tdx_lookup_stock —— 代码检索（所有精确代码的入口）

参数：`query` + `range`（默认 AG=A股；HK-GP 港股；**MG-GP 美股个股**；ZS 指数；QH 期货；QQ 期权；JJ 基金）。
- 返回 entity_code / entity_setcode / entity_type，喂给 quotes/kline/security_deep_info。
- **避坑**：语义检索可能跑偏（实测"美元指数"返回标普/恒指、"离岸人民币"返回一带一路指数）——**美元指数 DXY 与离岸人民币 CNH 在 tdx 无任何指数代码**，不要硬查。

---

## B. 选股与情绪类

### tdx_screener —— 自然语言选股（情绪周期 + 资金 + 涨跌分布核心）

参数：`message`（自然语言）+ `rang`（默认 AG）+ `pageNo`/`pageSize`。

**复盘实测高频用法：**

| 用途 | message 示例 | 返回亮点 |
|---|---|---|
| 涨停清单+梯队 | "涨停"（pageSize=50） | meta.total=涨停总数；每只含**连续涨停天数、几天几板、首次/最近涨停时间、打开次数、板型、封单金额、封成比、涨停原因** |
| 连板梯队 | "连板" / "3连板" / "4连板" | 按连续涨停天数直接分层 |
| 跌停数 | "跌停" | meta.total |
| 主力资金 | "主力净流入居前" | 个股主力净流入排名 |
| 北向 | "北向资金连续流入" | 北向口径个股 |
| 融资盘 | "融资余额增加" | 融资口径个股 |
| 题材强度 | "今日涨幅居前的概念板块" | 板块排名 |

**避坑**：不支持期货/期权（rang 无此市场）；返回列表需二次分析时用 sec_code 接 quotes/kline。

---

## C. 资讯与宏观类（wenda 四件套 + ai_listening）

### wenda_news_query —— 新闻快讯（消息归因 + 汇率/DXY 兜底）
- `keyword`（必填）+ `category` + `date_range` + `limit`。
- 美元指数/离岸人民币无行情通道时的兜底：keyword="美元指数" 从快讯文本提取价位，**必须标注媒体名+报价时点**。
- 反包高位股检索：keyword="反包"/"连板"。

### wenda_notice_query —— 公告
- `code`（必填）+ `notice_type` + `date_range` + `limit`。

### wenda_report_query —— 研报
- `code`（必填）+ `keyword` + `date_range`（如 "last_30_days"）+ `limit`。

### wenda_macro_query —— 宏观 EDB 数据（汇率的正确通道）
- **仅支持管道格式**：`query="主体|开始日期YYYYMMDD|结束日期YYYYMMDD|关键词|补充说明"`，日期段必填具体日期，禁止留空/模糊词。
- **人民币汇率（实测命中的写法）**：`query="汇率|20260910|20260918|人民币汇率中间价|"` → 返回"100美元兑人民币:中间价"（日频，除以 100 即 USDCNY）+"100美元兑人民币:汇买价(中行)"。
- **实测命不中的写法（禁用）**：关键词"美元指数""离岸人民币""美元兑人民币"——分别返回有效汇率指数旧数据/化工品离岸价/外汇掉期点，均无目标价位。
- **美元指数 DXY 与离岸 CNH 现汇：本库没有**，走 wenda_news 兜底或标【未获取】。
- 宏观指标（CPI/PPI/PMI/社融/M2）正常可用。

### tdx_ai_listening —— AI 资讯聚合摘要（个股/板块级归因首选）
- `setcode_code`（"市场_代码"：0_深 / 1_沪或880板块 / 2_北 / 31_港）+ `date`（YYYY-MM-DD，缓存约近 3 天）。
- 返回一句话概要 + 关键事件列表 + 多空权重，响应 3-15 秒。
- 空返回（"暂无该品种的资讯数据"）必须如实告知，禁止编造。

---

## D. 深度资料类

### tdx_security_deep_info —— 证券深度资料（资金四维补充）
- 前提：先 `tdx_lookup_stock` 锁定实体，`entity_type` 原样传入。
- 复盘可用面：个股/指数的**资金流向、融资融券（概要+明细）、沪深港通持股（概要+明细）**、财务、股东、估值。
- query 必须写清具体实体 + 要查的资料，如"查询 000300 指数 沪深港通持股概要"。

### tdx_api_data —— 统一底层入口（高级场景）
- 板块基础资料/资金流：`entry="TdxSharePCCW.skef10_bk_cpbd_jczl" branch="003" code="880976" timeType="1m"`
- 热点题材板块族：`entry="TdxSharePCCW.tdxf10_gg_rdtc" code=个股 fixedTag="zttzbkz" responseTransform={"kind":"preset","preset":"hot_topic_board_family"}`
- 优先自动路由（entry+判别参数），不行再显式 mode，最后 raw 兜底。

### tdx_technical_indicator_lookup / query —— 技术指标（可选增强）
- 先 lookup 拿指标 id/set/parameters，再 query（code 格式 "market|code" 如 "0|000001"，period 仅支持 "4"=日线）。
- 用于核心个股 MACD/KDJ/BOLL 时序，增强盘前思路的技术依据。

---

## E. 缺口总表（唯一软缺口：DXY + CNH 市场价）

| 数据 | 通道 | 状态 |
|---|---|---|
| 指数行情/涨跌家数/成交额 | tdx_quotes | ✅ |
| 涨停/跌停/连板梯队/封单 | tdx_screener | ✅ |
| 资金四维（主力/游资/北向/融资） | tdx_screener + tdx_security_deep_info | ✅ |
| 题材/新闻/公告/研报/宏观 | wenda 四件套 + tdx_ai_listening + tdx_api_data | ✅ |
| 美股三大指数 | tdx_quotes setcode=12（A_IXIC/A_DJI/A_SPX） | ✅ |
| 港股恒指 | tdx_quotes setcode=27（HSI） | ✅ |
| 内盘大宗（金/铜/油） | tdx_futures_quotes | ✅ |
| 人民币中间价/中行牌价 | wenda_macro_query（关键词"人民币汇率中间价"） | ✅ |
| **美元指数 DXY** | 无行情通道 | ⚠️ wenda_news 兜底/【未获取】 |
| **离岸人民币 CNH 市场价** | 无行情通道 | ⚠️ 有在岸中间价替代；严格需要时 wenda_news 兜底 |
