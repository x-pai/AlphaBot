# 盘前日报数据来源（westock 优先）

以下是已有调用经验，不保证连接、字段或代码永久可用；以本次实际工具 schema 与返回为准。T 是目标 A 股交易日，P 是 T 之前最近一个 A 股交易日。数据截止默认 T 08:30（Asia/Shanghai）；时间规则见 SKILL.md。

## 1. 先确认日期与市场状态

使用可用的交易日历确认 T、P；各海外市场独立确认交易日期、休市与时区。保存每项数据的来源、实际行情/发布时间、时区、市场范围和单位。报价缺少可信日期或时点时不能进入当日快照。

- A 股全日行情以 P 为准。早晨接口即使是刚请求的，也可能返回 P 的收盘、旧日期、清零值或 T 的占位，不能把请求时间当行情时间。
- 历史补跑时，实时 quote、hot、changedist 不能自动还原历史截面。只用截止前存档、能确认历史日期的 K 线/统计、或发布时间可核验的报道。
- 海外指数常规收盘与 ETF 盘后/夜盘分开；报价比较基准可能是前收盘或结算价，按供应商字段说明，不混算。

## 2. 上一交易日市场底盘

| 需求 | 调用线索 | 口径核验 |
| --- | --- | --- |
| 主要指数收盘 | `data_quote` codes=sh000001,sz399001,sz399006；按需增 sh000688、bj899050 | `price` / `prev_close` / `change_percent` 的实际含义与行情日；不能把 P 收盘字段误读成 T 已交易 |
| 历史价格与关键位置 | `data_kline` / `data_index`，按实际 schema 取 P 及以前数据 | 当前未完成 K 线剔除；复权、日期保持一致 |
| 宽度、成交、涨跌停 | `data_changedist` type=0 | `upCount` / `downCount` / `flatCount`、涨跌停、`totalAmount`、`amountChange` 均核对日期、范围、单位；P 全天只与此前交易日同口径全天比较 |
| 情绪与风格 | `data_market_overview` type=updown / summary / rotation，支持时明确 date=P | 子组日期可能不同；画像与原始统计冲突先查口径，不能用陈旧评分覆盖 P 的事实 |
| 板块与成分 | `data_sector` mode=list scope=sw1；mode=search query=方向；`data_hot` kind=board / stock | 行业清单未必含涨幅；热度不等于强度，8:30 热度不是今日 A 股涨幅 |
| 连板与涨停 | `tool_ranking` asset=stock metric=limitup_days date=P order=desc；按需 limitup_seal_volume | 核验返回日期、总量与截断；单页/Top N 不代表全市场，不据此判梯队断层；N 天 M 板与连续连板分开 |
| 资金与龙虎榜 | `data_fund_flow` codes=实际核心股 date=P；`data_lhb` date=P type=jg,yzb,yyb | 只补充与主判断相关证据；标明供应商资金口径，席位与持股数据不等于全市场当日流向 |

P 的连板高度只说明截至 P 的状态，“今日晋级”必须等待今日交易。无有效广度则标明缺口，不能把零值称为冰点。保留北向/主力/游资/融资等分类资金分析及表格，无法核验的项标明未获取，不虚构方向。

## 3. 美股最近收盘与亚洲早盘

### 美股与港股

- `data_quote` 既有代码：`usIXIC` 纳斯达克综指、`usDJI` 道琼斯、`usSPY` 标普 500 ETF、`usQQQ` 纳指 100 ETF；代码与实际返回名称交叉核验。SPY/QQQ 是 ETF，不能报成指数点位。
- 选择截止前最近完成的**常规交易时段**，注明美国交易日期；若 quote 返回的是盘后或夜盘，取可核验的常规收盘字段、历史日线或可靠收盘报道，不能直接把最新价称为收盘价。
- 港股 `hkHSI` 为恒生指数、`hkHSCEI` 为恒生中国企业指数；两者都不是恒生科技指数。T 08:30 仅引用最近收盘并标日期，不能称今日港股盘中。

### 日本与韩国（08:30 的重点增量）

- 先在当前可用的指数目录或行情搜索工具中定位日经 225 / TOPIX、KOSPI / KOSDAQ，核验代码与交易所后查询；不猜 westock 代码，也不把 ETF、期货当现货指数。
- 正常交易日两地当地 09:00（北京时间 08:00）开盘。用不晚于 T 08:30 的最新盘中快照，标报价时间、时区、是否延迟；有开盘点和当前点时才比较开盘后的变化，只有涨跌幅时只能比较前收盘。
- 结构化行情不可用，可用本次可用联网检索寻找交易所、指数提供商或可靠媒体早盘报道；必须读正文核对日期与报价时点。休市、没有早盘报价或无法复原历史时如实说明。

### 美股期货 / 夜盘（有可靠通道才补充）

- 先检索可用工具的品种目录，再选择真实可用的标普、纳指等股指期货，记录合约/连续合约、涨跌基准、时点与延迟。没有已核验代码就不调用猜测代码。
- 夜盘股票或 ETF 只写实际品种、交易时段与流动性背景；不能代表三大指数现货正在交易。
- 北京时间 08:30 不称“美股常规盘前”。夏冬令时、各交易所维护窗口和节假日按实际日期及返回核验。

## 4. 汇率与商品

- 外汇既有通道：`data_quote` codes=fxDINIW,fxCNH；分别为美元指数、离岸人民币，核对币对方向和字段。`fxUSDCNY` 是在岸行情，不能代替离岸；早晨可能尚未更新。
- 历史经验：`data_forex` 的 quote 模式可能只返回品种列表。先检查本次 schema 和返回，列表不能当行情；未知代码可能被静默忽略。
- 商品既有代码：`data_futures` mode=quote code=fuGC（黄金）、fuCL（WTI）、fuHG（铜）；其他如 hf_OIL、hf_CAD 先核验名称。关注 `updateTime` / `isDelayed` 及涨跌基准。
- 只保留影响今日判断的品种。无法取到实时行情时，可引用截止前可信快讯并注明媒体与报价时点，不能用人民币中间价替代 CNH 即期价。

## 5. 隔夜消息、公告与今日事件

- `data_hot` kind=news 作为发现线索；`data_news` symbol=实际候选 type=3、`data_notice` 核验公司消息/公告；`data_finsearch` 可检索收盘报道或题材消息，不能仅凭搜索摘要下结论。
- 检索窗口从 P 收盘到 T 信息截止，长假覆盖整个间隔；按新增信息重要性排序，不把旧新闻重新流行写成新催化。
- `data_calendar` date=T market=hs/hk/us 取今日已知日程；`data_macro` mode=indicator/expect、names、region、日期范围按需查询。发布时点晚于截止的实际值不可用，即使历史补跑时接口已经返回。
- 当日尚未发布的宏观值写“待公布”；预期注明来源。研报观点、AI 摘要与媒体推测不作为已确认事实。

## 6. 降级与来源

westock 不可用时，可使用本次可用 tdx 工具：`tdx_lookup_stock` 查实体，`tdx_quotes` / `tdx_kline` 取行情，`tdx_screener` 查询明确 P 日期的历史条件，`wenda_news_query` / `wenda_notice_query` 核验消息。查询是否支持历史日期、分页是否完整均以返回为准。

连接失败最多重试一次，再切换当前可用来源。核心 P 行情与日期均不可核验则输出短报；日韩或期货缺失只收缩外围结论，不能编补。报告保留重要事件的来源链接/公告编号；行情统一注明供应商和日期时点。

交易时段参考（仍需核验目标日期休市与实际报价）：[Nasdaq](https://www.nasdaq.com/market-activity/stock-market-holiday-schedule)、[JPX](https://www.jpx.co.jp/equities/trading/domestic/01.html)、[KRX](https://regulation.krx.co.kr/contents/RGL/03/03020401/RGL03020401.jsp)。

## 7. 完整分析模块的补充取数

- **题材股单**：`data_stocklist` mode=rank/detail，id、limit 按实际 schema；使用 `avgChangePct` 与 `accChangePct1M` 时核验实际统计日与覆盖范围，支撑主线强弱与持续性。
- **分类资金表**：保留 `data_fund_flow` 主力估算、`data_lhb` 机构/游资席位、可用的 `data_north_holding` 与 `data_fund_margin`。各工具按实际 schema 查询截止前已公布的最新统计期，标日期、单位和口径；持股与融资余额变化不冒充实时净流入。
- **上一交易日时间线**：`data_minute` 查询上证、创业板与 P 的 2–3 只实际主线/锚点股，每标的取一次即可。接口若只支持当前交易日，改用能返回 P 的历史分钟 K 线；核对时间戳。五模块保留标签、日内形状、轨迹、名场面、节点表；盘前/盘后消息与发生时点对齐，隔夜新增节点单列。
- **持仓体检**：仅在用户已提供数据或授权时调用 `get_my_positions` / `get_my_trades` / `get_portfolio_summary` / `get_orders`。保留持仓交易分析模块，无数据按模板注明跳过，不能自行生成持仓盈亏。
- **反包与连板**：`tool_ranking` metric=limitup_days / limitup_seal_volume、date=P；`data_finsearch` 提取 N 天 M 板需注明来源和发布时间。晋级率需要 P 与前一交易日的完整同口径池，不能从单份排名猜测；计算窗口截止 P。
