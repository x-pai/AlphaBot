import { buildMarketCacheKey, cached, getMarketSourceInfo, TTL } from './client';
import { formatAmount, formatAmountChange, formatChange, isAfterMarketClose, normalizeCode, yyyymmdd } from './format';
import { filterTrendPlateUniverse } from './plateFilter';
import {
  fetchPayoffList,
  fetchLatestMarketContext,
  fetchFundflowBatch,
  fetchPlateIndexHistory,
  fetchPlateMembers,
  fetchPoolsBatch,
  fetchQuoteSnapshots,
  fetchSurgeDomain,
  fetchTurnoverDomain,
  fetchTrendingPlates,
  fetchUniverseDomain,
  FUNDFLOW_MAX_DAYS,
} from './domain';
import type {
  IntradayEmotionSnapshot,
  MarketPayoffItem,
  ShortEmotionSnapshot,
  TurnoverMinutePoint,
  TurnoverSnapshot,
} from './types';
import { api } from '../api';

const LIST_LIMIT = 8;

export type PlateFlow = {
  /** 板块 ID（领域对象，趋势轨迹的成分/资金流明细均按此 ID 取数） */
  code: string;
  name: string;
  change: number;
  netFlow: number;
  ztCount: number;
  upCount: number;
  downCount: number;
  flatCount: number;
};

/** 缺少资金/广度的板块不参与强度评分，不能补零混入排序。 */
export function isCompletePlate(plate: Awaited<ReturnType<typeof fetchUniverseDomain>>[number]): plate is PlateFlow {
  return [plate.change, plate.netFlow, plate.ztCount, plate.upCount, plate.downCount, plate.flatCount]
    .every((value) => typeof value === 'number' && Number.isFinite(value));
}

export type TopicStock = {
  name: string;
  code: string;
  /** 主概念名（领域归一化的首个题材标签），参与展示与同题材匹配 */
  reason: string;
  /** 概念标签（领域归一化），参与板块逻辑；缺省时回退 reason */
  concepts?: string[];
  lbc: number;
  time: number | null;
  type: 'zt' | 'zb' | 'dt';
  fund: number | null;
  price: number | null;
  turnoverRate?: number;
  /** 当日炸板次数，断板反包/接力评分用 */
  zbc?: number;
  /** 当日首次炸板时刻（unix 秒），异动反包洗盘时长用 */
  firstBreak?: number;
  /** 当日最后一次回封时刻（unix 秒） */
  lastSealTs?: number;
};

export type PlateMember = {
  code: string;
  name: string;
  price: number | null;
  change: number | null;
  amount: number | null;
  netFlow: number | null;
  turnoverRate: number | null;
};

export type SurgeLimitStock = {
  code: string;
  name: string;
  plates: string[];
  analysis?: string;
};

export type ConceptIndexStock = {
  code: string;
  name: string;
  /** 题材标签（领域归一化） */
  plates: string[];
};

export async function loadTradingDays(limit = 20): Promise<string[]> {
  try {
    const today = new Date();
    const endDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    const response = await cached<{ success: boolean; data?: { days?: string[] }; error?: string }>(
      buildMarketCacheKey('loadTradingDays', { limit, endDate }),
      TTL.hours(24),
      true,
      async () => {
        const result = await api.get<{ success: boolean; data?: { days?: string[] }; error?: string }>(
          `/market/trading-calendar?limit=${limit}&end_date=${endDate}`
        );
        return result.data;
      },
    );
    if (!response.success || !response.data?.days) {
      return [];
    }
    return response.data.days.map((day) => day.replace(/-/g, '')).filter((day) => /^\d{8}$/.test(day));
  } catch (error) {
    console.warn('[market] loadTradingDays failed', error);
    return [];
  }
}

async function latestTradeDayAnchor() {
  const today = yyyymmdd();
  const tradingDays = await loadTradingDays(1);
  const anchor = tradingDays[tradingDays.length - 1] || today;
  return {
    anchor,
    closed: anchor !== today || isAfterMarketClose(),
  };
}

export async function loadTurnover(): Promise<TurnoverSnapshot | null> {
  try {
    const data = await cached<{ current: number | null; predict: number | null; previous: number | null; change: number | null; points: TurnoverMinutePoint[] } | null>(
      buildMarketCacheKey('loadTurnover', { source: 'backend' }),
      TTL.seconds(15),
      false,
      async () => await fetchTurnoverDomain(),
    );
    if (!data || data.current == null) return null;
    const current = data.current;
    const previous = data.previous;
    const predict = data.predict;
    const change = data.change;
    const points = data.points;
    return {
      current,
      predict,
      previous,
      change,
      currentText: formatAmount(current),
      predictText: formatAmount(predict),
      previousText: formatAmount(previous),
      changeText: formatAmountChange(change),
      points,
      emotion: null,
    };
  } catch {
    return null;
  }
}

export async function loadIntradayEmotion(): Promise<IntradayEmotionSnapshot | null> {
  try {
    const response = await cached<{
      success: boolean;
      data?: {
        positive_current?: number | null;
        negative_current?: number | null;
        index_current?: number | null;
        points?: Array<{
          time: string;
          positive?: number | null;
          negative?: number | null;
          index?: number | null;
        }>;
      };
      error?: string;
    }>(
      buildMarketCacheKey('loadIntradayEmotion'),
      TTL.seconds(15),
      false,
      async () => {
        const result = await api.get<{
          success: boolean;
          data?: {
            positive_current?: number | null;
            negative_current?: number | null;
            index_current?: number | null;
            points?: Array<{
              time: string;
              positive?: number | null;
              negative?: number | null;
              index?: number | null;
            }>;
          };
          error?: string;
        }>(
          '/market/emotion/intraday'
        );
        return result.data;
      },
    );
    if (!response.success || !response.data) {
      return null;
    }
    return {
      positiveCurrent: response.data.positive_current ?? null,
      negativeCurrent: response.data.negative_current ?? null,
      indexCurrent: response.data.index_current ?? null,
      points: (response.data.points || []).map((point) => ({
        time: point.time || '',
        positive: point.positive ?? null,
        negative: point.negative ?? null,
        index: point.index ?? null,
      })),
    };
  } catch (error) {
    console.warn('[market] loadIntradayEmotion failed', error);
    return null;
  }
}

export async function loadShortEmotion(days = 5): Promise<ShortEmotionSnapshot | null> {
  try {
    const { anchor, closed } = await latestTradeDayAnchor();
    const response = await cached<{
      success: boolean;
      data?: {
        latest_value?: number | null;
        latest_turnover?: number | null;
        zone?: string;
        days?: Array<{
          date: string;
          points: Array<{
            time: string;
            value: number;
            turnover?: number | null;
          }>;
        }>;
      };
      error?: string;
    }>(
      buildMarketCacheKey('loadShortEmotion', { days, anchor }),
      closed ? TTL.days(7) : TTL.minutes(2),
      true,
      async () => {
        const result = await api.get<{
          success: boolean;
          data?: {
            latest_value?: number | null;
            latest_turnover?: number | null;
            zone?: string;
            days?: Array<{
              date: string;
              points: Array<{
                time: string;
                value: number;
                turnover?: number | null;
              }>;
            }>;
          };
          error?: string;
        }>(
          `/market/emotion/short?days=${days}`
        );
        return result.data;
      },
    );
    if (!response.success || !response.data) {
      return null;
    }
    return {
      latestValue: response.data.latest_value ?? null,
      latestTurnover: response.data.latest_turnover ?? null,
      zone: response.data.zone || '--',
      days: (response.data.days || []).map((day) => ({
        date: day.date || '',
        points: (day.points || []).map((point) => ({
          time: point.time || '',
          value: point.value,
          turnover: point.turnover ?? null,
        })),
      })),
    };
  } catch (error) {
    console.warn('[market] loadShortEmotion failed', error);
    return null;
  }
}

// ── 板块宇宙（xgb plate/rank + plate/data，两笔请求覆盖全量） ──

export async function loadPlateUniverse(): Promise<PlateFlow[]> {
  try {
    const { anchor, closed } = await latestTradeDayAnchor();
    const plates = await cached<PlateFlow[]>(
      buildMarketCacheKey('loadPlateUniverse', { anchor, source: 'backend' }),
      closed ? TTL.days(7) : TTL.minutes(5),
      false,
      async () => (await fetchUniverseDomain()).filter(isCompletePlate),
    );
    return filterTrendPlateUniverse(plates);
  } catch (error) {
    console.warn('[market] loadPlateUniverse failed', error);
    return [];
  }
}

// ── 涨停 / 炸板 / 跌停池（xgb pool/detail，date 支持历史回看） ──

function hyphenDate(yyyymmdd: string): string {
  return /^\d{8}$/.test(yyyymmdd)
    ? `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}`
    : yyyymmdd;
}

export async function loadTopicPools(days: string[]): Promise<{
  ztByDate: Map<string, TopicStock[]>;
  zbByDate: Map<string, TopicStock[]>;
  dtByDate: Map<string, TopicStock[]>;
}> {
  const ztByDate = new Map<string, TopicStock[]>();
  const zbByDate = new Map<string, TopicStock[]>();
  const dtByDate = new Map<string, TopicStock[]>();
  if (days.length === 0) return { ztByDate, zbByDate, dtByDate };

  const normalizedDays = Array.from(new Set(days.map((day) => day.replace(/-/g, '')).filter((day) => /^\d{8}$/.test(day))));
  if (normalizedDays.length === 0) return { ztByDate, zbByDate, dtByDate };

  const source = await getMarketSourceInfo();
  if (source.unavailable.includes('historical_pools')) {
    const { anchor } = await latestTradeDayAnchor();
    if (normalizedDays.some(day => day !== anchor)) {
      throw new Error('历史股票池暂不可用：已停止自动全市场回补');
    }
  }
  const latest = normalizedDays[normalizedDays.length - 1];
  const historyDays = normalizedDays.slice(0, -1);
  const [historyBatch, latestBatch] = await Promise.all([
    historyDays.length > 0
      ? cached<{ ztByDate: Record<string, TopicStock[]>; zbByDate: Record<string, TopicStock[]>; dtByDate: Record<string, TopicStock[]> }>(
          buildMarketCacheKey('loadTopicPools:history', { days: historyDays.join(','), kinds: 'zt,zb', source: 'backend' }),
          TTL.days(7),
          true,
          async () => await fetchPoolsBatch(historyDays.map(hyphenDate), ['zt', 'zb']),
        )
      : Promise.resolve({ ztByDate: {}, zbByDate: {}, dtByDate: {} }),
    cached<{ ztByDate: Record<string, TopicStock[]>; zbByDate: Record<string, TopicStock[]>; dtByDate: Record<string, TopicStock[]> }>(
      buildMarketCacheKey('loadTopicPools:latest', { day: latest, kinds: 'zt,zb,dt', source: 'backend' }),
      TTL.seconds(20),
      true,
      async () => await fetchPoolsBatch([hyphenDate(latest)], ['zt', 'zb', 'dt']),
    ),
  ]);

  const assign = (target: Map<string, TopicStock[]>, source: Record<string, TopicStock[]>) => {
    Object.entries(source).forEach(([day, items]) => {
      target.set(
        day,
        (items || []).filter((item) => item.code && item.code !== '000000')
      );
    });
  };

  assign(ztByDate, historyBatch.ztByDate);
  assign(zbByDate, historyBatch.zbByDate);
  assign(dtByDate, historyBatch.dtByDate);
  assign(ztByDate, latestBatch.ztByDate);
  assign(zbByDate, latestBatch.zbByDate);
  assign(dtByDate, latestBatch.dtByDate);
  return { ztByDate, zbByDate, dtByDate };
}

export async function loadPlateMembers(code: string): Promise<PlateMember[]> {
  try {
    const { anchor, closed } = await latestTradeDayAnchor();
    return await cached<PlateMember[]>(
      buildMarketCacheKey('loadPlateMembers', { code, anchor, source: 'backend' }),
      closed ? TTL.days(7) : TTL.minutes(2),
      false,
      async () => {
        const members = await fetchPlateMembers(code);
        return members.map((member) => ({ ...member, code: normalizeCode(member.code) || member.code }));
      },
    );
  } catch {
    return [];
  }
}

export type PlateDayBar = {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  amount: number;
};

export async function loadPlateDayKline(code: string, limit = 12): Promise<PlateDayBar[]> {
  try {
    const { anchor, closed } = await latestTradeDayAnchor();
    return await cached<PlateDayBar[]>(
      buildMarketCacheKey('loadPlateDayKline', { code, limit, anchor, source: 'backend' }),
      closed ? TTL.days(7) : TTL.minutes(5),
      false,
      async () => {
        // 多取一根算首日涨幅；接口返回新日期在前，先转升序
        const bars = (await fetchPlateIndexHistory(code, limit + 1)).sort((a, b) => a.date.localeCompare(b.date));
        return bars.slice(1).map((bar, index) => {
          const prev = bars[index];
          const pct = prev.close > 0 ? (bar.close / prev.close - 1) * 100 : 0;
          return {
            date: bar.date,
            open: bar.open,
            pct,
            close: bar.close,
            high: bar.high,
            low: bar.low,
            amount: 0,
          };
        });
      }
    );
  } catch (error) {
    console.warn('[market] loadPlateDayKline failed', { code, error });
    return [];
  }
}

// ── 板块资金流历史（plate_set 成分 + ddc fundflow/batch 按日聚合） ──

export type PlateFlowHistoryPoint = {
  date: string;
  mainNetInflow: number;
  mainNetInflowRatio: number;
  superLargeNetInflow: number;
  superLargeNetInflowRatio: number;
  largeNetInflow: number;
  largeNetInflowRatio: number;
  midNetInflow: number;
  midNetInflowRatio: number;
  smallNetInflow: number;
  smallNetInflowRatio: number;
};

type FundflowDayAggregate = {
  main: number;
  mainVolume: number;
  superLarge: number;
  superLargeVolume: number;
  large: number;
  largeVolume: number;
  mid: number;
  midVolume: number;
  small: number;
  smallVolume: number;
};

function emptyAggregate(): FundflowDayAggregate {
  return {
    main: 0,
    mainVolume: 0,
    superLarge: 0,
    superLargeVolume: 0,
    large: 0,
    largeVolume: 0,
    mid: 0,
    midVolume: 0,
    small: 0,
    smallVolume: 0,
  };
}

/** 净流入占比 = 净额 / 该类进出总成交 × 100 */
function inflowRatio(net: number, volume: number): number {
  return volume > 0 ? (net / volume) * 100 : 0;
}

/**
 * 板块资金流历史 = 成分股逐日主力净流入求和（自建口径，与外部终端口径
 * 官方板块口径有定义差异，但跨板块同口径可比）。服务端 day_count 上限 10。
 * 缓存按最新交易日锚定：盘中窗口仍在变化走短 TTL；收盘后/非交易日窗口不可变，
 * 长缓存到下一交易日（换日 key 自然失效），历史不再跟随实时节奏重拉。
 */
export async function loadPlateFlowHistory(code: string, limit = 10): Promise<PlateFlowHistoryPoint[]> {
  const days = Math.max(1, Math.min(limit, FUNDFLOW_MAX_DAYS));
  try {
    const tradingDays = await loadTradingDays(1);
    const today = yyyymmdd();
    const anchor = tradingDays[tradingDays.length - 1] || today;
    const closed = anchor !== today || isAfterMarketClose();
    return await cached<PlateFlowHistoryPoint[]>(
      buildMarketCacheKey('loadPlateFlowHistory', { code, days, anchor }),
      closed ? TTL.hours(48) : TTL.minutes(3),
      false,
      async () => {
        const members = await loadPlateMembers(code);
        const codes = members.map((member) => member.code);
        if (codes.length === 0) return [];
        const flows = await fetchFundflowBatch(codes, days);
        const byDate = new Map<string, FundflowDayAggregate>();
        flows.forEach((rows) => {
          rows.forEach((row) => {
            const acc = byDate.get(row.date) || emptyAggregate();
            acc.main += row.netInflow;
            acc.mainVolume += row.mainIn + row.mainOut;
            acc.superLarge += row.netSuper;
            acc.superLargeVolume += row.superIn + row.superOut;
            acc.large += row.netBig;
            acc.largeVolume += row.bigIn + row.bigOut;
            acc.mid += row.netMedium;
            acc.midVolume += row.mediumIn + row.mediumOut;
            acc.small += row.netSmall;
            acc.smallVolume += row.smallIn + row.smallOut;
            byDate.set(row.date, acc);
          });
        });
        // fundflow 单位万元，转亿
        return Array.from(byDate.entries())
          .sort(([left], [right]) => left.localeCompare(right))
          .slice(-days)
          .map(([date, acc]) => ({
            date: date.replace(/-/g, ''),
            mainNetInflow: acc.main / 1e4,
            mainNetInflowRatio: inflowRatio(acc.main, acc.mainVolume),
            superLargeNetInflow: acc.superLarge / 1e4,
            superLargeNetInflowRatio: inflowRatio(acc.superLarge, acc.superLargeVolume),
            largeNetInflow: acc.large / 1e4,
            largeNetInflowRatio: inflowRatio(acc.large, acc.largeVolume),
            midNetInflow: acc.mid / 1e4,
            midNetInflowRatio: inflowRatio(acc.mid, acc.midVolume),
            smallNetInflow: acc.small / 1e4,
            smallNetInflowRatio: inflowRatio(acc.small, acc.smallVolume),
          }));
      },
    );
  } catch (error) {
    console.warn('[market] loadPlateFlowHistory failed', { code, error });
    return [];
  }
}

export async function loadSurgeLimitUp(): Promise<SurgeLimitStock[]> {
  try {
    const { anchor, closed } = await latestTradeDayAnchor();
    return await cached<SurgeLimitStock[]>(
      buildMarketCacheKey('loadSurgeLimitUp', { anchor, source: 'backend' }),
      closed ? TTL.days(7) : TTL.seconds(45),
      false,
      async () => await fetchSurgeDomain(),
    );
  } catch {
    return [];
  }
}

export async function loadConceptIndexPool(): Promise<ConceptIndexStock[]> {
  try {
    const { anchor, closed } = await latestTradeDayAnchor();
    return await cached<ConceptIndexStock[]>(
      buildMarketCacheKey('loadConceptIndexPool', { anchor, source: 'backend' }),
      closed ? TTL.days(7) : TTL.seconds(45),
      false,
      async () =>
        (await fetchLatestMarketContext()).latestZt.map((item) => ({
          code: item.code,
          name: item.name,
          plates: item.concepts ?? [],
        })),
    );
  } catch {
    return [];
  }
}

export function buildConceptIndex(stocks: ConceptIndexStock[]): Map<string, string[]> {
  const index = new Map<string, string[]>();
  stocks.forEach((stock) => {
    if (!stock.code || stock.plates.length === 0) return;
    index.set(stock.code, Array.from(new Set(stock.plates)));
  });
  return index;
}

// ── 催化层：xgb 趋势板块推荐（编辑性内容，仅作主线卡片展示与加分，不参与事实数据） ──

export type TrendingPlate = {
  /** xgb plate_id（字符串），与板块宇宙 code 同源可直接匹配 */
  plateId: string;
  name: string;
  description: string;
};

export async function loadTrendingPlates(): Promise<TrendingPlate[]> {
  try {
    const { anchor, closed } = await latestTradeDayAnchor();
    return await cached<TrendingPlate[]>(
      buildMarketCacheKey('loadTrendingPlates', { anchor }),
      closed ? TTL.days(7) : TTL.minutes(15),
      false,
      async () => {
        const items = await fetchTrendingPlates();
        return items.map((item) => ({
          plateId: String(item.plateId ?? ''),
          name: String(item.name || ''),
          description: String(item.description || '').trim(),
        }));
      },
    );
  } catch (error) {
    console.warn('[market] loadTrendingPlates failed', error);
    return [];
  }
}

const NON_PLATE_CONCEPTS = new Set(['其他', 'ST股', '未分类']);

/** 逻辑用概念标签：优先 xgb concepts，缺省回退 reason（主概念名），无效名返回空数组 */
export function stockConcepts(stock: Pick<TopicStock, 'concepts' | 'reason'>): string[] {
  if (stock.concepts && stock.concepts.length > 0) return stock.concepts;
  const reason = stock.reason?.trim();
  if (!reason || NON_PLATE_CONCEPTS.has(reason)) return [];
  return [reason];
}

export type QuoteSnapshot = { name: string; price: number | null; change: number | null };

/** 批量实时报价（xgb stock/data），用于观察池盘中排序 */
export async function loadQuoteList(codes: string[]): Promise<Map<string, QuoteSnapshot>> {
  try {
    return await cached<Map<string, QuoteSnapshot>>(
      buildMarketCacheKey('loadQuoteList', { codes: codes.join(','), source: 'backend' }),
      TTL.seconds(20),
      false,
      async () => {
        const data = await fetchQuoteSnapshots(codes);
        const quotes = new Map<string, QuoteSnapshot>();
        codes.forEach((code) => {
          const quote = data[normalizeCode(code)];
          if (!quote) return;
          quotes.set(normalizeCode(code), {
            name: quote.name || '',
            price: typeof quote.price === 'number' ? quote.price : null,
            change: typeof quote.change === 'number' ? quote.change : null,
          });
        });
        return quotes;
      },
    );
  } catch {
    return new Map();
  }
}

export async function loadStrong(): Promise<MarketPayoffItem[]> {
  try {
    const { anchor, closed } = await latestTradeDayAnchor();
    return await cached<MarketPayoffItem[]>(
      buildMarketCacheKey('loadStrong', { anchor, source: 'backend' }),
      closed ? TTL.days(7) : TTL.minutes(2),
      true,
      async () => {
        const items = await fetchPayoffList<{ name: string; change: number | null; plate: string; days: number; boards: number }>('strong');
        return items
      .map((item) => {
        const change = item.change;
        const plate = item.plate || '';
        const days = item.days || 0;
        const boards = item.boards || 0;
        return {
          name: item.name || '--',
          value: formatChange(change),
          note: [plate, `${days}天${boards}板`].filter(Boolean).join(' / '),
          tone: (change == null ? 'normal' : change >= 0 ? 'up' : 'down') as 'up' | 'down' | 'normal',
          change,
        };
      })
        .sort((a, b) => (b.change ?? -Infinity) - (a.change ?? -Infinity))
        .slice(0, LIST_LIMIT)
        .map(({ change: _change, ...item }) => item);
      },
    );
  } catch {
    return [];
  }
}

export async function loadHot(): Promise<MarketPayoffItem[]> {
  if ((await getMarketSourceInfo()).unavailable.includes('payoff_hot')) return [];
  try {
    const { anchor, closed } = await latestTradeDayAnchor();
    return await cached<MarketPayoffItem[]>(
      buildMarketCacheKey('loadHot', { anchor, source: 'backend' }),
      closed ? TTL.days(7) : TTL.minutes(2),
      true,
      async () => {
        const items = await fetchPayoffList<{ name: string; change: number | null; heat: number | null; rank?: number | null; tag: string }>('hot');
        return items.slice(0, LIST_LIMIT).map((item) => {
          const change = item.change;
          const hotRate = item.rank != null ? `第 ${item.rank} 名` : item.heat != null ? `${item.heat.toFixed(1)}万热度` : '热度不可用';
          const tag = item.tag || '';
          return {
            name: item.name || '--',
            value: formatChange(change),
            note: tag ? `${hotRate} / ${tag}` : hotRate,
            tone: (change == null ? 'normal' : change >= 0 ? 'up' : 'down') as 'up' | 'down' | 'normal',
          };
        });
      },
    );
  } catch {
    return [];
  }
}

export async function loadBigFace(days: string[]): Promise<MarketPayoffItem[]> {
  const { anchor, closed } = await latestTradeDayAnchor();
  const source = await getMarketSourceInfo();
  const candidates = source.unavailable.includes('historical_payoff')
    ? [anchor] : days.length > 0 ? days.slice(-3).reverse() : [yyyymmdd()];
  for (const [index, dateStr] of candidates.entries()) {
    const isLatestCandidate = index === 0 && dateStr === anchor;
    try {
      const items = await cached<
        Array<{ name: string; change: number | null; maxDrawdown: number; industryBlock: string }>
      >(
        buildMarketCacheKey('loadBigFace', { date: dateStr, latest: isLatestCandidate }),
        isLatestCandidate && !closed ? TTL.minutes(2) : TTL.days(7),
        true,
        async () => await fetchPayoffList<{ name: string; change: number | null; maxDrawdown: number; industryBlock: string }>('drawdown', { date: dateStr }),
      );
      if (items.length === 0) continue;
      return items
        .map((item) => {
          const change = item.change;
          const drawdown = item.maxDrawdown;
          return {
            name: item.name || '--',
            value: formatChange(change),
            note: `回撤 ${drawdown.toFixed(2)}%${item.industryBlock ? ` / ${item.industryBlock}` : ''}`,
            tone: (change == null ? 'normal' : change >= 0 ? 'up' : 'down') as 'up' | 'down' | 'normal',
            max_drawdown: drawdown,
          };
        })
        .sort((a, b) => a.max_drawdown - b.max_drawdown)
        .slice(0, LIST_LIMIT)
        .map(({ max_drawdown: _drawdown, ...item }) => item);
    } catch {
      // try older trading day
    }
  }
  return [];
}
