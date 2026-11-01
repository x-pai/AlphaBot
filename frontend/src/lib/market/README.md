# Market Data Notes

本目录承载市场主页的数据访问、缓存和快照拼装逻辑。本文档聚焦当前 `market` 模块的接口职责、缓存策略和刷新频次，方便后续继续收口数据层与业务层边界。

## 目录职责

- `api.ts`: 页面场景数据入口，负责组织请求、缓存键和轻量转换。
- `domain.ts`: 后端领域接口访问层，统一消费 `/market/*` 契约。
- `client.ts`: 前端缓存层，负责内存缓存、IndexedDB 持久缓存与请求去重。
- `snapshot.ts`: 页面级快照拼装层，把多个接口组合成市场页需要的 4 张卡片数据。
- `cycle.ts`: 龙头接力、断板反包等多日衍生逻辑。
- `sectorTrend.ts`: 趋势卡里的板块趋势聚合逻辑。
- `types.ts`: market 相关类型定义。

## 页面入口

市场主页使用的主要入口在 [page.tsx](../../app/page.tsx)：

- 首次进入市场页：`loadMarketSummarySnapshot()`
- 点击 `趋势` 卡：`loadTrendSnapshot()`
- 点击 `情绪` 卡：`loadEmotionSnapshot(days)`
- 点击 `主线` 卡：`loadMainlineSnapshot()`
- 点击 `赚钱效应` 卡：`loadPayoffSnapshot()`

## 缓存模型

`client.ts` 里有两层缓存：

- 内存缓存：进程内 `Map`
- 持久缓存：浏览器 `IndexedDB`

缓存行为：

- `cached()` 先查内存，再查持久层，最后才发请求
- 相同 `key` 的并发请求会复用同一个 `inflight Promise`
- 所有刷新统一走缓存逻辑：命中则复用，过期则重拉

## 页面刷新频次

页面层频次主要由 [page.tsx](../../app/page.tsx) 控制：

- 市场页会话级重载阈值：`60s`
- 自动刷新轮询间隔：`30s`
- 自动刷新只在交易时段触发
- 自动刷新只刷新用户开启了 `autoRefresh` 的卡片

说明：

- 首次进入市场页时先加载“总览快照”，不是一次性把 4 张卡片的完整明细都拉满
- 切换到某张还没加载过的卡片时，才补拉该卡完整数据
- 已命中缓存的数据不会重复打外部请求

## 快照与接口关系

### 1. 市场总览 `loadMarketSummarySnapshot`

用途：首次进入市场页时加载一份较轻的总览数据，提供 4 张卡片的首屏摘要。

会调用：`loadTradingDays(20)`、`loadTurnover()`、`loadLatestMarketContext()`、`loadStrong()`、`loadHot()`、`loadBigFace(tradingDays)`

### 2. 趋势卡 `loadTrendSnapshot`

会调用：`loadTurnover()`、`loadLatestMarketContext()`

依赖的领域数据：最新交易日、最新日池子、板块宇宙、异动题材补充。

### 3. 情绪卡 `loadEmotionSnapshot`

会调用：`loadTradingDays(20)`、`loadIntradayEmotion()`、`loadShortEmotion(days)`、`loadTopicPools(tradingDays)`

外部请求量最大的卡片，主要成本在多日池子批量拉取。

### 4. 主线卡 `loadMainlineSnapshot`

会调用：`loadLatestMarketContext()`、`loadTradingDays(20)`、`loadTopicPools(relayDays)`、`loadQuoteList(reboundWatchCodes)`

- `mainlineLanes` 依赖最新日板块宇宙和涨停池
- `relay` 依赖多日涨停/炸板池
- 断板反包观察池会额外打一笔批量实时行情

### 5. 赚钱效应卡 `loadPayoffSnapshot`

会调用：`loadTradingDays(20)`、`loadStrong()`、`loadHot()`、`loadBigFace(tradingDays)`

## 当前接口与缓存清单

### 前端请求层

| 逻辑函数 | 前端请求接口 | 主要用途 | 前端 TTL | 持久化 |
| --- | --- | --- | --- | --- |
| `loadTradingDays` | `/market/trading-calendar` | 交易日历 | `24h` | 是 |
| `loadTurnover` | `/market/turnover` | 成交额、预估成交、较昨变化 | `15s` | 否 |
| `loadIntradayEmotion` | `/market/emotion/intraday` | 分时情绪 | `15s` | 否 |
| `loadShortEmotion(days)` | `/market/emotion/short?days=` | 短线情绪曲线 | `2m` | 是 |
| `loadLatestMarketContext` | `/market/context/latest` | 最新交易日池子 + 题材索引 + 异动 + 板块宇宙 | `20s` | 是 |
| `loadPlateUniverse` | `/market/universe` | 板块宇宙：涨跌幅、净流入、涨跌家数、涨停家数 | `2m` | 是 |
| `loadTopicPools(days)` | `/market/pools/batch` | 多日涨停/炸板/跌停池批量拉取 | 历史窗 `7d`，最新日 `20s` | 是 |
| `loadPlateMembers` | `/market/plate-members?plateId=` | 板块成分股明细 | `2m` | 是 |
| `loadPlateDayKline` | `/market/plate-index?plateId=&count=` | 板块指数日 K | `5m` | 是 |
| `loadPlateFlowHistory` | `/market/plate-members` + `/market/fundflow` | 板块资金流历史（前端聚合） | 盘中 `3m`，收盘后 `48h` | 是 |
| `loadSurgeLimitUp` | `/market/surge` | 异动涨停与题材标签 | `45s` | 是 |
| `loadConceptIndexPool` | `/market/context/latest` | 从最新上下文提取涨停池题材标签索引 | `45s` | 是 |
| `loadTrendingPlates` | `/market/trending` | 趋势板块催化推荐 | `15m` | 是 |
| `loadQuoteList` | `/market/quotes?symbols=` | 观察池实时报价 | `20s` | 否 |
| `loadStrong` | `/market/payoff/strong` | 强势股列表 | `2m` | 是 |
| `loadHot` | `/market/payoff/hot` | 热榜列表 | `2m` | 是 |
| `loadBigFace` | `/market/payoff/drawdown?date=` | 大面股列表 | 最新候选 `2m`，历史候选 `7d` | 是 |
| `ensurePrivateStrategy` | `/market/strategy` | 下发 private 策略覆盖 | 会话内 1 次，失败回退 IDB `7d` | 是 |

### 后端刷新与 Redis 层

| 后端接口/键 | 刷新节流 | Redis TTL | 说明 |
| --- | --- | --- | --- |
| `/market/pool/{kind}` -> `market:pool:{kind}:{yyyymmdd}` | 盘中 `20s` single-flight，收盘后不再刷新 | 最新日无显式 TTL，历史日无显式 TTL，非交易日空标记 `1h` | 最新交易日读时刷新，历史日按需补采 |
| `/market/pools/batch` -> 复用 `market:pool:{kind}:{yyyymmdd}` | 逐项沿用单池读时刷新 | 继承单池策略 | 历史窗口批量回填，最新窗口批量复用 |
| `/market/context/latest` -> 复用 pool/universe/surge/strategy 现有键 | 逐项沿用各自刷新节流 | 继承子域策略 | 仅做“最新交易日上下文”聚合，不新增独立 Redis 键 |
| `/market/universe` -> `market:universe` | `45s` single-flight | `24h` | 后端只在过冷或缺失时回源 |
| `/market/surge` -> `market:surge` | `45s` single-flight | `24h` | 与宇宙相同策略 |
| `/market/quotes` -> `market:quotes:{sha1(symbols)}` | 请求合并 + 参数归一 key | `20s` | 批量行情按代码集缓存 |
| `/market/fundflow` -> `market:fundflow:{sha1}:{days}` | 请求合并 + 参数归一 key | 盘中 `3m`，收盘后 `48h` | 资金流按代码集和窗口缓存 |
| `/market/plate-members` -> `market:members:{plateId}` | 命中即返回 | 盘中 `2m`，收盘后 `24h` | 板块成分与行情合成结果缓存 |
| `/market/plate-index` -> `market:plate-index:{plateId}:{count}` | 命中即返回 | 盘中 `5m`，收盘后 `24h` | 板块指数日线缓存 |
| `/market/trending` -> `market:trending` | 命中即返回 | `15m` | 趋势推荐缓存 |
| `/market/payoff/{kind}` -> `market:payoff:{kind}:{date?}` | 命中即返回 | `strong/hot 2m`，`drawdown` 历史 `7d` | 赚钱效应按类型和日期缓存 |
| `/market/turnover` -> `market:turnover` | 命中即返回 | `15s` | 分钟成交额缓存 |
| `/market/strategy` -> `backend/data/strategy/private.defaults.json` | `GET/PUT /market/strategy` 直接读写文件 | 无 | 文件是唯一真相源，改文件后下次读取立即生效 |

## 关键口径说明

- **缓存分层（前后端分治）**：前端 TTL 控制页面重算频率；后端 `MarketDomainService` 控制回源频率；Redis 负责跨请求复用。真实回源频率取两层里更“冷”的那层。
- **最新上下文**：`/market/context/latest` 只聚合最新交易日必需数据，不单独落 Redis，直接复用池子 / 宇宙 / 异动现有缓存键。
- **批量池子**：前端改为“历史窗 1 笔 + 最新窗 1 笔”。历史窗走 `/market/pools/batch` 的 `zt/zb` 批量请求并缓存 `7d`；最新窗走 `zt/zb/dt` 批量请求并缓存 `20s`。
- **strategy 文件源**：`backend/data/strategy/private.defaults.json` 为空或缺失时会自动生成默认私有策略；后端 `/market/strategy` 直接读写该文件，不再经过 Redis。
- **动态 TTL**：`plate-members`、`plate-index`、`fundflow` 这三类含盘中变化字段的接口，后端改成盘中短 TTL、收盘后长 TTL；避免前端在主动刷新时仍被后端长缓存挡住。
- **主线三卡**：`mainline.ts` 多维打分选卡，组合了攻击性、梯队、空间地位、资金、持续性、封板质量与催化项。具体权重口径见对应代码注释。
- **板块资金流历史**：当前仍由前端串联 `/market/plate-members` 和 `/market/fundflow` 后聚合而成；`day_count` 服务端上限 10，因此 `loadPlateFlowHistory(limit)` 会被截断到 10。
- **候选留痕**：趋势界面每日把候选板块名单写入 IDB（`market:trendCandidates:{day}`，30 天），趋势视图读前 5 个交易日的快照计算“近 5 日跌出候选”；这份留痕只在本地 App 打开时积累，没有本地快照的日期自然缺失。
- **成分股/报价等其他领域接口**：现在也已统一接入后端 Redis；带参数的接口会先做参数归一化后生成 key，减少相同请求因顺序不同导致的缓存碎片。

## 频次估算（冷启动）

### 首次进入市场页

- `loadTurnover`: 1
- `loadTradingDays`: 1
- `loadTopicPools(tradingDays)`: 2
- `loadSurgeLimitUp`: 1
- `loadConceptIndexPool`: 1
- `loadPlateUniverse`: 1
- `loadStrong` / `loadHot` / `loadBigFace`: 3
- `loadTrendingPlates`: 1
- `/market/strategy`: 1

合计约 `11` 笔前端请求。

### 点击趋势卡

冷缓存约 `2` 笔：`loadTurnover` 1 + `loadLatestMarketContext` 1。

### 点击情绪卡

约 `4` 笔：`loadTradingDays(20)` 1 + `loadIntradayEmotion` 1 + `loadShortEmotion` 1 + `loadTopicPools(20日)` 1。

### 点击主线卡

若总览已加载过，增量约 `3` 笔：`loadTradingDays(20)` 1 + `loadTrendingPlates` 1 + `loadQuoteList` 1。若池子历史窗尚未命中，则再补 `1` 笔 `loadTopicPools`。

### 趋势轨迹明细（SectorTrendTrajectory）

- 底部使用 `SectorFlowHeatmap` 展示当前候选板块的资金持续性，支持 5/10 日视图、本页置顶和点击联动详情。
- `loadTradingDays(10)` 提供统一日期轴；候选历史按每批 3 个板块加载，完成后一次性更新，切换选中板块或榜单视角不再改变评分样本。
- 每板块调用 `loadPlateFlowHistory(id, 10)`，沿用成分股、资金流和交易日缓存；选中板块另加载成分详情。
- 颜色使用固定且对称的净占比档位（0、3%、8%），不做每日排名归一。净占比分母为主力买卖总额。
- 近 5 日统计要求统一日期窗口内数据齐全；缺失、占位点和非有限数值不计作零，最新值不会回退到过期日期。
- 历史强度仍按完整当前候选池计算金额百分位；只有一个有效样本时使用中性百分位 50。排名仅代表当前候选池，不代表历史全市场排名。
