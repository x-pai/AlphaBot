import { isCompletePlate } from './api';
import {
  loadBigFace,
  loadHot,
  loadIntradayEmotion,
  loadQuoteList,
  loadShortEmotion,
  loadStrong,
  loadTopicPools,
  loadTradingDays,
  loadTrendingPlates,
  loadTurnover,
  stockConcepts,
  type PlateFlow,
  type SurgeLimitStock,
  type TopicStock,
} from './api';
import { cached, getMarketSourceInfo, TTL } from './client';
import { buildRelaySnapshot } from './cycle';
import { fetchLatestMarketContext } from './domain';
import { formatShortDate, isAfterMarketClose, normalizeCode, yyyymmdd } from './format';
import { buildMainlineLanes } from './mainline';
import { ensurePrivateStrategy, getStrategy, isPrivateLoaded } from './strategy';
import { buildSectorTrendData } from './sectorTrend';
import { indexedDBCache } from '../indexedDBCache';
import {
  DEFAULT_MARKET_SNAPSHOT,
  type MarketBoardLevel,
  type MarketEmotionPoint,
  type MarketGeeseRow,
  type MarketGeeseStock,
  type MarketMainlineLane,
  type MarketSnapshot,
  type MarketTrendTopic,
} from './types';

export { DEFAULT_MARKET_SNAPSHOT } from './types';
export type { MarketSnapshot } from './types';

const DEFAULT_EMOTION_DAYS = 5;
const FULL_EMOTION_DAYS = 20;

/** 从最近涨停池派生盘中异动源，不依赖上游 surge 是否收录该股票。 */
function buildRecentLimitUpUniverse(
  days: string[],
  latestDay: string,
  ztByDate: Map<string, TopicStock[]>
): SurgeLimitStock[] {
  const latestIndex = days.lastIndexOf(latestDay);
  const priorDays = (latestIndex >= 0 ? days.slice(0, latestIndex) : days.slice(0, -1)).slice(-getStrategy().rebound.lookback);
  const stocks = new Map<string, SurgeLimitStock>();
  priorDays.forEach((date) => {
    (ztByDate.get(date) || []).forEach((stock) => {
      const code = normalizeCode(stock.code);
      if (!code) return;
      stocks.set(code, {
        code,
        name: stock.name,
        plates: stockConcepts(stock),
      });
    });
  });
  return Array.from(stocks.values());
}

export type MarketEmotionSnapshot = {
  emotionSeries: MarketEmotionPoint[];
  intradayEmotion: MarketSnapshot['intradayEmotion'];
  shortEmotion: MarketSnapshot['shortEmotion'];
  facts: string[];
};

export type MarketTrendSnapshot = {
  turnover: MarketSnapshot['turnover'];
  sectorTrend: MarketSnapshot['sectorTrend'];
  facts: string[];
};

export type MarketMainlineSnapshot = {
  mainlineLanes: MarketMainlineLane[];
  relay: MarketSnapshot['relay'];
  facts: string[];
};

export type MarketPayoffSnapshot = {
  payoffLists: MarketSnapshot['payoffLists'];
  facts: string[];
};

type TopicPoolsBundle = {
  ztByDate: Map<string, TopicStock[]>;
  zbByDate: Map<string, TopicStock[]>;
  dtByDate: Map<string, TopicStock[]>;
};

type LatestMarketContext = {
  latestDay: string;
  pools: TopicPoolsBundle;
  latestZt: TopicStock[];
  latestZb: TopicStock[];
  latestDt: TopicStock[];
  surge: Awaited<ReturnType<typeof fetchLatestMarketContext>>['surge'];
  conceptIndex: Map<string, string[]>;
  /** 全量板块宇宙（xgb 两笔请求覆盖，priorityNames 补拉机制已移除） */
  baseUniverse: PlateFlow[];
  trendUniverse: PlateFlow[];
};

function joinNames(names: Array<string | undefined>, limit = 2): string {
  const values = names.filter((name): name is string => Boolean(name)).slice(0, limit);
  return values.length > 0 ? values.join('、') : '--';
}

function settledValue<T>(result: PromiseSettledResult<T>, fallback: T): T {
  return result.status === 'fulfilled' ? result.value : fallback;
}

function boardHeight(stock: TopicStock): number {
  return Math.max(1, stock.lbc || 1);
}

function groupZtByHeight(list: TopicStock[]): Map<number, TopicStock[]> {
  const grouped = new Map<number, TopicStock[]>();
  list.forEach((stock) => {
    const height = boardHeight(stock);
    const rows = grouped.get(height) || [];
    rows.push(stock);
    grouped.set(height, rows);
  });
  grouped.forEach((rows) => rows.sort((a, b) => (a.time ?? Infinity) - (b.time ?? Infinity)));
  return grouped;
}

function attachConcepts(list: TopicStock[], index: Map<string, string[]>): TopicStock[] {
  if (index.size === 0) return list;
  return list.map((stock) => {
    const concepts = index.get(normalizeCode(stock.code));
    return concepts && concepts.length > 0 ? { ...stock, concepts } : stock;
  });
}

function plateOf(stock: TopicStock): string | undefined {
  const name = stock.reason?.trim();
  if (!name || name === '其他') return undefined;
  return name.split(/[、,/|]/)[0]?.trim() || undefined;
}

function toGeeseStock(stock: TopicStock, result: MarketGeeseStock['result'], note: string): MarketGeeseStock {
  return { name: stock.name, code: stock.code, change: '', note, result, plate: plateOf(stock) };
}

function deriveGeese(prevZt: TopicStock[], currZt: TopicStock[], zbList: TopicStock[]): MarketGeeseRow[] {
  const prevByHeight = groupZtByHeight(prevZt);
  const currByHeight = groupZtByHeight(currZt);
  const currByCode = new Map(currZt.map((stock) => [normalizeCode(stock.code), stock]));
  const zbByCode = new Map(zbList.map((stock) => [normalizeCode(stock.code), stock]));
  const rows: MarketGeeseRow[] = [...prevByHeight.keys()]
    .sort((a, b) => b - a)
    .map((height) => {
      const prevStocks = prevByHeight.get(height) || [];
      const nextCodes = new Set((currByHeight.get(height + 1) || []).map((stock) => normalizeCode(stock.code)));
      const stocks = prevStocks.map((stock) => {
        const code = normalizeCode(stock.code);
        const today = currByCode.get(code);
        if (nextCodes.has(code) || (today && boardHeight(today) > height)) {
          return toGeeseStock(today || stock, 'success', '晋级');
        }
        const broken = zbByCode.get(code);
        if (broken) return toGeeseStock(broken, 'broken', '炸板');
        return toGeeseStock(stock, 'failed', '断板');
      });
      return {
        progress: `${height}进${height + 1}`,
        numerator: stocks.filter((stock) => stock.result === 'success').length,
        denominator: stocks.length,
        stocks,
      };
    });

  const firstBoard = currByHeight.get(1) || [];
  if (firstBoard.length > 0) {
    rows.push({
      progress: '首板',
      numerator: firstBoard.length,
      denominator: firstBoard.length,
      stocks: firstBoard.map((stock) => toGeeseStock(stock, 'success', '涨停')),
    });
  }
  return rows.filter((row) => row.denominator > 0);
}

function emotionFromZt(date: string, ztList: TopicStock[], geeseRows: MarketGeeseRow[]): MarketEmotionPoint | null {
  const grouped = groupZtByHeight(ztList);
  const heights = [...grouped.keys()].sort((a, b) => b - a);
  const maxHeight = heights[0] || 0;
  if (maxHeight === 0) return null;
  const allLevels: MarketBoardLevel[] = heights.map((height) => {
    const stocks = grouped.get(height) || [];
    return {
      height,
      number: stocks.length,
      stocks: stocks.map((stock) => stock.name),
      code_list: stocks.map((stock) => ({ name: stock.name, code: stock.code })),
    };
  });
  const maxData = allLevels[0];
  const secondData = allLevels[1] || { height: 0, number: 0, stocks: [], code_list: [] };
  return {
    label: formatShortDate(date).replace('/', '-'),
    fullDate: date,
    maxHeight,
    secondHeight: secondData.height,
    maxCount: maxData.number,
    secondCount: secondData.number,
    maxNames: maxData.stocks,
    secondNames: secondData.stocks,
    allLevels,
    geeseRows,
  };
}

function buildTopicFundMap(...groups: TopicStock[][]): Map<string, number> {
  const funds = new Map<string, number>();
  groups.flat().forEach((stock) => {
    stockConcepts(stock).forEach((name) => {
      funds.set(name, (funds.get(name) || 0) + (stock.fund || 0) / 1e8);
    });
  });
  return funds;
}

let inflight: Promise<MarketSnapshot> | null = null;

function emotionFacts(series: MarketEmotionPoint[]): string[] {
  const latest = series[series.length - 1];
  if (!latest) return DEFAULT_MARKET_SNAPSHOT.diagnostics.情绪.facts;
  return [
    `最高板 ${joinNames(latest.maxNames, 2)} ${latest.maxHeight}板`,
    `次高板 ${joinNames(latest.secondNames, 2)} ${latest.secondHeight}板`,
    `最高板家数 ${latest.maxCount}只`,
  ];
}

function trendFacts(turnover: MarketSnapshot['turnover']): string[] {
  if (!turnover) return DEFAULT_MARKET_SNAPSHOT.diagnostics.趋势.facts;
  return [
    `当前成交 ${turnover.currentText}`,
    `预估全天 ${turnover.predictText}`,
    `较昨日 ${turnover.changeText}`,
  ];
}

function mainlineFacts(lanes: MarketMainlineLane[]): string[] {
  if (lanes.length === 0) return DEFAULT_MARKET_SNAPSHOT.diagnostics.主线.facts;
  const top = lanes[0];
  return [
    `${top.name} 涨停${top.ztCount}只${top.maxHeight > 0 ? ` 最高${top.maxHeight}板` : ''}`,
    `资金 ${lanes.slice(0, 2).map((lane) => `${lane.name} ${lane.value}`).join(' / ')}`,
    `龙头股 ${top.leader?.name || '--'}`,
  ];
}

function payoffFacts(payoffLists: MarketSnapshot['payoffLists'], hotUnavailable = false): string[] {
  return [
    `强势股 ${joinNames(payoffLists.strong.map((item) => item.name))}`,
    hotUnavailable ? '人气榜暂停：尚未确认低成本排名接口' : `热榜股 ${joinNames(payoffLists.hot.map((item) => item.name))}`,
    `大面代表 ${joinNames(payoffLists.bigface.map((item) => item.name))}`,
  ];
}

function emptyPools(): TopicPoolsBundle {
  return {
    ztByDate: new Map<string, TopicStock[]>(),
    zbByDate: new Map<string, TopicStock[]>(),
    dtByDate: new Map<string, TopicStock[]>(),
  };
}

async function latestContextAnchor() {
  const today = yyyymmdd();
  const tradingDays = await loadTradingDays(1);
  const anchor = tradingDays[tradingDays.length - 1] || today;
  return {
    anchor,
    closed: anchor !== today || isAfterMarketClose(),
  };
}

async function loadLatestMarketContext(): Promise<LatestMarketContext> {
  const { anchor, closed } = await latestContextAnchor();
  const payload = await cached<Awaited<ReturnType<typeof fetchLatestMarketContext>>>(
    `market:context:latest:${anchor}`,
    closed ? TTL.days(7) : TTL.seconds(20),
    false,
    async () => await fetchLatestMarketContext()
  );
  const latestDay = payload.latestDay || '';
  const pools: TopicPoolsBundle = {
    ztByDate: new Map(Object.entries(payload.pools?.ztByDate ?? {})),
    zbByDate: new Map(Object.entries(payload.pools?.zbByDate ?? {})),
    dtByDate: new Map(Object.entries(payload.pools?.dtByDate ?? {})),
  };
  const conceptIndex = new Map(
    Object.entries(payload.conceptIndex ?? {}).map(([code, names]) => [normalizeCode(code), names])
  );
  const latestZt = attachConcepts(payload.latestZt ?? [], conceptIndex);
  const latestZb = payload.latestZb ?? [];
  const latestDt = payload.latestDt ?? [];

  return {
    latestDay,
    pools,
    latestZt,
    latestZb,
    latestDt,
    surge: payload.surge ?? [],
    conceptIndex,
    baseUniverse: (payload.baseUniverse ?? []).filter(isCompletePlate),
    trendUniverse: (payload.trendUniverse ?? payload.baseUniverse ?? []).filter(isCompletePlate),
  };
}

async function buildEmotionSnapshot(limit: number): Promise<MarketEmotionSnapshot> {
  if ((await getMarketSourceInfo()).unavailable.includes('historical_pools')) {
    return { emotionSeries: [], intradayEmotion: await loadIntradayEmotion(),
      shortEmotion: await loadShortEmotion(limit), facts: ['历史股票池暂不可用，历史情绪分析暂停'] };
  }
  const [tradingDays, intradayEmotion, shortEmotion] = await Promise.all([
    loadTradingDays(FULL_EMOTION_DAYS),
    loadIntradayEmotion(),
    loadShortEmotion(limit),
  ]);
  const pools =
    tradingDays.length > 0
      ? await loadTopicPools(tradingDays)
      : {
          ztByDate: new Map<string, TopicStock[]>(),
          zbByDate: new Map<string, TopicStock[]>(),
          dtByDate: new Map<string, TopicStock[]>(),
        };

  const emotionDays = tradingDays.slice(-limit);
  const emotionSeries = emotionDays
    .map((day, index) => {
      const prev = index > 0 ? emotionDays[index - 1] : '';
      const zt = pools.ztByDate.get(day) || [];
      const geese = deriveGeese(prev ? pools.ztByDate.get(prev) || [] : [], zt, pools.zbByDate.get(day) || []);
      return emotionFromZt(day, zt, geese);
    })
    .filter((item): item is MarketEmotionPoint => item !== null);

  return {
    emotionSeries,
    intradayEmotion,
    shortEmotion,
    facts: emotionFacts(emotionSeries),
  };
}

export async function loadEmotionSnapshot(limit = FULL_EMOTION_DAYS): Promise<MarketEmotionSnapshot> {
  return buildEmotionSnapshot(limit);
}

/** 候选名单每日留痕（IDB，30 天）：跌出候选 = 近几日在榜、今日不在榜，消除幸存者偏差 */
type TrendCandidateSnapshot = { day: string; plates: Array<{ id: string; name: string }> };
const TREND_DROP_DAYS = 5;
function trendCandidateKey(day: string) {
  return `market:trendCandidates:${day}`;
}

async function recordTrendCandidates(day: string, topics: MarketTrendTopic[]): Promise<void> {
  if (typeof window === 'undefined' || !day || topics.length === 0) return;
  try {
    await indexedDBCache.set<TrendCandidateSnapshot>(
      trendCandidateKey(day),
      { day, plates: topics.map((topic) => ({ id: topic.id, name: topic.name })) },
      TTL.days(30)
    );
  } catch {
    // 留痕失败不影响主流程
  }
}

async function loadDroppedCandidates(
  day: string,
  topics: MarketTrendTopic[],
  priorDays: string[]
): Promise<Array<{ name: string; lastSeen: string }>> {
  if (typeof window === 'undefined' || !day) return [];
  const currentIds = new Set(topics.map((topic) => topic.id));
  const lastSeen = new Map<string, { name: string; lastSeen: string }>();
  for (const prior of priorDays) {
    try {
      const snapshot = await indexedDBCache.get<TrendCandidateSnapshot>(trendCandidateKey(prior));
      if (!snapshot) continue;
      snapshot.plates.forEach((plate) => {
        if (currentIds.has(plate.id)) return;
        lastSeen.set(plate.id, { name: plate.name, lastSeen: formatShortDate(prior) });
      });
    } catch {
      // 单日留痕读取失败跳过
    }
  }
  return [...lastSeen.values()];
}

export async function loadTrendSnapshot(): Promise<MarketTrendSnapshot> {
  await ensurePrivateStrategy();
  const [turnover, context] = await Promise.all([loadTurnover(), loadLatestMarketContext()]);
  const eventAddedCount = context.trendUniverse.filter((plate) => !context.baseUniverse.some((base) => base.code === plate.code)).length;
  const trendData = buildSectorTrendData(context.latestDay, context.trendUniverse, context.latestZt, context.surge);
  void recordTrendCandidates(context.latestDay, trendData.topics);
  const tradingDays = await loadTradingDays(FULL_EMOTION_DAYS);
  const priorDays = tradingDays.filter((day) => day !== context.latestDay).slice(-TREND_DROP_DAYS);
  const droppedBoards = await loadDroppedCandidates(context.latestDay, trendData.topics, priorDays);
  return {
    turnover,
    sectorTrend: {
      ...trendData,
      sampleStats: {
        baseCount: context.baseUniverse.length,
        eventAddedCount,
        finalCount: trendData.topics.length,
      },
      droppedBoards,
    },
    facts: trendFacts(turnover),
  };
}

export async function loadMainlineSnapshot(): Promise<MarketMainlineSnapshot> {
  if ((await getMarketSourceInfo()).unavailable.includes('historical_pools')) {
    return { mainlineLanes: [], relay: null, facts: ['历史股票池暂不可用，主线及接力分析暂停'] };
  }
  // 主线/反包评分依赖 private 策略段（后端下发）；不可用时以空数据降级
  await ensurePrivateStrategy();
  if (!isPrivateLoaded()) {
    return { mainlineLanes: [], relay: null, facts: DEFAULT_MARKET_SNAPSHOT.diagnostics.主线.facts };
  }
  // 接力/反包需要多日池历史：与 context 的最新日池共享缓存，历史日 8h 持久缓存
  const [context, relayDays, trending] = await Promise.all([
    loadLatestMarketContext(),
    loadTradingDays(FULL_EMOTION_DAYS),
    loadTrendingPlates(),
  ]);
  const relayPools =
    relayDays.length > 0
      ? await loadTopicPools(relayDays)
      : {
          ztByDate: new Map<string, TopicStock[]>(),
          zbByDate: new Map<string, TopicStock[]>(),
          dtByDate: new Map<string, TopicStock[]>(),
        };
  const mainlineLanes = buildMainlineLanes({
    plates: context.trendUniverse,
    ztPool: context.latestZt,
    topicFunds: buildTopicFundMap(context.latestZt, context.latestZb, context.latestDt),
    historyZtByDate: relayPools.ztByDate,
    latestDay: context.latestDay,
    trendingPlates: trending,
  });
  const recentLimitUpUniverse = buildRecentLimitUpUniverse(relayDays, context.latestDay, relayPools.ztByDate);
  const latestRelayDay = relayDays[relayDays.length - 1];
  const previousRelayDay = relayDays[relayDays.length - 2];
  // 一笔行情同时用于派生近6日涨停异动池和观察池状态，复用既有 20s 缓存。
  const quoteCodes = new Set([
    ...recentLimitUpUniverse.map((stock) => stock.code),
    ...context.surge.map((stock) => stock.code),
    ...(latestRelayDay ? relayPools.zbByDate.get(latestRelayDay) || [] : []).map((stock) => stock.code),
    ...(previousRelayDay ? relayPools.zbByDate.get(previousRelayDay) || [] : []).map((stock) => stock.code),
  ]);
  const quotes = await loadQuoteList(Array.from(quoteCodes));
  const { repairPct } = getStrategy().rebound;
  const recentLimitUpSurge = recentLimitUpUniverse.filter((stock) => {
    const quote = quotes.get(normalizeCode(stock.code));
    return quote?.change != null && quote.change >= repairPct;
  });
  const relay = buildRelaySnapshot({
    days: relayDays,
    ztByDate: relayPools.ztByDate,
    zbByDate: relayPools.zbByDate,
    surge: [...context.surge, ...recentLimitUpSurge],
    mainlineThemes: new Set(mainlineLanes.map((lane) => lane.name)),
  });
  // 观察池使用同一笔实时行情补全状态；昨日炸板股需先确认当日修复。
  if (relay && relay.reboundWatching.length > 0) {
    relay.reboundWatching = relay.reboundWatching
      .map((stock) => {
        const quote = quotes.get(normalizeCode(stock.code));
        return quote ? { ...stock, change: quote.change, price: quote.price } : stock;
      })
      .filter((stock) => !stock.brokeYesterday || (stock.change != null && stock.change >= repairPct))
      .sort((a, b) => b.score - a.score || a.gapDays - b.gapDays)
      .slice(0, getStrategy().rebound.watchLimit);
  }
  return {
    mainlineLanes,
    relay,
    facts: mainlineFacts(mainlineLanes),
  };
}

export async function loadPayoffSnapshot(): Promise<MarketPayoffSnapshot> {
  const tradingDays = await loadTradingDays(FULL_EMOTION_DAYS);
  const [strong, hot, bigface] = await Promise.all([
    loadStrong(),
    loadHot(),
    loadBigFace(tradingDays),
  ]);
  const payoffLists = { strong, hot, bigface };
  return {
    payoffLists,
    facts: payoffFacts(payoffLists, (await getMarketSourceInfo()).unavailable.includes('payoff_hot')),
  };
}

export async function loadMarketSummarySnapshot(): Promise<MarketSnapshot> {
  const historyAvailable = !(await getMarketSourceInfo()).unavailable.includes('historical_pools');
  const snapshot: MarketSnapshot = JSON.parse(JSON.stringify(DEFAULT_MARKET_SNAPSHOT));
  const tradingDays = await loadTradingDays(FULL_EMOTION_DAYS);
  const emotionDays = tradingDays.slice(-DEFAULT_EMOTION_DAYS);
  const [turnoverResult, contextResult, strongResult, hotResult, bigFaceResult, trendingResult] = await Promise.allSettled([
    loadTurnover(),
    loadLatestMarketContext(),
    loadStrong(),
    loadHot(),
    loadBigFace(tradingDays),
    loadTrendingPlates(),
  ]);

  const turnover = settledValue(turnoverResult, null);
  if (turnover) {
    snapshot.turnover = turnover;
    snapshot.diagnostics.趋势.facts = trendFacts(turnover);
  }

  const context = settledValue(contextResult, null);
  const strategyReady = await ensurePrivateStrategy();
  if (context) {
    const latestEmotion = historyAvailable ? emotionFromZt(
      context.latestDay,
      context.latestZt,
      deriveGeese([], context.latestZt, context.pools.zbByDate.get(context.latestDay) || [])
    ) : null;
    snapshot.diagnostics.情绪.facts = historyAvailable ? emotionFacts(latestEmotion ? [latestEmotion] : []) : ['历史股票池暂不可用，历史情绪分析暂停'];

    // 持续性回看池：context 只带最新日，历史日单独拉（8h 持久缓存，增量成本低）
    const histDays = tradingDays
      .filter((day) => day !== context.latestDay)
      .slice(-getStrategy().mainline.persistDays);
    const histPools = historyAvailable && histDays.length > 0 ? await loadTopicPools(histDays) : emptyPools();
    const lanes = strategyReady && historyAvailable
      ? buildMainlineLanes({
          plates: context.trendUniverse,
          ztPool: context.latestZt,
          topicFunds: buildTopicFundMap(context.latestZt, context.latestZb, context.latestDt),
          historyZtByDate: histPools.ztByDate,
          latestDay: context.latestDay,
          trendingPlates: settledValue(trendingResult, []),
        })
      : [];
    snapshot.mainlineLanes = lanes;
    snapshot.diagnostics.主线.facts = historyAvailable ? mainlineFacts(lanes) : ['历史股票池暂不可用，主线及接力分析暂停'];
  }

  snapshot.payoffLists.strong = settledValue(strongResult, []);
  snapshot.payoffLists.hot = settledValue(hotResult, []);
  snapshot.payoffLists.bigface = settledValue(bigFaceResult, []);
  snapshot.diagnostics.赚钱效应.facts = payoffFacts(snapshot.payoffLists, (await getMarketSourceInfo()).unavailable.includes('payoff_hot'));

  if (emotionDays.length === 0) {
    snapshot.diagnostics.情绪.facts = DEFAULT_MARKET_SNAPSHOT.diagnostics.情绪.facts;
  }

  return snapshot;
}

export async function loadMarketSnapshot(): Promise<MarketSnapshot> {
  if (inflight) return inflight;
  inflight = buildSnapshot().finally(() => {
    inflight = null;
  });
  return inflight;
}

async function buildSnapshot(): Promise<MarketSnapshot> {
  const historyAvailable = !(await getMarketSourceInfo()).unavailable.includes('historical_pools');
  const snapshot: MarketSnapshot = JSON.parse(JSON.stringify(DEFAULT_MARKET_SNAPSHOT));
  const tradingDays = await loadTradingDays(FULL_EMOTION_DAYS);
  const latestDay = tradingDays[tradingDays.length - 1] || '';
  const emotionDays = tradingDays.slice(-DEFAULT_EMOTION_DAYS);
  const historyDays = latestDay ? tradingDays.filter((day) => day !== latestDay) : tradingDays;

  const [turnoverResult, contextResult, historyPoolResult, strongResult, hotResult, bigFaceResult, trendingResult] = await Promise.allSettled([
    loadTurnover(),
    loadLatestMarketContext(),
    historyAvailable && historyDays.length > 0
      ? loadTopicPools(historyDays)
      : Promise.resolve({
          ztByDate: new Map<string, TopicStock[]>(),
          zbByDate: new Map<string, TopicStock[]>(),
          dtByDate: new Map<string, TopicStock[]>(),
        }),
    loadStrong(),
    loadHot(),
    loadBigFace(tradingDays),
    loadTrendingPlates(),
  ]);

  const turnover = settledValue(turnoverResult, null);
  const strategyReady = await ensurePrivateStrategy();
  if (turnover) {
    snapshot.turnover = turnover;
    snapshot.diagnostics.趋势.facts = [
      `当前成交 ${turnover.currentText}`,
      `预估全天 ${turnover.predictText}`,
      `较昨日 ${turnover.changeText}`,
    ];
  }

  const context = settledValue(contextResult, null);
  const historyPools = settledValue(historyPoolResult, {
    ztByDate: new Map<string, TopicStock[]>(),
    zbByDate: new Map<string, TopicStock[]>(),
    dtByDate: new Map<string, TopicStock[]>(),
  });
  const latestPools = context?.pools || emptyPools();
  const pools: TopicPoolsBundle = {
    ztByDate: new Map([...historyPools.ztByDate.entries(), ...latestPools.ztByDate.entries()]),
    zbByDate: new Map([...historyPools.zbByDate.entries(), ...latestPools.zbByDate.entries()]),
    dtByDate: new Map([...historyPools.dtByDate.entries(), ...latestPools.dtByDate.entries()]),
  };
  const plateUniverse = context?.baseUniverse || [];
  const latestZt = context?.latestZt || [];
  const latestZb = context?.latestZb || [];
  const latestDt = context?.latestDt || [];
  const surge = context?.surge || [];
  const plates = context?.trendUniverse || plateUniverse;
  const trendUniverse = plates;

  snapshot.emotionSeries = (historyAvailable ? emotionDays : [])
    .map((day, index) => {
      const prev = index > 0 ? emotionDays[index - 1] : '';
      const zt = pools.ztByDate.get(day) || [];
      const geese = deriveGeese(prev ? pools.ztByDate.get(prev) || [] : [], zt, pools.zbByDate.get(day) || []);
      return emotionFromZt(day, zt, geese);
    })
    .filter((item): item is MarketEmotionPoint => item !== null);
  snapshot.diagnostics.情绪.facts = historyAvailable ? emotionFacts(snapshot.emotionSeries) : ['历史股票池暂不可用，历史情绪分析暂停'];

  if (!strategyReady) {
    snapshot.diagnostics.趋势.facts = trendFacts(turnover);
    return snapshot;
  }

  const lanes = historyAvailable ? buildMainlineLanes({
    plates,
    ztPool: latestZt,
    topicFunds: buildTopicFundMap(latestZt, latestZb, latestDt),
    historyZtByDate: pools.ztByDate,
    latestDay,
    trendingPlates: settledValue(trendingResult, []),
  }) : [];
  snapshot.mainlineLanes = lanes;
  snapshot.diagnostics.主线.facts = historyAvailable ? mainlineFacts(lanes) : ['历史股票池暂不可用，主线及接力分析暂停'];

  snapshot.relay = historyAvailable ? buildRelaySnapshot({
    days: tradingDays,
    ztByDate: pools.ztByDate,
    zbByDate: pools.zbByDate,
    surge,
    mainlineThemes: new Set(lanes.map((lane) => lane.name)),
  }) : null;

  snapshot.payoffLists.strong = settledValue(strongResult, []);
  snapshot.payoffLists.hot = settledValue(hotResult, []);
  snapshot.payoffLists.bigface = settledValue(bigFaceResult, []);
  snapshot.diagnostics.赚钱效应.facts = payoffFacts(snapshot.payoffLists, (await getMarketSourceInfo()).unavailable.includes('payoff_hot'));

  const trendData = buildSectorTrendData(latestDay, trendUniverse, latestZt, surge);
  const eventAddedCount = trendUniverse.filter((plate) => !plateUniverse.some((base) => base.code === plate.code)).length;
  snapshot.sectorTrend = {
    ...trendData,
    sampleStats: {
      baseCount: plateUniverse.length,
      eventAddedCount,
      finalCount: trendData.topics.length,
    },
  };
  snapshot.diagnostics.趋势.facts = trendFacts(turnover);
  return snapshot;
}
