/**
 * 主线板块打分与选卡。
 *
 * 旧口径（涨停家数/高度 + 板块绝对净流入）是单日强度快照，两个硬伤：
 * 板块净流入未归一（大体量板块天然占优）、缺多日持续性（主线是"反复活跃"而非单日脉冲）。
 * 新口径分维度独立设上限，避免单一维度主导排序，总分约 0~140：
 *
 * - 攻击性 ≤30：当日涨停家数，主概念 ×1、次概念 ×0.5（防一股多概念重复供分），10 只封顶
 * - 梯队    ≤32：最高板 ×4 + 加权连板高度和 ×1
 * - 空间地位 ≤15：题材含市场最高板 +15、含次高板 +6（情绪核心所在题材）
 * - 资金    ≤25：板块净流入与户均净流入的组内百分位（消除板块体量差）
 * - 持续性  ≤25：近 5 个交易日（不含当日）题材在榜天数 ×3 + 累计涨停 ×0.5
 * - 质量    ≤10：早盘(≤10:00)封板占比 ×8 + 封单合计(封顶 20 亿) ×0.1 − 炸板次数(封顶 6)
 * - 催化    +12：命中 xgb 趋势板块推荐（tab/recommend?module=trending_plates）
 * 全部参数见 strategy.ts 的 mainline 节点。
 */
import { stockConcepts, type PlateFlow, type TopicStock, type TrendingPlate } from './api';
import { percentileRank } from './flowStrength';
import { formatPlateFlow, matchPlate, normalizeCode, normalizePlateName } from './format';
import { getStrategy } from './strategy';
import type { MarketMainlineLane, MarketMainlineStock } from './types';

function boardHeight(stock: TopicStock): number {
  return Math.max(1, stock.lbc || 1);
}

function toMainlineStock(stock: TopicStock): MarketMainlineStock {
  return { name: stock.name, code: stock.code, lbc: boardHeight(stock) };
}

export type MainlineLanesInput = {
  /** 过滤后的板块宇宙（loadPlateUniverse 输出） */
  plates: PlateFlow[];
  /** 当日涨停池（已附概念） */
  ztPool: TopicStock[];
  /** 概念封单兜底（buildTopicFundMap 输出，单位亿） */
  topicFunds: Map<string, number>;
  /** 近若干交易日涨停池（按日），持续性回看用；latestDay 当日不计入 */
  historyZtByDate?: Map<string, TopicStock[]>;
  latestDay?: string;
  /** xgb 趋势板块推荐（催化层） */
  trendingPlates?: TrendingPlate[];
};

export function buildMainlineLanes(input: MainlineLanesInput): MarketMainlineLane[] {
  const { plates, ztPool, topicFunds, historyZtByDate, latestDay, trendingPlates } = input;
  const cfg = getStrategy().mainline;
  const exclude = new Set(cfg.exclude.map((name) => normalizePlateName(name)));

  // 市场最高/次高板（去重取前两档），决定空间地位分
  const marketHeights = [...new Set(ztPool.map(boardHeight))].sort((a, b) => b - a);
  const marketMaxHeight = marketHeights[0] ?? 0;
  const marketSecondHeight = marketHeights[1] ?? 0;

  // 按概念分组：主概念 ×1、次概念 ×secondaryWeight；组名排除纯事件/无效标签
  type Member = { stock: TopicStock; weight: number };
  const groups = new Map<string, Map<string, Member>>();
  ztPool.forEach((stock) => {
    stockConcepts(stock).forEach((name, index) => {
      const key = normalizePlateName(name);
      if (!key || exclude.has(key)) return;
      const members = groups.get(name) ?? new Map<string, Member>();
      const code = normalizeCode(stock.code) || stock.name;
      const weight = index === 0 ? 1 : cfg.secondaryWeight;
      const prev = members.get(code);
      if (!prev || weight > prev.weight) members.set(code, { stock, weight });
      groups.set(name, members);
    });
  });

  // 持续性：近 persistDays 个交易日（不含当日）题材在榜天数与累计涨停家数
  const persistDays = new Map<string, Set<string>>();
  const persistZt = new Map<string, number>();
  const histDays = [...(historyZtByDate?.keys() ?? [])]
    .filter((day) => day && day !== latestDay)
    .sort()
    .slice(-cfg.persistDays);
  histDays.forEach((day) => {
    const dayCodes = new Map<string, Set<string>>();
    (historyZtByDate?.get(day) ?? []).forEach((stock) => {
      stockConcepts(stock).forEach((name) => {
        const key = normalizePlateName(name);
        if (!key) return;
        const codes = dayCodes.get(key) ?? new Set<string>();
        codes.add(normalizeCode(stock.code) || stock.name);
        dayCodes.set(key, codes);
      });
    });
    dayCodes.forEach((codes, key) => {
      const days = persistDays.get(key) ?? new Set<string>();
      days.add(day);
      persistDays.set(key, days);
      persistZt.set(key, (persistZt.get(key) ?? 0) + codes.size);
    });
  });

  // 催化索引：plate_id 优先，归一名兜底
  const trendingById = new Map<string, TrendingPlate>();
  const trendingByName = new Map<string, TrendingPlate>();
  (trendingPlates ?? []).forEach((item) => {
    if (item.plateId) trendingById.set(item.plateId, item);
    trendingByName.set(normalizePlateName(item.name), item);
  });

  const stats = [...groups.entries()].map(([name, members]) => {
    const rows = [...members.values()];
    const sorted = rows.map((member) => member.stock).sort((a, b) => b.lbc - a.lbc || (a.time ?? Infinity) - (b.time ?? Infinity));
    const plate = matchPlate(plates, name);
    const fallbackNetFlow = topicFunds.get(name) || 0;
    const netFlow = plate?.netFlow || fallbackNetFlow;
    const size = plate ? Math.max(plate.upCount + plate.downCount + plate.flatCount, 1) : 0;
    const ztEff = rows.reduce((sum, member) => sum + member.weight, 0);
    const maxHeight = sorted[0] ? boardHeight(sorted[0]) : 0;
    const heightEff = rows.reduce((sum, member) => sum + boardHeight(member.stock) * member.weight, 0);
    const sealFundSum = rows.reduce((sum, member) => sum + (member.stock.fund || 0), 0) / 1e8;
    const breaks = rows.reduce((sum, member) => sum + (member.stock.zbc || 0), 0);
    const earlyShare =
      rows.length > 0 ? rows.filter((member) => member.stock.time != null && member.stock.time <= cfg.earlySealMinutes).length / rows.length : 0;
    const key = normalizePlateName(name);
    const trending = (plate && trendingById.get(plate.code)) || trendingByName.get(key);
    return {
      name,
      plate,
      sorted,
      netFlow,
      size,
      ztCount: rows.length,
      maxHeight,
      heightEff,
      ztEff,
      sealFundSum,
      breaks,
      earlyShare,
      daysActive: persistDays.get(key)?.size ?? 0,
      histZtCount: persistZt.get(key) ?? 0,
      catalyst: trending?.description || undefined,
      catalyzed: Boolean(trending),
    };
  });

  const netFlows = stats.map((item) => item.netFlow);
  const intensities = stats.map((item) => (item.size > 0 ? item.netFlow / item.size : 0));
  const w = cfg.weights;

  return stats
    .map((item) => {
      const attack = Math.min(item.ztEff, w.attackCap) * w.attackPerBoard;
      const ladder = Math.min(item.maxHeight * w.maxHeight + item.heightEff * w.heightSum, w.ladderCap);
      const position =
        item.maxHeight === marketMaxHeight
          ? w.marketMaxBonus
          : item.maxHeight === marketSecondHeight
            ? w.marketSecondBonus
            : 0;
      const flow =
        (w.flowNetShare * percentileRank(netFlows, item.netFlow) +
          (1 - w.flowNetShare) * percentileRank(intensities, item.size > 0 ? item.netFlow / item.size : 0)) *
        w.flowScale;
      const persistence =
        Math.min(item.daysActive, cfg.persistDays) * w.persistPerDay +
        Math.min(item.histZtCount, w.persistZtCap) * w.persistZt;
      const quality = Math.max(
        0,
        item.earlyShare * w.earlyShare +
          Math.min(item.sealFundSum, w.sealFundCap) * w.sealFund -
          Math.min(item.breaks, w.breakCap) * w.breakPenalty
      );
      const catalyst = item.catalyzed ? cfg.catalystBonus : 0;
      return { ...item, score: attack + ladder + position + flow + persistence + quality + catalyst };
    })
    .sort((a, b) => b.score - a.score || b.ztCount - a.ztCount || b.netFlow - a.netFlow)
    .slice(0, cfg.limit)
    .map((item) => ({
      name: item.name,
      value: item.netFlow !== 0 ? formatPlateFlow(item.netFlow) : '--',
      change: item.plate?.change || 0,
      netFlow: item.netFlow,
      ztCount: item.ztCount,
      maxHeight: item.maxHeight,
      upCount: item.plate?.upCount || 0,
      downCount: item.plate?.downCount || 0,
      leader: item.sorted[0] ? toMainlineStock(item.sorted[0]) : null,
      followers: item.sorted.slice(1, cfg.followers + 1).map(toMainlineStock),
      score: Math.round(item.score),
      persistDays: item.daysActive,
      catalyst: item.catalyst,
    }));
}
