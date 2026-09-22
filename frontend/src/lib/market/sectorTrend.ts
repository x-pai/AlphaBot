import type { MarketTrendPanelData, MarketTrendStage, MarketTrendTopic, MarketTrendStockTag } from './types';
import { stockConcepts, type PlateFlow, type SurgeLimitStock, type TopicStock } from './api';
import { isoDate, matchPlate, normalizeCode, normalizePlateName } from './format';
import { getTrendPlateWeight, isTrendExcludedPlate } from './plateFilter';
import { percentileRank } from './flowStrength';
import { getStrategy } from './strategy';
import { dedupeCandidatePlates, type PlateGroup } from './plateDedup';

const INFLOW_COLORS = ['#ff5a6f', '#5b8def', '#18b7d8', '#f59e0b', '#14b8a6'];
const OUTFLOW_COLORS = ['#f7bfc5', '#c8d4f2', '#b9e8ee', '#f6d8ae', '#cfe9df'];

export const EMPTY_SECTOR_TREND: MarketTrendPanelData = {
  range: 20,
  latestDay: '',
  topics: [],
  stockTags: {},
  sampleStats: {
    baseCount: 0,
    eventAddedCount: 0,
    finalCount: 0,
  },
};

function clampScore(value: number): number {
  return Math.max(0, Math.min(100, value));
}

function plateSize(plate: PlateFlow): number {
  return plate.upCount + plate.downCount + plate.flatCount;
}

/** 趋势视角不纳入 ST/*ST/退市整理股票，避免其异常涨跌幅与资金流污染板块统计。 */
function isDelistingRiskStock(name: string): boolean {
  return /ST/i.test(name) || /退$/.test(name);
}

function candidateRpsScore(input: {
  changeRank: number;
  netFlowRank: number;
  flowIntensityRank: number;
  breadthRank: number;
  ztRank: number;
}): number {
  const { rps } = getStrategy().trend;
  const priceScore = input.changeRank;
  const flowScore = input.netFlowRank * rps.flowNetShare + input.flowIntensityRank * rps.flowIntensityShare;
  const breadthScore = input.breadthRank;
  const activityScore = input.ztRank;
  return clampScore(flowScore * rps.flow + breadthScore * rps.breadth + priceScore * rps.price + activityScore * rps.activity);
}

function inferPhase(score: number): MarketTrendStage {
  const [main, ferment, diverge, swing, ebb] = getStrategy().trend.phase;
  if (score >= main) return '主升';
  if (score >= ferment) return '发酵';
  if (score >= diverge) return '分歧';
  if (score >= swing) return '震荡';
  if (score >= ebb) return '退潮';
  return '冷却';
}

function stockInPlate(stock: TopicStock, plate: PlateFlow): boolean {
  return stockConcepts(stock).some(
    (name) => matchPlate([plate], name)?.code === plate.code || normalizePlateName(name) === normalizePlateName(plate.name)
  );
}

function ztCountForPlate(plate: PlateFlow, ztList: TopicStock[], surge: SurgeLimitStock[]): number {
  return ztCountForGroup([plate], ztList, surge);
}

/** 按题材组计数：组内任一板块命中即算，一股只计 1 次 */
function ztCountForGroup(members: PlateFlow[], ztList: TopicStock[], surge: SurgeLimitStock[]): number {
  const byConcept = ztList.filter(
    (stock) => !isDelistingRiskStock(stock.name) && members.some((plate) => stockInPlate(stock, plate))
  ).length;
  const bySurge = surge.filter((stock) =>
    !isDelistingRiskStock(stock.name) &&
    members.some((plate) =>
      stock.plates.some((name) => name === plate.name || matchPlate([plate], name)?.code === plate.code)
    )
  ).length;
  return Math.max(byConcept, bySurge);
}

function highlightedStocksForGroup(members: PlateFlow[], ztList: TopicStock[]): MarketTrendTopic['highlightedStocks'] {
  const seen = new Set<string>();
  return ztList
    .filter((stock) => !isDelistingRiskStock(stock.name) && members.some((plate) => stockInPlate(stock, plate)))
    .sort((a, b) => b.lbc - a.lbc || (a.time ?? Infinity) - (b.time ?? Infinity))
    .filter((stock) => {
      const code = normalizeCode(stock.code) || stock.name;
      if (seen.has(code)) return false;
      seen.add(code);
      return true;
    })
    .slice(0, 8)
    .map((stock) => ({
      code: normalizeCode(stock.code),
      name: stock.name,
      lbc: Math.max(1, stock.lbc || 1),
    }));
}

function pickCandidatePlates(plates: PlateFlow[], ztList: TopicStock[], surge: SurgeLimitStock[]): PlateFlow[] {
  const { candidateLimit, slicePerSide } = getStrategy().trend;
  const matched = new Map<string, PlateFlow>();
  const push = (plate?: PlateFlow) => {
    if (!plate?.code || isTrendExcludedPlate(plate.name) || matched.has(plate.code)) return;
    matched.set(plate.code, plate);
  };

  ztList.forEach((stock) => stockConcepts(stock).forEach((name) => push(matchPlate(plates, name))));
  surge.forEach((stock) => stock.plates.forEach((name) => push(matchPlate(plates, name))));

  const weightedFlow = (plate: PlateFlow) => plate.netFlow * getTrendPlateWeight(plate.name);
  const weightedChange = (plate: PlateFlow) => plate.change * getTrendPlateWeight(plate.name);

  // 排除名单必须在候选池阶段硬过滤；仅把权重设为 0 仍可能在候选不足时被推入榜单。
  const eligiblePlates = plates.filter((plate) => !isTrendExcludedPlate(plate.name));
  const byFlow = [...eligiblePlates]
    .sort((a, b) => weightedFlow(b) - weightedFlow(a) || b.ztCount - a.ztCount)
    .slice(0, slicePerSide);
  const byChange = [...eligiblePlates]
    .sort((a, b) => weightedChange(b) - weightedChange(a) || b.netFlow - a.netFlow)
    .slice(0, slicePerSide);

  [...byFlow, ...byChange].forEach((plate) => push(plate));
  return Array.from(matched.values()).slice(0, candidateLimit);
}

function toTopic(
  group: PlateGroup,
  index: number,
  flow: MarketTrendTopic['flow'],
  colors: string[],
  date: string,
  ztList: TopicStock[],
  surge: SurgeLimitStock[],
  score: number
): MarketTrendTopic {
  const plate = group.representative;
  const size = Math.max(plateSize(plate), 1);
  const ztCount = ztCountForGroup(group.members, ztList, surge);
  const ztRatio = ztCount / size;
  const breadth = plate.upCount / size;
  return {
    id: plate.code,
    name: plate.name,
    color: colors[index % colors.length],
    flow,
    date,
    score,
    changePct: plate.change,
    moneyFlow: plate.netFlow,
    breadth,
    ztCount,
    ztRatio,
    phase: inferPhase(score),
    highlightedStocks: highlightedStocksForGroup(group.members, ztList),
    relatedPlates: group.related.length > 0 ? group.related : undefined,
  };
}

function buildStockTags(ztList: TopicStock[], surge: SurgeLimitStock[]): Record<string, MarketTrendStockTag> {
  const surgeByCode = new Map(surge.map((item) => [normalizeCode(item.code), item]));
  return Object.fromEntries(
    ztList.map((stock) => {
      const lbc = Math.max(1, stock.lbc || 1);
      const code = normalizeCode(stock.code);
      const surgeItem = surgeByCode.get(code);
      return [
        code,
        {
          lbc,
          status: lbc <= 1 ? '首板' : `${lbc}板`,
          analysis: surgeItem?.analysis || undefined,
          plate: stock.reason?.trim() || undefined,
        },
      ];
    })
  );
}

export function buildSectorTrendData(
  latestDay: string,
  plates: PlateFlow[],
  ztList: TopicStock[],
  surge: SurgeLimitStock[] = []
): MarketTrendPanelData {
  const eligibleZtList = ztList.filter((stock) => !isDelistingRiskStock(stock.name));
  const eligibleSurge = surge.filter((stock) => !isDelistingRiskStock(stock.name));
  const picked = pickCandidatePlates(plates, eligibleZtList, eligibleSurge);
  if (picked.length === 0) return EMPTY_SECTOR_TREND;

  // 同题材归并：近义概念并成一组，只留代表板参与候选
  const groups = dedupeCandidatePlates(picked, (plate) => ztCountForPlate(plate, eligibleZtList, eligibleSurge));

  const date = isoDate(latestDay);
  const metrics = groups.map((group) => {
    const plate = group.representative;
    const size = Math.max(plateSize(plate), 1);
    const breadth = plate.upCount / size;
    // 户均主力净流入：替代原"资金/成交额"集中度（xgb 无板块成交额）
    const flowIntensity = plate.netFlow / size;
    return {
      group,
      plate,
      breadth,
      flowIntensity,
    };
  });

  const changeValues = metrics.map((item) => item.plate.change);
  const netFlowValues = metrics.map((item) => item.plate.netFlow);
  const flowIntensityValues = metrics.map((item) => item.flowIntensity);
  const breadthValues = metrics.map((item) => item.breadth);
  const ztCountValues = metrics.map((item) => item.plate.ztCount);

  const topics = metrics.map((item, index) => {
    const baseScore = candidateRpsScore({
      changeRank: percentileRank(changeValues, item.plate.change),
      netFlowRank: percentileRank(netFlowValues, item.plate.netFlow),
      flowIntensityRank: percentileRank(flowIntensityValues, item.flowIntensity),
      breadthRank: percentileRank(breadthValues, item.breadth),
      ztRank: percentileRank(ztCountValues, item.plate.ztCount),
    });
    const score = clampScore(baseScore * getTrendPlateWeight(item.plate.name));

    return toTopic(
      item.group,
      index,
      item.plate.netFlow >= 0 ? 'in' : 'out',
      item.plate.netFlow >= 0 ? INFLOW_COLORS : OUTFLOW_COLORS,
      date,
      eligibleZtList,
      eligibleSurge,
      score
    );
  });

  return {
    range: 20,
    latestDay: date,
    topics: topics.sort((a, b) => b.score - a.score || b.moneyFlow - a.moneyFlow),
    stockTags: buildStockTags(eligibleZtList, eligibleSurge),
    sampleStats: {
      baseCount: plates.length,
      eventAddedCount: 0,
      finalCount: topics.length,
    },
  };
}
