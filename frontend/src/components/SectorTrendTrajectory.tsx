'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { loadPlateFlowHistory, loadPlateMembers, type PlateFlowHistoryPoint, type PlateMember } from '@/lib/market/api';
import { flowStrengthScore, percentileRank } from '@/lib/market/flowStrength';
import { getStrategy } from '@/lib/market/strategy';
import type { MarketTrendPanelData, MarketTrendStage, MarketTrendTopic } from '@/lib/market/types';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { StockPreviewTooltip } from '@/components/StockPreviewTooltip';
import { cn } from '@/lib/utils';

type SectorTrendTrajectoryProps = {
  data: MarketTrendPanelData;
  onSelectStock?: (code: string, name: string) => void;
};

type MemberSortKey = 'rank' | 'changePercent' | 'amount' | 'netFlow' | 'turnoverRate';

type TrendMember = {
  rank: number;
  code: string;
  name: string;
  lbc: number;
  changePercent: number;
  amount: number;
  netFlow: number;
  turnoverRate: number;
  status?: string;
  limitAnalysis?: string;
  limitPlate?: string;
};

type TopicHistoryPoint = {
  date: string;
  expmaValue: number;
  expmaRatioPct: number;
  strengthScore: number;
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
  rank: number;
  /** 兜底占位点（历史未加载）：不参与当日百分位与排名 */
  excluded?: boolean;
};

type SectorPulseState = '加强' | '新启动' | '修复' | '分歧' | '退潮' | '冷却';

type TopicInsight = {
  topic: MarketTrendTopic;
  points: TopicHistoryPoint[];
  latest: TopicHistoryPoint;
  state: SectorPulseState;
  stateReason: string;
  /** 排行榜右侧展示前一交易日的历史状态，避免与名称旁当日状态重复。 */
  previousState: SectorPulseState;
  scoreDelta1d: number;
  scoreDelta3d: number;
  scoreSlope3d: number | null;
  flowDelta1d: number;
  flowDelta3d: number;
  flowSum3d: number | null;
  expmaDelta1d: number;
  rankDelta3d: number;
  latestRank: number;
  breadthPct: number;
  ztPct: number;
  moneyFlowRank: number;
  scoreRank: number;
};

type RankingViewMode = 'today' | 'trend';

type StructureRole = {
  role: '龙头' | '中军' | '补涨';
  name: string;
  note: string;
  code?: string;
};

type LadderRow = {
  label: string;
  count: number;
  width: number;
};

const SVG_WIDTH = 1000;
const SVG_HEIGHT = 372;
const PAD = { top: 20, right: 112, bottom: 34, left: 44 };
/** 分区/脉冲阈值来自 strategy.ts 的 trend 节点（标定依据见该文件与回测记录）。 */const PHASE_STYLES: Record<MarketTrendStage, string> = {
  主升: 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-200',
  发酵: 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-200',
  分歧: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-950/40 dark:text-yellow-200',
  震荡: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-200',
  退潮: 'bg-sky-100 text-sky-700 dark:bg-sky-950/40 dark:text-sky-200',
  冷却: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200',
};

const FLOW_META = {
  in: {
    label: '净流入',
    badge: 'bg-rose-50 text-rose-600 dark:bg-rose-950/20 dark:text-rose-300',
  },
  out: {
    label: '净流出',
    badge: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/20 dark:text-emerald-300',
  },
} as const;

const PULSE_STYLES: Record<SectorPulseState, string> = {
  加强: 'bg-rose-50 text-rose-700 dark:bg-rose-950/30 dark:text-rose-200',
  新启动: 'bg-orange-50 text-orange-700 dark:bg-orange-950/30 dark:text-orange-200',
  修复: 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-200',
  分歧: 'bg-yellow-50 text-yellow-700 dark:bg-yellow-950/30 dark:text-yellow-200',
  退潮: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-200',
  冷却: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200',
};

const PULSE_COLORS: Record<SectorPulseState, string> = {
  加强: '#e11d48',
  新启动: '#f97316',
  修复: '#f59e0b',
  分歧: '#eab308',
  退潮: '#10b981',
  冷却: '#64748b',
};

function shortDate(value: string) {
  if (!value || value.length < 8) return value;
  return `${value.slice(5, 7)}-${value.slice(8, 10)}`;
}

function formatPercent(value: number, digits = 2) {
  const amount = Number.isFinite(value) ? value : 0;
  return `${amount >= 0 ? '+' : ''}${amount.toFixed(digits)}%`;
}

function formatSignedYi(value: number) {
  const amount = Number.isFinite(value) ? value : 0;
  return `${amount >= 0 ? '+' : ''}${amount.toFixed(1)}亿`;
}

function formatSignedPoints(value: number | null, suffix = '分') {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}${suffix}`;
}

function formatSignedYiOptional(value: number | null) {
  if (value == null || !Number.isFinite(value)) return '--';
  return formatSignedYi(value);
}

function formatYi(value: number) {
  const amount = Number.isFinite(value) ? value : 0;
  return `${amount.toFixed(1)}亿`;
}

function formatRatio(value: number) {
  if (!Number.isFinite(value)) return '--';
  return `${Math.round(value * 100)}%`;
}

function boardHeightLabel(lbc: number) {
  if (lbc <= 1) return '首板';
  return `${lbc}板`;
}

function yForStrength(value: number) {
  const plotHeight = SVG_HEIGHT - PAD.top - PAD.bottom;
  return PAD.top + ((100 - value) / 100) * plotHeight;
}

function barBaseY() {
  return SVG_HEIGHT - PAD.bottom;
}

function barTopFor(value: number) {
  return yForStrength(value);
}

function xFor(index: number, total: number) {
  const plotWidth = SVG_WIDTH - PAD.left - PAD.right;
  if (total <= 1) return PAD.left + plotWidth / 2;
  return PAD.left + (plotWidth * index) / (total - 1);
}

function stageForScore(score: number): MarketTrendStage {
  const { zones } = getStrategy().trend;
  if (score >= zones.main) return '主升';
  if (score >= zones.strong) return '发酵';
  if (score >= zones.watch) return '震荡';
  return '退潮';
}

function deltaFromTail(values: number[], offset: number) {
  if (values.length === 0) return 0;
  const latest = values[values.length - 1] || 0;
  const previous = values[Math.max(0, values.length - 1 - offset)] ?? values[0] ?? 0;
  return latest - previous;
}

/** 最近4个交易日资金强度的线性回归拟合，3个间隔，单位：分/日。 */
function linearRegressionFit(values: number[]): { slope: number; intercept: number } | null {
  if (values.length < 4) return null;
  const window = values.slice(-4);
  const xMean = 1.5;
  const yMean = window.reduce((sum, value) => sum + value, 0) / window.length;
  const numerator = window.reduce((sum, value, index) => sum + (index - xMean) * (value - yMean), 0);
  const denominator = window.reduce((sum, _value, index) => sum + (index - xMean) ** 2, 0);
  if (denominator === 0) return null;
  const slope = numerator / denominator;
  return { slope, intercept: yMean - slope * xMean };
}

function linearRegressionSlope(values: number[]): number | null {
  return linearRegressionFit(values)?.slope ?? null;
}

function sumTail(values: number[], length: number): number | null {
  if (values.length < length) return null;
  return values.slice(-length).reduce((sum, value) => sum + value, 0);
}

function calcExpma(values: number[], period = 3) {
  if (values.length === 0) return [];
  const alpha = 2 / (period + 1);
  const result: number[] = [values[0]];
  for (let i = 1; i < values.length; i += 1) {
    result.push(alpha * values[i] + (1 - alpha) * result[i - 1]);
  }
  return result;
}

function buildExpmaDomain(series: TopicHistoryPoint[][]) {
  const values = series.flatMap((points) => points.map((point) => point.expmaRatioPct).filter((value) => Number.isFinite(value)));
  if (values.length === 0) return { min: -1, max: 1 };
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) {
    const padding = Math.max(0.4, Math.abs(min) * 0.2);
    return { min: min - padding, max: max + padding };
  }
  const padding = (max - min) * 0.08;
  return { min: min - padding, max: max + padding };
}

function buildNumericTicks(min: number, max: number, count = 5) {
  if (!Number.isFinite(min) || !Number.isFinite(max) || count <= 1) return [min, max];
  return Array.from({ length: count }, (_, index) => min + ((max - min) * index) / (count - 1));
}

function fallbackHistoryPoint(topic: MarketTrendTopic, rank: number): TopicHistoryPoint {
  return {
    date: topic.date,
    expmaValue: 0,
    expmaRatioPct: 0,
    strengthScore: 50,
    mainNetInflow: topic.moneyFlow,
    mainNetInflowRatio: 0,
    superLargeNetInflow: 0,
    superLargeNetInflowRatio: 0,
    largeNetInflow: 0,
    largeNetInflowRatio: 0,
    midNetInflow: 0,
    midNetInflowRatio: 0,
    smallNetInflow: 0,
    smallNetInflowRatio: 0,
    rank,
    excluded: true,
  };
}

function buildTopicHistory(flowPoints: PlateFlowHistoryPoint[], topic: MarketTrendTopic): TopicHistoryPoint[] {
  if (flowPoints.length === 0) return [fallbackHistoryPoint(topic, 0)];

  // 折线 = 净流入占比（净额/成交额，无量纲）的 EXPMA(3)，单位 %，跨板块可比；
  // 旧口径按各板块自身最大净流入归一，多线叠画在同一轴上是伪对比，已废弃
  const expma = calcExpma(flowPoints.map((point) => point.mainNetInflowRatio), 3);

  return flowPoints.map((point, index) => ({
    date: `${point.date.slice(0, 4)}-${point.date.slice(4, 6)}-${point.date.slice(6, 8)}`,
    expmaValue: expma[index] || point.mainNetInflowRatio || 0,
    expmaRatioPct: expma[index] ?? point.mainNetInflowRatio ?? 0,
    strengthScore: flowStrengthScore(point, 50),
    mainNetInflow: point.mainNetInflow,
    mainNetInflowRatio: point.mainNetInflowRatio,
    superLargeNetInflow: point.superLargeNetInflow,
    superLargeNetInflowRatio: point.superLargeNetInflowRatio,
    largeNetInflow: point.largeNetInflow,
    largeNetInflowRatio: point.largeNetInflowRatio,
    midNetInflow: point.midNetInflow,
    midNetInflowRatio: point.midNetInflowRatio,
    smallNetInflow: point.smallNetInflow,
    smallNetInflowRatio: point.smallNetInflowRatio,
    rank: 0,
  }));
}

function rankDeltaFromTail(points: TopicHistoryPoint[], offset: number) {
  const latest = points[points.length - 1]?.rank;
  const previous = points[Math.max(0, points.length - 1 - offset)]?.rank;
  if (!latest || !previous) return 0;
  return previous - latest;
}

function classifyPulse(topic: MarketTrendTopic, points: TopicHistoryPoint[]) {
  const { zones, pulseDelta3d: PULSE_DELTA3D } = getStrategy().trend;
  const SCORE_ZONE_MAIN = zones.main;
  const SCORE_ZONE_STRONG = zones.strong;
  const scores = points.map((point) => point.strengthScore);
  const expma = points.map((point) => point.expmaRatioPct);
  const flows = points.map((point) => point.mainNetInflow);
  const latestScore = scores[scores.length - 1] ?? topic.score;
  const scoreDelta1d = deltaFromTail(scores, 1);
  const scoreDelta3d = deltaFromTail(scores, 3);
  const flowDelta1d = deltaFromTail(flows, 1);
  const flowDelta3d = deltaFromTail(flows, 3);
  const expmaDelta1d = deltaFromTail(expma, 1);
  const latestRatio = points[points.length - 1]?.mainNetInflowRatio ?? 0;
  const latestRank = points[points.length - 1]?.rank ?? 0;
  const rankDelta3d = rankDeltaFromTail(points, 3);
  const validPoints = points.filter((point) => !point.excluded);
  const scoreSlope3d = linearRegressionSlope(validPoints.map((point) => point.strengthScore));
  const flowSum3d = sumTail(validPoints.map((point) => point.mainNetInflow), 3);
  const metrics = { scoreDelta1d, scoreDelta3d, scoreSlope3d, flowDelta1d, flowDelta3d, flowSum3d, expmaDelta1d, rankDelta3d, latestRank };

  if (latestScore >= SCORE_ZONE_MAIN && scoreDelta3d >= PULSE_DELTA3D && flowDelta3d >= 0 && latestRatio >= 0) {
    return { state: '加强' as const, stateReason: '主力净流入与净占比同步走强，趋势仍在抬升', ...metrics };
  }
  if (latestScore >= SCORE_ZONE_STRONG && rankDelta3d >= 3 && flowDelta3d > 0) {
    return { state: '新启动' as const, stateReason: '近几日主力排名快速抬升，具备资金新启动特征', ...metrics };
  }
  if (scoreDelta3d > 0 && flowDelta3d > 0 && latestRatio > 0 && latestScore < SCORE_ZONE_MAIN) {
    return { state: '修复' as const, stateReason: '资金重新回流，但强度中枢仍低于主升区', ...metrics };
  }
  if (latestScore >= 50 && (scoreDelta1d < 0 || flowDelta1d < 0 || expmaDelta1d < 0) && latestRatio > -1.5) {
    return { state: '分歧' as const, stateReason: '板块仍有活跃度，但主力净流入开始放缓', ...metrics };
  }
  if (scoreDelta3d <= -PULSE_DELTA3D || flowDelta3d < 0 || latestRatio < -2) {
    return { state: '退潮' as const, stateReason: '真实资金流持续走弱，排名与强度中枢下移', ...metrics };
  }
  return { state: '冷却' as const, stateReason: '当前缺少持续强化信号，资金尚未形成明确方向', ...metrics };
}

function linePath(points: TopicHistoryPoint[], yForExpma: (value: number) => number) {
  return points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${xFor(index, points.length).toFixed(1)} ${yForExpma(point.expmaRatioPct).toFixed(1)}`)
    .join(' ');
}

function rankChip(delta: number) {
  if (delta > 0) return `较3日 +${delta}`;
  if (delta < 0) return `较3日 ${delta}`;
  return '较3日 持平';
}

function buildStateNote(point: TopicHistoryPoint, previous?: TopicHistoryPoint | null) {
  const flowDelta = point.mainNetInflow - (previous?.mainNetInflow ?? point.mainNetInflow);
  if (point.mainNetInflowRatio >= 0 && flowDelta > 0) return '主力回流加速，板块承接增强。';
  if (point.mainNetInflowRatio >= 0 && flowDelta <= 0) return '资金仍偏正，但边际增量开始放缓。';
  if (point.mainNetInflowRatio < 0 && flowDelta > 0) return '抛压尚在缓解，处于修复观察阶段。';
  return '资金分歧偏大，更多在核心股间博弈。';
}

function buildLadderRows(stockTags: Record<string, MarketTrendPanelData['stockTags'][string]>, members: TrendMember[]): LadderRow[] {
  const counts = new Map<string, number>([
    ['6板+', 0],
    ['5板', 0],
    ['4板', 0],
    ['3板', 0],
    ['2板', 0],
    ['首板', 0],
  ]);

  members.forEach((member) => {
    const lbc = stockTags[member.code]?.lbc;
    if (!lbc) return;
    if (lbc >= 6) counts.set('6板+', (counts.get('6板+') || 0) + 1);
    else if (lbc === 5) counts.set('5板', (counts.get('5板') || 0) + 1);
    else if (lbc === 4) counts.set('4板', (counts.get('4板') || 0) + 1);
    else if (lbc === 3) counts.set('3板', (counts.get('3板') || 0) + 1);
    else if (lbc === 2) counts.set('2板', (counts.get('2板') || 0) + 1);
    else counts.set('首板', (counts.get('首板') || 0) + 1);
  });

  const maxCount = Math.max(...Array.from(counts.values()), 1);
  return Array.from(counts.entries()).map(([label, count]) => ({
    label,
    count,
    width: Math.max(count > 0 ? 18 : 8, Math.round((count / maxCount) * 100)),
  }));
}

function endLabelPosition(index: number, values: Array<{ id: string; y: number }>) {
  const sorted = [...values].sort((a, b) => a.y - b.y);
  const gap = 14;
  for (let i = 1; i < sorted.length; i += 1) {
    if (sorted[i].y - sorted[i - 1].y < gap) {
      sorted[i].y = sorted[i - 1].y + gap;
    }
  }
  for (let i = sorted.length - 2; i >= 0; i -= 1) {
    if (sorted[i + 1].y > SVG_HEIGHT - PAD.bottom) {
      sorted[i + 1].y = SVG_HEIGHT - PAD.bottom;
    }
    if (sorted[i + 1].y - sorted[i].y < gap) {
      sorted[i].y = sorted[i + 1].y - gap;
    }
  }
  return sorted.find((item) => item.id === values[index].id)?.y ?? values[index].y;
}

export default function SectorTrendTrajectory({ data, onSelectStock }: SectorTrendTrajectoryProps) {
  const trendCfg = getStrategy().trend;
  const yTicks = [0, trendCfg.zones.watch, trendCfg.zones.strong, trendCfg.zones.main, 100];
  const topics = useMemo(() => data.topics || [], [data.topics]);
  const [selectedId, setSelectedId] = useState<string | null>(topics[0]?.id ?? null);
  const [viewMode, setViewMode] = useState<RankingViewMode>('today');
  const [histories, setHistories] = useState<Record<string, TopicHistoryPoint[]>>({});
  const [membersById, setMembersById] = useState<Record<string, TrendMember[]>>({});
  const [sortBy, setSortBy] = useState<{ key: MemberSortKey; dir: 'asc' | 'desc' }>({ key: 'changePercent', dir: 'desc' });
  const [hover, setHover] = useState<{ topicId: string; pointIndex: number } | null>(null);
  const [detailHoverIndex, setDetailHoverIndex] = useState<number | null>(null);

  useEffect(() => {
    if (topics.length === 0) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !topics.some((topic) => topic.id === selectedId)) {
      setSelectedId(topics[0].id);
    }
  }, [selectedId, topics]);

  useEffect(() => {
    setDetailHoverIndex(null);
  }, [selectedId, viewMode]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    loadPlateMembers(selectedId)
      .then((members) => {
        if (!active) return;
        setMembersById((current) => ({
          ...current,
          [selectedId]: members.map((item: PlateMember, index) => ({
            rank: index + 1,
            code: item.code,
            name: item.name,
            lbc: data.stockTags[item.code]?.lbc || 0,
            changePercent: item.change,
            amount: item.amount,
            netFlow: item.netFlow,
            turnoverRate: item.turnoverRate,
            status: data.stockTags[item.code]?.status,
            limitAnalysis: data.stockTags[item.code]?.analysis,
            limitPlate: data.stockTags[item.code]?.plate,
          })),
        }));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [data.stockTags, selectedId]);

  const historiesWithRank = useMemo(() => {
    // Pass 1：同日候选净流入百分位（兜底占位点不参与基数）
    const flowsByDate = new Map<string, number[]>();
    Object.values(histories).forEach((points) => {
      points.forEach((point) => {
        if (point.excluded) return;
        const rows = flowsByDate.get(point.date) || [];
        rows.push(point.mainNetInflow);
        flowsByDate.set(point.date, rows);
      });
    });

    // Pass 2：回填最终 strengthScore（金额项 = 同日百分位）
    const scored = new Map<string, TopicHistoryPoint[]>();
    Object.entries(histories).forEach(([topicId, points]) => {
      scored.set(
        topicId,
        points.map((point) => ({
          ...point,
          strengthScore: point.excluded
            ? point.strengthScore
            : flowStrengthScore(point, percentileRank(flowsByDate.get(point.date) || [], point.mainNetInflow)),
        }))
      );
    });

    // Pass 3：按最终分做每日排名（兜底占位点不参与）
    const rankRows = new Map<string, Array<{ id: string; score: number; flow: number }>>();
    scored.forEach((points, topicId) => {
      points.forEach((point) => {
        if (point.excluded) return;
        const rows = rankRows.get(point.date) || [];
        rows.push({ id: topicId, score: point.strengthScore, flow: point.mainNetInflow });
        rankRows.set(point.date, rows);
      });
    });
    const rankMap = new Map<string, Map<string, number>>();
    rankRows.forEach((rows, date) => {
      const ranked = [...rows].sort((a, b) => b.score - a.score || b.flow - a.flow);
      rankMap.set(date, new Map(ranked.map((row, index) => [row.id, index + 1])));
    });

    return Object.fromEntries(
      topics.map((topic, topicIndex) => {
        const basePoints = scored.get(topic.id) || [fallbackHistoryPoint(topic, topicIndex + 1)];
        return [
          topic.id,
          basePoints.map((point) => ({
            ...point,
            rank:
              rankMap.get(point.date)?.get(topic.id) || point.rank || topicIndex + 1,
          })),
        ];
      })
    ) as Record<string, TopicHistoryPoint[]>;
  }, [histories, topics]);

  const topicInsights = useMemo(() => {
    const scoreRankMap = new Map(
      [...topics]
        .sort((a, b) => b.score - a.score || b.moneyFlow - a.moneyFlow)
        .map((topic, index) => [topic.id, index + 1])
    );
    const flowRankMap = new Map(
      [...topics]
        .sort((a, b) => b.moneyFlow - a.moneyFlow || b.score - a.score)
        .map((topic, index) => [topic.id, index + 1])
    );

    return topics
      .map((topic, index) => {
        const points = historiesWithRank[topic.id] || [fallbackHistoryPoint(topic, index + 1)];
        const latest = points[points.length - 1] || points[0];
        const pulse = classifyPulse(topic, points);
        const previousPoints = points.length > 1 ? points.slice(0, -1) : points;
        const previousPulse = classifyPulse(topic, previousPoints);
        return {
          topic,
          points,
          latest,
          state: pulse.state,
          stateReason: pulse.stateReason,
          previousState: previousPulse.state,
          scoreDelta1d: pulse.scoreDelta1d,
          scoreDelta3d: pulse.scoreDelta3d,
          scoreSlope3d: pulse.scoreSlope3d,
          flowDelta1d: pulse.flowDelta1d,
          flowDelta3d: pulse.flowDelta3d,
          flowSum3d: pulse.flowSum3d,
          expmaDelta1d: pulse.expmaDelta1d,
          rankDelta3d: pulse.rankDelta3d,
          latestRank: pulse.latestRank || latest.rank || index + 1,
          breadthPct: topic.breadth * 100,
          ztPct: topic.ztRatio * 100,
          moneyFlowRank: flowRankMap.get(topic.id) || topics.length,
          scoreRank: scoreRankMap.get(topic.id) || topics.length,
        } satisfies TopicInsight;
      })
      .sort((a, b) => b.topic.score - a.topic.score || b.scoreDelta3d - a.scoreDelta3d);
  }, [historiesWithRank, topics]);

  const todayTopicInsights = useMemo(
    () =>
      [...topicInsights]
        .sort((a, b) => b.topic.score - a.topic.score || b.topic.moneyFlow - a.topic.moneyFlow || b.latest.strengthScore - a.latest.strengthScore)
        .slice(0, 10),
    [topicInsights]
  );

  const trendTopicInsights = useMemo(
    () =>
      [...topicInsights]
        .sort((a, b) => (b.scoreSlope3d ?? -Infinity) - (a.scoreSlope3d ?? -Infinity))
        .slice(0, 10),
    [topicInsights]
  );

  const activeTopicInsights = viewMode === 'today' ? todayTopicInsights : trendTopicInsights;
  // 默认只拉当前选中板块的历史；切到趋势视角后再补齐候选历史，降低首屏 fundflow 压力
  const historyTargetIds = useMemo(() => {
    const ids = new Set<string>();
    if (selectedId) ids.add(selectedId);
    if (viewMode === 'trend') {
      topics.forEach((topic) => ids.add(topic.id));
    }
    return Array.from(ids);
  }, [topics, selectedId, viewMode]);
  const selectedInsight = activeTopicInsights.find((item) => item.topic.id === selectedId) || activeTopicInsights[0] || null;
  const selectedTopic = selectedInsight?.topic || null;
  const activeHistory = selectedInsight?.points || [];

  useEffect(() => {
    if (historyTargetIds.length === 0) return;
    let active = true;

    const consumeBatch = async (batchIds: string[]) => {
      const results = await Promise.all(batchIds.map((id) => loadPlateFlowHistory(id, data.range || 20)));
      if (!active) return;
      setHistories((current) => {
        const next = { ...current };
        batchIds.forEach((id, index) => {
          const topic = topics.find((item) => item.id === id);
          if (!topic) return;
          next[id] = buildTopicHistory(results[index], topic);
        });
        return next;
      });
    };

    (async () => {
      try {
        for (let index = 0; index < historyTargetIds.length; index += 3) {
          await consumeBatch(historyTargetIds.slice(index, index + 3));
        }
      } catch {
        // keep current history cache
      }
    })();
    return () => {
      active = false;
    };
  }, [data.range, historyTargetIds, topics]);

  const pulseSummary = useMemo(() => {
    const count = (state: SectorPulseState) => topicInsights.filter((item) => item.state === state).length;
    return [
      { label: '连续强势', value: count('加强'), note: '真实资金强度与趋势继续抬升' },
      { label: '新启动', value: count('新启动'), note: '近几日历史排名快速抬升' },
      { label: '修复中', value: count('修复'), note: '分歧后主力资金重新回流' },
      { label: '分歧/退潮', value: count('分歧') + count('退潮'), note: '资金斜率转弱，需要观察承接' },
    ];
  }, [topicInsights]);

  const chartTopics = useMemo(
    () =>
      activeTopicInsights.map((item, index) => ({
        topic: item.topic,
        points: historiesWithRank[item.topic.id] || [fallbackHistoryPoint(item.topic, index + 1)],
      })),
    [activeTopicInsights, historiesWithRank]
  );

  const expmaDomain = useMemo(() => buildExpmaDomain(chartTopics.map((item) => item.points)), [chartTopics]);
  const expmaTicks = useMemo(() => buildNumericTicks(expmaDomain.min, expmaDomain.max), [expmaDomain]);
  const yForExpma = (value: number) => {
    const plotHeight = SVG_HEIGHT - PAD.top - PAD.bottom;
    const safeValue = Number.isFinite(value) ? value : expmaDomain.min;
    const range = expmaDomain.max - expmaDomain.min || 1;
    return PAD.top + ((expmaDomain.max - safeValue) / range) * plotHeight;
  };

  const xLabels = activeHistory.map((point) => point.date);
  const endPoints = chartTopics.map(({ topic, points }) => ({
    id: topic.id,
    y: yForExpma(points[points.length - 1]?.expmaRatioPct ?? 0),
  }));

  const sortedMembers = useMemo(() => {
    const values = [...(membersById[selectedId || ''] || [])];
    values.sort((a, b) => {
      if (sortBy.key === 'changePercent' && sortBy.dir === 'desc') {
        const lbcDelta = b.lbc - a.lbc;
        if (lbcDelta !== 0) return lbcDelta;
      }
      const left = a[sortBy.key];
      const right = b[sortBy.key];
      const delta = Number(left) - Number(right);
      if (delta !== 0) return sortBy.dir === 'asc' ? delta : -delta;
      return b.netFlow - a.netFlow || b.amount - a.amount || a.rank - b.rank;
    });
    return values;
  }, [membersById, selectedId, sortBy]);

  const selectedMembers = useMemo(
    () => (selectedTopic ? membersById[selectedTopic.id] || [] : []),
    [membersById, selectedTopic]
  );

  const expansionMetrics = useMemo(() => {
    const total = selectedMembers.length;
    if (total === 0) {
      return {
        advancers: 0,
        advPct: 0,
        strongCount: 0,
        positiveFlowCount: 0,
        positiveFlowPct: 0,
        coreAmountShare: 0,
      };
    }
    const advancers = selectedMembers.filter((member) => member.changePercent > 0).length;
    const strongCount = selectedMembers.filter((member) => member.changePercent >= 3).length;
    const positiveFlowCount = selectedMembers.filter((member) => member.netFlow > 0).length;
    const totalAmount = selectedMembers.reduce((sum, member) => sum + member.amount, 0) || 1;
    const coreAmountShare =
      selectedMembers
        .slice()
        .sort((a, b) => b.amount - a.amount)
        .slice(0, 3)
        .reduce((sum, member) => sum + member.amount, 0) / totalAmount;
    return {
      advancers,
      advPct: (advancers / total) * 100,
      strongCount,
      positiveFlowCount,
      positiveFlowPct: (positiveFlowCount / total) * 100,
      coreAmountShare: coreAmountShare * 100,
    };
  }, [selectedMembers]);

  const structureRoles = useMemo(() => {
    if (!selectedTopic) return [] as StructureRole[];
    const topAmountMember = [...selectedMembers].sort((a, b) => b.amount - a.amount || b.netFlow - a.netFlow)[0];
    const topMomentumMember = [...selectedMembers].sort((a, b) => b.changePercent - a.changePercent || b.netFlow - a.netFlow)[0];
    const highlighted = [...selectedTopic.highlightedStocks].sort((a, b) => b.lbc - a.lbc);
    const leader = highlighted[0];
    const follower = highlighted.find((item) => item.code !== leader?.code) || topMomentumMember;

    const roles: StructureRole[] = [];
    if (leader) {
      roles.push({
        role: '龙头',
        name: leader.name,
        code: leader.code,
        note: `${boardHeightLabel(leader.lbc)}，打开板块高度，情绪锚点最明确`,
      });
    }
    if (topAmountMember) {
      roles.push({
        role: '中军',
        name: topAmountMember.name,
        code: topAmountMember.code,
        note: `成交额 ${formatYi(topAmountMember.amount)}，${topAmountMember.netFlow >= 0 ? '承接资金较强' : '容量承接仍待确认'}`,
      });
    }
    if (follower) {
      const followerNote =
        highlighted.some((item) => item.code === follower.code)
          ? `${boardHeightLabel((follower as (typeof highlighted)[number]).lbc)}，处于扩散补位阶段`
          : `${formatPercent((follower as TrendMember).changePercent, 1)}，低位资金开始跟随`;
      roles.push({
        role: '补涨',
        name: follower.name,
        code: follower.code,
        note: followerNote,
      });
    }
    return roles;
  }, [selectedMembers, selectedTopic]);

  const ladderRows = useMemo(
    () => buildLadderRows(data.stockTags, selectedMembers),
    [data.stockTags, selectedMembers]
  );

  function toggleSort(key: MemberSortKey) {
    setSortBy((current) => (current.key === key ? { key, dir: current.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }));
  }

  if (topics.length === 0) {
    return (
      <div className="rounded-[24px] border border-dashed border-border/70 bg-background/35 px-5 py-10 text-center text-sm text-muted-foreground">
        暂无趋势题材数据
      </div>
    );
  }

  const hoverTopic = hover ? chartTopics.find((item) => item.topic.id === hover.topicId) : null;
  const hoverPoint = hover && hoverTopic ? hoverTopic.points[hover.pointIndex] : null;

  return (
    <section className="overflow-hidden rounded-[28px] border border-border/70 bg-background/80 shadow-[0_18px_40px_rgba(15,23,42,0.06)]">
      <div className="border-b border-border/60 px-5 py-3.5">
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr),auto] xl:items-start">
          <div>
            <div className="text-base font-semibold text-foreground">题材趋势</div>
            <div className="mt-1 max-w-[760px] text-xs leading-5 text-muted-foreground">
              1D/3D 对比已切到真实板块资金流时序。当前榜单先基于现有候选池重排活跃度 Top10，后续可再替换更完整母样本。
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
              <span>基础样本 {data.sampleStats.baseCount}</span>
              <span className="h-3 w-px bg-border/60" />
              <span>事件补入 {data.sampleStats.eventAddedCount}</span>
              <span className="h-3 w-px bg-border/60" />
              <span>最终候选 {data.sampleStats.finalCount}</span>
            </div>
            {data.droppedBoards && data.droppedBoards.length > 0 ? (
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-amber-700/90 dark:text-amber-300/80">
                <span>近5日跌出候选:</span>
                {data.droppedBoards.map((board) => (
                  <span key={board.name}>
                    {board.name}
                    <span className="text-muted-foreground">（{board.lastSeen}）</span>
                  </span>
                ))}
              </div>
            ) : null}
          </div>
          <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
            {pulseSummary.map((item) => (
              <div key={item.label} className="rounded-[18px] border border-border/60 bg-background px-3 py-2.5">
                <div className="text-[11px] text-muted-foreground">{item.label}</div>
                <div className="mt-1 text-lg font-semibold leading-none text-foreground">{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="p-4 pt-3">
        <div className="mb-4 grid gap-4 xl:grid-cols-[1.08fr,0.92fr] xl:items-stretch">
          <div className="flex h-full flex-col overflow-hidden rounded-[26px] border border-border/70 bg-background shadow-[0_12px_28px_rgba(15,23,42,0.04)]">
            <div className="border-b border-border/60 px-4 py-3.5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-foreground">活跃板块排行榜</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {viewMode === 'today'
                      ? '按当日综合强度重排，优先回答“现在谁最活跃”。'
                      : '切到 3 日趋势排行，仅按3日强度斜率排序。'}
                  </div>
                </div>
                <div className="inline-flex rounded-full border border-border/60 bg-background p-1 shadow-sm">
                  {([
                    ['today', '今日截面'],
                    ['trend', '趋势视角'],
                  ] as const).map(([mode, label]) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setViewMode(mode)}
                      className={cn(
                        'rounded-full px-3 py-1.5 text-[11px] transition-all',
                        viewMode === mode
                        ? 'bg-foreground text-background shadow-[0_8px_20px_rgba(15,23,42,0.16)]'
                          : 'text-muted-foreground hover:text-foreground'
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex-1 overflow-auto divide-y divide-border/50">
              {activeTopicInsights.map((item, index) => {
                const active = item.topic.id === selectedTopic?.id;
                return (
                  <button
                    key={`insight-${item.topic.id}`}
                    type="button"
                    onClick={() => setSelectedId(item.topic.id)}
                    className={cn(
                      'grid w-full gap-3 px-4 py-2.5 text-left transition-all sm:grid-cols-[minmax(0,1.85fr),repeat(4,minmax(0,0.72fr)),auto]',
                      index === 0 && !active && 'bg-rose-50/55',
                      index === 1 && !active && 'bg-orange-50/45',
                      index === 2 && !active && 'bg-amber-50/40',
                      active
                        ? 'bg-muted/30 shadow-[inset_3px_0_0_rgb(249_115_22)]'
                        : 'hover:bg-muted/16'
                    )}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.topic.color }} />
                        <span className="truncate text-sm font-semibold text-foreground">{item.topic.name}</span>
                        {item.topic.relatedPlates && item.topic.relatedPlates.length > 0 ? (
                          <span className="shrink-0 rounded-full bg-muted/40 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                            同题材 {item.topic.relatedPlates.length}
                          </span>
                        ) : null}
                        <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-medium shadow-sm', PULSE_STYLES[item.state])}>{item.state}</span>
                      </div>
                      <div className="mt-1 line-clamp-1 text-xs leading-5 text-muted-foreground">
                        {viewMode === 'today'
                          ? `上涨占比 ${item.breadthPct.toFixed(0)}% · 涨停占比 ${item.ztPct.toFixed(1)}%`
                          : `${item.stateReason} · ${rankChip(item.rankDelta3d)}`}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">{viewMode === 'today' ? '综合强度' : '最新资金强度'}</div>
                      <div className="mt-1 text-sm font-semibold text-foreground">
                        {viewMode === 'today' ? item.topic.score.toFixed(1) : item.latest.strengthScore.toFixed(1)}
                      </div>
                    </div>
                    <div>
                      {viewMode === 'today' ? (
                        <>
                          <div className="text-xs text-muted-foreground">今日资金</div>
                          <div className={cn('mt-1 text-sm font-semibold', item.topic.moneyFlow >= 0 ? 'text-rose-600' : 'text-emerald-600')}>
                            {formatSignedYi(item.topic.moneyFlow)}
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="text-xs text-muted-foreground">1日强度变化</div>
                          <div className={cn('mt-1 text-sm font-semibold', item.scoreDelta1d >= 0 ? 'text-rose-600' : 'text-emerald-600')}>
                            {formatSignedPoints(item.scoreDelta1d, '')}
                          </div>
                        </>
                      )}
                    </div>
                    <div>
                      {viewMode === 'today' ? (
                        <>
                          <div className="text-xs text-muted-foreground">阶段涨跌</div>
                          <div className={cn('mt-1 text-sm font-semibold', item.topic.changePct >= 0 ? 'text-rose-600' : 'text-emerald-600')}>
                            {formatPercent(item.topic.changePct, 1)}
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="text-xs text-muted-foreground">3日强度斜率</div>
                          <div className={cn('mt-1 text-sm font-semibold', (item.scoreSlope3d ?? 0) >= 0 ? 'text-rose-600' : 'text-emerald-600')}>
                            {formatSignedPoints(item.scoreSlope3d, '')}
                          </div>
                        </>
                      )}
                    </div>
                    <div>
                      {viewMode === 'today' ? (
                        <>
                          <div className="text-xs text-muted-foreground">涨停家数</div>
                          <div className="mt-1 text-sm font-semibold text-foreground">{item.topic.ztCount}家</div>
                        </>
                      ) : (
                        <>
                          <div className="text-xs text-muted-foreground">近3日净流入</div>
                          <div className={cn('mt-1 text-sm font-semibold', (item.flowSum3d ?? 0) >= 0 ? 'text-rose-600' : 'text-emerald-600')}>
                            {formatSignedYiOptional(item.flowSum3d)}
                          </div>
                        </>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-muted-foreground">{viewMode === 'today' ? '历史状态' : '历史位次'}</div>
                      {viewMode === 'today' ? (
                        <div className={cn('mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium', PULSE_STYLES[item.previousState])}>{item.previousState}</div>
                      ) : (
                        <div className="mt-1 text-sm font-semibold text-foreground">#{item.latestRank}</div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {selectedInsight ? (
          <div className="h-full overflow-hidden rounded-[26px] border border-border/70 bg-background shadow-[0_12px_28px_rgba(15,23,42,0.04)]">
            <div className="border-b border-border/60 px-4 py-3.5">
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-sm font-semibold text-foreground">板块轨迹详情 · {selectedInsight.topic.name}</div>
                  <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-medium shadow-sm', PULSE_STYLES[selectedInsight.state])}>
                    {selectedInsight.state}
                  </span>
                </div>
                <div className="mt-1 text-xs leading-5 text-muted-foreground">{selectedInsight.stateReason}</div>
              </div>
              <div className="p-4">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-[18px] border border-border/60 px-3.5 py-3">
                    <div className="text-xs text-muted-foreground">当前资金强度</div>
                    <strong className="mt-1.5 block text-xl font-semibold text-foreground">{selectedInsight.latest.strengthScore.toFixed(1)}</strong>
                    <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>今日主力</span>
                      <span className={selectedInsight.topic.moneyFlow >= 0 ? 'text-rose-600' : 'text-emerald-600'}>{formatSignedYi(selectedInsight.topic.moneyFlow)}</span>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>今日综合强度</span>
                      <span className="text-foreground">{selectedInsight.topic.score.toFixed(1)}</span>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>涨停家数</span>
                      <span className="text-foreground">{selectedInsight.topic.ztCount}家</span>
                    </div>
                  </div>
                  <div className="rounded-[18px] border border-border/60 px-3.5 py-3">
                    <div className="text-xs text-muted-foreground">3日强度斜率</div>
                    <strong className={cn('mt-1.5 block text-xl font-semibold', (selectedInsight.scoreSlope3d ?? 0) >= 0 ? 'text-rose-600' : 'text-emerald-600')}>
                      {formatSignedPoints(selectedInsight.scoreSlope3d, '')}
                    </strong>
                    <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>近3日净流入</span>
                      <span className={cn(selectedInsight.flowSum3d == null || selectedInsight.flowSum3d >= 0 ? 'text-rose-600' : 'text-emerald-600')}>
                        {formatSignedYiOptional(selectedInsight.flowSum3d)}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>历史位次</span>
                      <span className="text-foreground">#{selectedInsight.latestRank}</span>
                    </div>
                  </div>
                  <div className="rounded-[18px] border border-border/60 px-3.5 py-3">
                    <div className="text-xs text-muted-foreground">扩散指标</div>
                    <strong className="mt-1.5 block text-xl font-semibold text-foreground">{selectedInsight.breadthPct.toFixed(0)}%</strong>
                    <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>涨停占比</span>
                      <span className="text-foreground">{selectedInsight.ztPct.toFixed(1)}%</span>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>阶段涨跌</span>
                      <span className={selectedInsight.topic.changePct >= 0 ? 'text-rose-600' : 'text-emerald-600'}>{formatPercent(selectedInsight.topic.changePct, 1)}</span>
                    </div>
                  </div>
                </div>
                <div className="mt-4 space-y-4">
                  <div className="text-xs text-muted-foreground">近 {Math.min(selectedInsight.points.length, 10)} 个交易日资金强度轨迹</div>
                  {(() => {
                    const sparkPoints = selectedInsight.points.slice(-10);
                    const scoreValues = sparkPoints.map((point) => point.strengthScore);
                    const scoreMin = Math.min(...scoreValues);
                    const scoreMax = Math.max(...scoreValues);
                    const scoreRange = scoreMax - scoreMin || 1;
                    const previewIndex = detailHoverIndex ?? Math.max(0, sparkPoints.length - 1);
                    const activePoint = detailHoverIndex !== null ? sparkPoints[detailHoverIndex] : null;
                    const activePrev = detailHoverIndex !== null ? sparkPoints[Math.max(0, detailHoverIndex - 1)] : null;
                    const scoreY = (value: number) => 108 - ((value - scoreMin) / scoreRange) * 94;
                    const sparkX = (index: number) => (sparkPoints.length <= 1 ? 160 : (320 * index) / (sparkPoints.length - 1));
                    const regressionPoints = sparkPoints
                      .map((point, index) => ({ point, index }))
                      .filter(({ point }) => !point.excluded)
                      .slice(-4);
                    const regression = linearRegressionFit(regressionPoints.map(({ point }) => point.strengthScore));
                    const regressionLine = regression && regressionPoints.length === 4
                      ? {
                          x1: sparkX(regressionPoints[0].index),
                          y1: scoreY(regression.intercept),
                          x2: sparkX(regressionPoints[3].index),
                          y2: scoreY(regression.intercept + regression.slope * 3),
                        }
                      : null;
                    const activeState = activePoint
                      ? classifyPulse(
                          { ...selectedInsight.topic, score: activePoint.strengthScore, moneyFlow: activePoint.mainNetInflow },
                          sparkPoints.slice(0, previewIndex + 1)
                        ).state
                      : null;

                    return (
                      <>
                        <div className="relative" onMouseLeave={() => setDetailHoverIndex(null)}>
                          <svg viewBox="0 0 320 132" className="h-[136px] w-full">
                            <text x="2" y="10" fontSize="8" fill="currentColor" opacity="0.5">资金强度</text>
                            <path
                              d={sparkPoints
                                .map((point, index) => {
                                  const x = sparkX(index);
                                  return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${scoreY(point.strengthScore).toFixed(1)}`;
                                })
                                .join(' ')}
                              fill="none"
                              stroke={selectedInsight.topic.color}
                              strokeWidth="3"
                              strokeLinecap="round"
                            />
                            {regressionLine ? (
                              <line
                                x1={regressionLine.x1}
                                y1={regressionLine.y1}
                                x2={regressionLine.x2}
                                y2={regressionLine.y2}
                                stroke="#64748b"
                                strokeWidth="1.5"
                                strokeDasharray="5 4"
                                opacity="0.85"
                              />
                            ) : null}
                            {sparkPoints.map((point, index, arr) => {
                              const x = sparkX(index);
                              const y = scoreY(point.strengthScore);
                              const recentStart = Math.max(0, arr.length - 5);
                              const isRecent = index >= recentStart;
                              const state = classifyPulse(
                                { ...selectedInsight.topic, score: point.strengthScore, moneyFlow: point.mainNetInflow },
                                arr.slice(0, index + 1)
                              ).state;
                              const isActive = index === previewIndex;
                              return (
                                <g key={`spark-${point.date}`}>
                                  {isRecent ? <line x1={x} y1="14" x2={x} y2="110" stroke="currentColor" opacity={isActive ? 0.12 : 0.06} strokeDasharray="3 5" /> : null}
                                  <circle
                                    cx={x}
                                    cy={y}
                                    r={isRecent ? (isActive ? 5.6 : 4.6) : index === arr.length - 1 ? 4.5 : 3}
                                    fill={isRecent ? '#ffffff' : selectedInsight.topic.color}
                                    stroke={isRecent ? PULSE_COLORS[state] : selectedInsight.topic.color}
                                    strokeWidth={isRecent ? (isActive ? 3 : 2.2) : 0}
                                    onMouseEnter={() => setDetailHoverIndex(index)}
                                  />
                                  {(index === 0 || index === arr.length - 1 || index % 3 === 0) && (
                                    <text x={x} y="126" textAnchor="middle" fontSize="9" fill="currentColor" opacity="0.55">
                                      {shortDate(point.date)}
                                    </text>
                                  )}
                                  {isRecent && isActive ? (
                                    <text x={x} y={Math.max(14, y - 10)} textAnchor="middle" fontSize="9" fill="currentColor" opacity="0.82">
                                      {state}
                                    </text>
                                  ) : null}
                                </g>
                              );
                            })}
                          </svg>
                          {activePoint && activeState ? (
                            <div className="pointer-events-none absolute right-2 top-2 rounded-[16px] border border-border/70 bg-background/95 px-3 py-2 text-[11px] shadow-[0_16px_30px_rgba(15,23,42,0.12)] backdrop-blur-sm">
                              <div className="flex items-center gap-2">
                                <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-medium', PULSE_STYLES[activeState])}>{activeState}</span>
                                <span className="text-muted-foreground">{shortDate(activePoint.date)}</span>
                              </div>
                              <div className="mt-1 text-foreground">{buildStateNote(activePoint, activePrev)}</div>
                              <div className="mt-1 text-muted-foreground">
                                资金强度 {activePoint.strengthScore.toFixed(1)} · 净流入 {formatSignedYi(activePoint.mainNetInflow)} · 净占比 {formatPercent(activePoint.mainNetInflowRatio, 1)}
                              </div>
                            </div>
                          ) : null}
                        </div>
                        <div className="flex flex-wrap gap-3 text-[11px] text-muted-foreground">
                          <span>彩环点: 近5日状态</span>
                        </div>
                      </>
                    );
                  })()}
                  <div className="border-t border-border/60 pt-4">
                    <div className="text-xs text-muted-foreground">内部梯队与扩散</div>
                    <div className="mt-3 grid gap-4 xl:grid-cols-2">
                      <div className="space-y-2.5">
                        {ladderRows.map((row) => (
                          <div key={row.label} className="grid items-center gap-2.5 grid-cols-[56px,1fr,48px]">
                            <div className="text-[11px] text-muted-foreground">{row.label}</div>
                            <div className="h-2.5 overflow-hidden rounded-full bg-muted/35">
                              <div className="h-full rounded-full bg-[linear-gradient(90deg,#fb923c,#f97316)] shadow-[0_6px_18px_rgba(249,115,22,0.18)]" style={{ width: `${row.width}%` }} />
                            </div>
                            <div className="text-xs font-medium text-foreground">{row.count} 家</div>
                          </div>
                        ))}
                        <div className="space-y-1 border-t border-border/50 pt-3 text-[11px] text-muted-foreground">
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                            <span>上涨家数 {expansionMetrics.advancers} / {selectedMembers.length || '--'}</span>
                            <span className="h-3 w-px bg-border/60" />
                            <span>净流入为正 {expansionMetrics.positiveFlowCount} / {selectedMembers.length || '--'}</span>
                          </div>
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                            <span>涨幅超 3% {expansionMetrics.strongCount} 家</span>
                            <span className="h-3 w-px bg-border/60" />
                            <span>前三成交占比 {expansionMetrics.coreAmountShare.toFixed(0)}%</span>
                          </div>
                        </div>
                      </div>
                      <div className="max-h-[236px] overflow-y-auto pr-1">
                        <div className="grid gap-2">
                        {structureRoles.map((role) => (
                          <StockPreviewTooltip key={`${role.role}-${role.name}`} code={role.code} name={role.name} summary={role.note}>
                            <button
                              type="button"
                              onClick={() => role.code && onSelectStock?.(role.code, role.name)}
                              className="rounded-[14px] border border-border/60 bg-muted/10 px-2.5 py-2 text-left transition-all hover:-translate-y-[1px] hover:border-orange-300/70 hover:shadow-[0_12px_28px_rgba(249,115,22,0.08)]"
                            >
                              <div className="flex items-center justify-between gap-2">
                                <div className="flex min-w-0 items-center gap-1.5">
                                  <div className="truncate text-sm font-semibold text-foreground">{role.name}</div>
                                  <span className="shrink-0 rounded-full bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">{role.role}</span>
                                </div>
                                {role.code ? <div className="shrink-0 text-[10px] text-muted-foreground">{role.code}</div> : null}
                              </div>
                              <div className="mt-1 line-clamp-1 text-[11px] leading-4 text-muted-foreground">{role.note}</div>
                            </button>
                          </StockPreviewTooltip>
                        ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="overflow-hidden rounded-[26px] border border-border/70 bg-background shadow-[0_12px_28px_rgba(15,23,42,0.04)]">
          <div className="border-b border-border/60 px-4 py-3.5">
            <div className="text-sm font-semibold text-foreground">历史资金强度时序</div>
            <div className="mt-1 text-xs text-muted-foreground">
              柱体: 每日资金强度（同日候选百分位口径）；折线: 净流入占比 EXPMA(3)，跨板块可比。
            </div>
          </div>
          <div className="relative overflow-x-auto">
            <svg viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`} className="min-w-[980px] w-full" onMouseLeave={() => setHover(null)}>
              <rect x={PAD.left} y={PAD.top} width={SVG_WIDTH - PAD.left - PAD.right} height={yForStrength(trendCfg.zones.main) - PAD.top} fill="rgba(255,110,128,0.04)" rx="24" />
              <rect x={PAD.left} y={yForStrength(trendCfg.zones.main)} width={SVG_WIDTH - PAD.left - PAD.right} height={yForStrength(trendCfg.zones.strong) - yForStrength(trendCfg.zones.main)} fill="rgba(251,146,60,0.045)" rx="24" />
              <rect x={PAD.left} y={yForStrength(trendCfg.zones.strong)} width={SVG_WIDTH - PAD.left - PAD.right} height={yForStrength(trendCfg.zones.watch) - yForStrength(trendCfg.zones.strong)} fill="rgba(250,204,21,0.04)" rx="24" />
              <rect x={PAD.left} y={yForStrength(trendCfg.zones.watch)} width={SVG_WIDTH - PAD.left - PAD.right} height={barBaseY() - yForStrength(trendCfg.zones.watch)} fill="rgba(148,163,184,0.04)" rx="24" />

              <text x={PAD.left + 10} y={PAD.top + 14} fontSize="9" fill="currentColor" opacity="0.46">主升区</text>
              <text x={PAD.left + 10} y={yForStrength(trendCfg.zones.main) + 14} fontSize="9" fill="currentColor" opacity="0.42">强势区</text>
              <text x={PAD.left + 10} y={yForStrength(trendCfg.zones.strong) + 14} fontSize="9" fill="currentColor" opacity="0.38">观察区</text>
              <text x={PAD.left + 10} y={yForStrength(trendCfg.zones.watch) + 14} fontSize="9" fill="currentColor" opacity="0.36">冷却区</text>
              <text x={SVG_WIDTH - PAD.right - 10} y={PAD.top + 14} fontSize="9" textAnchor="end" fill="currentColor" opacity="0.46">
                实线 = 净流入板块 · 虚线 = 净流出板块
              </text>

              {yTicks.map((value) => (
                <g key={value}>
                  <line x1={PAD.left} y1={yForStrength(value)} x2={SVG_WIDTH - PAD.right} y2={yForStrength(value)} stroke="rgba(148,163,184,0.18)" strokeDasharray="5 8" />
                  <text x={10} y={yForStrength(value) + 4} fontSize="9" fill="currentColor" opacity="0.52">
                    {value}
                  </text>
                </g>
              ))}

              {expmaTicks.map((value) => (
                <g key={`expma-${value.toFixed(4)}`}>
                  <text x={SVG_WIDTH - PAD.right + 12} y={yForExpma(value) + 4} fontSize="9" fill="#64748b" opacity="0.82">
                    {`${value >= 0 ? '+' : ''}${value.toFixed(1)}%`}
                  </text>
                </g>
              ))}

              {xLabels.map((label, index) => (
                <g key={label}>
                  <line x1={xFor(index, xLabels.length)} y1={PAD.top} x2={xFor(index, xLabels.length)} y2={SVG_HEIGHT - PAD.bottom} stroke="rgba(148,163,184,0.08)" />
                  {(index === 0 || index === xLabels.length - 1 || index % 2 === 0) && (
                    <text x={xFor(index, xLabels.length)} y={SVG_HEIGHT - 14} textAnchor="middle" fontSize="9" fill="currentColor" opacity="0.56">
                      {shortDate(label)}
                    </text>
                  )}
                </g>
              ))}

              {hover ? (
                <line
                  x1={xFor(hover.pointIndex, xLabels.length)}
                  y1={PAD.top}
                  x2={xFor(hover.pointIndex, xLabels.length)}
                  y2={SVG_HEIGHT - PAD.bottom}
                  stroke="rgba(148,163,184,0.4)"
                  strokeDasharray="3 4"
                />
              ) : null}

              {(() => {
                // 柱体始终绑定当前选中板块，与右侧近10日轨迹保持同一对象。
                const barTopicId = selectedTopic?.id ?? null;
                const barEntry = chartTopics.find(({ topic }) => topic.id === barTopicId);
                if (!barEntry || barEntry.points.length === 0) return null;
                const { topic: barTopic, points: barHistory } = barEntry;
                // 主升区进出事件：相邻两日跨越 SCORE_ZONE_MAIN 视为事件点
                const events = barHistory
                  .map((point, index) => {
                    const prev = barHistory[index - 1];
                    if (!prev) return null;
                    if (prev.strengthScore < trendCfg.zones.main && point.strengthScore >= trendCfg.zones.main) return { index, kind: 'in' as const };
                    if (prev.strengthScore >= trendCfg.zones.main && point.strengthScore < trendCfg.zones.main) return { index, kind: 'out' as const };
                    return null;
                  })
                  .filter((event): event is { index: number; kind: 'in' | 'out' } => event !== null);
                return barHistory.map((point, index) => {
                  const width = Math.max(7, (SVG_WIDTH - PAD.left - PAD.right) / Math.max(barHistory.length, 20) - 10);
                  const x = xFor(index, barHistory.length) - width / 2;
                  const center = x + width / 2;
                  const active = hover?.topicId === barTopic.id && hover.pointIndex === index;
                  const event = events.find((item) => item.index === index);
                  const markerY = Math.max(PAD.top + 12, barTopFor(point.strengthScore) - 8);
                  return (
                    <g key={`bar-${barTopic.id}-${point.date}`}>
                      <rect
                        x={x}
                        y={barTopFor(point.strengthScore)}
                        width={width}
                        height={barBaseY() - barTopFor(point.strengthScore)}
                        rx="4"
                        fill={barTopic.color}
                        fillOpacity={active ? 0.24 : 0.1}
                        stroke={active ? 'rgba(255,255,255,0.75)' : 'none'}
                        strokeWidth={active ? 1 : 0}
                      />
                      {event ? (
                        <>
                          <polygon
                            points={
                              event.kind === 'in'
                                ? `${center},${markerY - 5} ${center - 4.5},${markerY + 3} ${center + 4.5},${markerY + 3}`
                                : `${center},${markerY + 3} ${center - 4.5},${markerY - 5} ${center + 4.5},${markerY - 5}`
                            }
                            fill={event.kind === 'in' ? '#e11d48' : '#64748b'}
                          />
                          <text
                            x={center}
                            y={event.kind === 'in' ? markerY - 8 : markerY + 13}
                            textAnchor="middle"
                            fontSize="8.5"
                            fill={event.kind === 'in' ? '#e11d48' : '#64748b'}
                            opacity="0.9"
                          >
                            {event.kind === 'in' ? '入主升' : '出主升'}
                          </text>
                        </>
                      ) : null}
                    </g>
                  );
                });
              })()}

              {chartTopics.map(({ topic, points }) => {
                const active = topic.id === selectedTopic?.id;
                const path = linePath(points, yForExpma);
                return (
                  <g key={topic.id}>
                    <path
                      d={path}
                      fill="none"
                      stroke={topic.color}
                      strokeWidth={active ? 3.2 : 1.5}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeDasharray={active ? undefined : topic.flow === 'out' ? '10 10' : undefined}
                      opacity={active ? 0.98 : 0.22}
                    />
                    {points.map((point, index) => {
                      const isHover = hover?.topicId === topic.id && hover.pointIndex === index;
                      return (
                        <g key={`${topic.id}-${point.date}`}>
                          <circle
                            cx={xFor(index, points.length)}
                            cy={yForExpma(point.expmaRatioPct)}
                            r={active ? (index === points.length - 1 ? 6.6 : 4.2) : 2.8}
                            fill={topic.color}
                            fillOpacity={active ? 1 : 0.42}
                            stroke="white"
                            strokeWidth={isHover || active ? 1.5 : 1}
                            onMouseEnter={() => setHover({ topicId: topic.id, pointIndex: index })}
                            onClick={() => setSelectedId(topic.id)}
                          />
                        </g>
                      );
                    })}
                  </g>
                );
              })}

              {chartTopics.map(({ topic }, index) => {
                const active = topic.id === selectedTopic?.id;
                const y = endLabelPosition(index, endPoints);
                return (
                  <g key={`${topic.id}-label`} onClick={() => setSelectedId(topic.id)}>
                    <text
                      x={SVG_WIDTH - PAD.right + 12}
                      y={y}
                      fontSize={active ? 11 : 10}
                      fill={topic.color}
                      opacity={active ? 1 : 0.34}
                      fontWeight={active ? 700 : 500}
                    >
                      {topic.name}
                    </text>
                  </g>
                );
              })}
            </svg>

            {hoverPoint && hoverTopic ? (
              <div className="pointer-events-none absolute right-3 top-3 rounded-[22px] border border-border/70 bg-background/95 px-3.5 py-3 text-xs shadow-[0_18px_36px_rgba(15,23,42,0.12)] backdrop-blur-sm">
                <div className="font-medium text-foreground">{hoverTopic.topic.name}</div>
                <div className="mt-1 text-muted-foreground">{hoverPoint.date}</div>
                <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5">
                  <div className="text-muted-foreground">净占比 EXPMA(3)</div>
                  <div className="text-right text-foreground">{formatPercent(hoverPoint.expmaValue, 2)}</div>
                  <div className="text-muted-foreground">日资金强度</div>
                  <div className="text-right text-foreground">{hoverPoint.strengthScore.toFixed(1)}</div>
                  <div className="text-muted-foreground">主力净流入</div>
                  <div className={cn('text-right', hoverPoint.mainNetInflow >= 0 ? 'text-rose-600' : 'text-emerald-600')}>{formatSignedYi(hoverPoint.mainNetInflow)}</div>
                  <div className="text-muted-foreground">阶段</div>
                  <div className="text-right text-muted-foreground">{stageForScore(hoverPoint.strengthScore)}</div>
                </div>
                <div className="mt-3 border-t border-border/60 pt-2.5">
                  <div className="mb-1 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Flow Mix</div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                    <div className="text-muted-foreground">主力净占比</div>
                    <div className="text-right text-foreground">{formatPercent(hoverPoint.mainNetInflowRatio, 2)}</div>
                    <div className="text-muted-foreground">超大单</div>
                    <div className="text-right text-foreground">{formatSignedYi(hoverPoint.superLargeNetInflow)}</div>
                    <div className="text-muted-foreground">大单</div>
                    <div className="text-right text-foreground">{formatSignedYi(hoverPoint.largeNetInflow)}</div>
                    <div className="text-muted-foreground">中小单</div>
                    <div className="text-right text-foreground">{formatSignedYi(hoverPoint.midNetInflow + hoverPoint.smallNetInflow)}</div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {selectedTopic ? (
        <div className="border-t border-border/60 px-5 py-4">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-3">
                <span className="h-3.5 w-3.5 rounded-full" style={{ backgroundColor: selectedTopic.color }} />
                <div className="text-lg font-semibold text-foreground">
                  {selectedTopic.name} · {selectedTopic.date}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-sm">
                <span className={cn('rounded-full px-2.5 py-0.5 font-medium', FLOW_META[selectedTopic.flow].badge)}>
                  {FLOW_META[selectedTopic.flow].label}
                </span>
                <span className={cn('rounded-full px-2.5 py-0.5 font-medium', PHASE_STYLES[selectedTopic.phase])}>{selectedTopic.phase}</span>
                <span className="rounded-full bg-muted/30 px-2.5 py-0.5 text-muted-foreground">综合强度 {selectedTopic.score.toFixed(1)}</span>
                <span className={cn('rounded-full px-2.5 py-0.5', selectedTopic.changePct >= 0 ? 'bg-rose-50 text-rose-600 dark:bg-rose-950/30 dark:text-rose-300' : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-300')}>
                  阶段涨跌 {formatPercent(selectedTopic.changePct)}
                </span>
              </div>
              {selectedTopic.relatedPlates && selectedTopic.relatedPlates.length > 0 ? (
                <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                  <span>同题材板块</span>
                  {selectedTopic.relatedPlates.map((name) => (
                    <span key={name} className="rounded-full bg-muted/40 px-2 py-0.5">{name}</span>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="grid w-full gap-3 text-sm sm:grid-cols-3 xl:max-w-[380px]">
              <div>
                <div className="text-muted-foreground">涨停家数</div>
                <div className="mt-1 text-sm font-semibold text-foreground">{selectedTopic.ztCount}家</div>
              </div>
              <div>
                <div className="text-muted-foreground">资金流</div>
                <div className={cn('mt-1 text-sm font-semibold', selectedTopic.moneyFlow >= 0 ? 'text-rose-600' : 'text-emerald-600')}>
                  {formatSignedYi(selectedTopic.moneyFlow)}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">上涨占比</div>
                <div className="mt-1 text-sm font-semibold text-foreground">{formatRatio(selectedTopic.breadth)}</div>
              </div>
            </div>
          </div>

          <div className="mt-4 overflow-hidden rounded-[22px] border border-border/60 bg-background/60">
            <div className="max-h-[500px] overflow-auto">
              <table className="w-full text-left">
                <thead className="sticky top-0 bg-muted/20 text-muted-foreground backdrop-blur">
                  <tr className="text-sm">
                    <th className="px-5 py-3.5 font-medium">
                      <button type="button" className="hover:text-foreground" onClick={() => toggleSort('rank')}>
                        排名
                      </button>
                    </th>
                    <th className="px-5 py-3.5 font-medium">代码</th>
                    <th className="px-5 py-3.5 font-medium">名称</th>
                    <th className="px-5 py-3.5 font-medium">
                      <button type="button" className="hover:text-foreground" onClick={() => toggleSort('changePercent')}>
                        涨跌幅
                      </button>
                    </th>
                    <th className="px-5 py-3.5 font-medium">
                      <button type="button" className="hover:text-foreground" onClick={() => toggleSort('amount')}>
                        成交额
                      </button>
                    </th>
                    <th className="px-5 py-3.5 font-medium">
                      <button type="button" className="hover:text-foreground" onClick={() => toggleSort('netFlow')}>
                        资金净流入
                      </button>
                    </th>
                    <th className="px-5 py-3.5 font-medium">
                      <button type="button" className="hover:text-foreground" onClick={() => toggleSort('turnoverRate')}>
                        换手率
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sortedMembers.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-5 py-7 text-center text-sm text-muted-foreground">
                        加载成分股中…
                      </td>
                    </tr>
                  ) : (
                    sortedMembers.map((member, index) => (
                      <tr key={`${selectedTopic.id}-${member.code}`} className="border-t border-border/50 text-sm hover:bg-muted/20">
                        <td className="px-5 py-3 text-foreground">{index + 1}</td>
                        <td className="px-5 py-3 text-muted-foreground">{member.code}</td>
                        <td className="px-5 py-3 font-medium text-foreground">
                          <StockPreviewTooltip code={member.code} name={member.name}>
                            <button
                              type="button"
                              onClick={() => onSelectStock?.(member.code, member.name)}
                              className="cursor-pointer text-left text-foreground hover:text-orange-600"
                            >
                              {member.name}
                            </button>
                          </StockPreviewTooltip>
                          {member.status ? (
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <span className="ml-2 inline-flex rounded-full bg-orange-100 px-2 py-0.5 text-[10px] text-orange-700 dark:bg-orange-950/30 dark:text-orange-300">
                                    {member.status}
                                  </span>
                                </TooltipTrigger>
                                <TooltipContent
                                  side="top"
                                  align="start"
                                  sideOffset={8}
                                  className="max-w-[280px] rounded-2xl border border-orange-200/55 bg-white/88 px-3 py-2.5 text-[12px] leading-5 text-slate-700 shadow-[0_14px_28px_rgba(15,23,42,0.10)] backdrop-blur-sm dark:border-orange-900/40 dark:bg-slate-950/84 dark:text-slate-200"
                                >
                                  <div className="flex items-center gap-2">
                                    <span className="inline-flex rounded-full bg-orange-100/80 px-2 py-0.5 text-[10px] font-semibold text-orange-700 dark:bg-orange-950/30 dark:text-orange-200">
                                      {member.status}
                                    </span>
                                    {member.limitPlate ? (
                                      <span className="text-[11px] text-slate-500/90 dark:text-slate-400">{member.limitPlate}</span>
                                    ) : null}
                                  </div>
                                  <div className="mt-2 text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400/90 dark:text-slate-500">
                                    涨停分析
                                  </div>
                                  <div className="mt-1 whitespace-pre-wrap text-[12px] leading-5 text-slate-700/95 dark:text-slate-200">
                                    {member.limitAnalysis || member.limitPlate || '暂无涨停分析'}
                                  </div>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          ) : null}
                        </td>
                        <td className={cn('px-5 py-3 font-medium', member.changePercent >= 0 ? 'text-rose-600' : 'text-emerald-600')}>
                          {formatPercent(member.changePercent)}
                        </td>
                        <td className="px-5 py-3 text-foreground">{formatYi(member.amount)}</td>
                        <td className={cn('px-5 py-3 font-medium', member.netFlow >= 0 ? 'text-rose-600' : 'text-emerald-600')}>
                          {formatSignedYi(member.netFlow)}
                        </td>
                        <td className="px-5 py-3 text-foreground">{member.turnoverRate.toFixed(1)}%</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
