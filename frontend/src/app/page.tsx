'use client';

import MarketSourceNotice from '@/components/MarketSourceNotice';
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useAuth } from '@/lib/contexts/AuthContext';
import { StockInfo } from '../types';
import { ChartLine, Search, Settings, Info, Bot, LogIn, User, LogOut, Key, Flame, Trophy, Sparkles, RefreshCw, Lock } from 'lucide-react';
import { Button } from '../components/ui/button';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { useAccounts } from '@/lib/contexts/AccountContext';
import { isAfterMarketClose, isTradingTime, yyyymmdd } from '@/lib/market/format';
import { getStrategy } from '@/lib/market/strategy';
import { searchStocks } from '@/lib/api';
import {
  DEFAULT_MARKET_SNAPSHOT,
  loadEmotionSnapshot,
  loadMainlineSnapshot,
  loadMarketSummarySnapshot,
  loadPayoffSnapshot,
  loadTrendSnapshot,
} from '@/lib/market/snapshot';
import type { MarketCardLabel, MarketEmotionPoint, MarketMainlineLane, MarketSnapshot, ReboundPick, RelaySnapshot, ShortEmotionSnapshot } from '@/lib/market/types';
import { isAuthRequiredView, loginUrl, parseHomeView } from '@/lib/authRedirect';
import { StockPreviewTooltip as MarketStockPreviewTooltip } from '@/components/StockPreviewTooltip';

const StockSearch = dynamic(() => import('../components/StockSearch'), { ssr: false });
const StockDetail = dynamic(() => import('../components/StockDetail'), { ssr: false });
const StockChart = dynamic(() => import('../components/StockChart'), { ssr: false });
const AIAnalysis = dynamic(() => import('../components/AIAnalysis'), { ssr: false });
const SavedStocks = dynamic(() => import('../components/SavedStocks'), { ssr: false });
const CacheControl = dynamic(() => import('../components/CacheControl'), { ssr: false });
const ChangePasswordDialog = dynamic(() => import('../components/ChangePasswordDialog'), { ssr: false });
const AccountSwitcher = dynamic(() => import('@/components/AccountSwitcher'), { ssr: false });
const TurnoverMinuteChart = dynamic(() => import('@/components/TurnoverMinuteChart'), { ssr: false });
const SectorTrendTrajectory = dynamic(() => import('@/components/SectorTrendTrajectory'), { ssr: false });
const ShortEmotionChart = dynamic(() => import('@/components/ShortEmotionChart'), { ssr: false });
const IntradayEmotionChart = dynamic(() => import('@/components/IntradayEmotionChart'), { ssr: false });

type HomeViewMode = 'stock' | 'market' | 'topic';

const MODE_STORAGE_KEY = 'alphabot-home-view-mode';
const VIEW_MODE_ORDER: HomeViewMode[] = ['stock', 'market', 'topic'];

type OpportunityMapStageId = 'breakout' | 'leader' | 'adjustment' | 'rotation' | 'weak' | 'collapse';

type OpportunityMapStage = {
  id: OpportunityMapStageId;
  label: string;
  signal: string;
  opportunity: string;
  risk: string;
};

type OpportunityMapAssessment = {
  stage: OpportunityMapStageId;
  evidence: string[];
};

const OPPORTUNITY_MAP_STAGES: OpportunityMapStage[] = [
  { id: 'breakout', label: '板块爆发', signal: '首板扩散，强势股开始连板', opportunity: '只做最早共振的首板、1进2和最强分支。', risk: '回避无板块呼应的独立涨停。' },
  { id: 'leader', label: '核心龙头', signal: '最高标持续打开，资金向核心集中', opportunity: '聚焦龙头、容量中军，等分歧承接或回封。', risk: '回避一致后排补涨。' },
  { id: 'adjustment', label: '龙头调整', signal: '高标断板或震荡，承接强弱待确认', opportunity: '仅做跌而不弱的核心低吸、回封。', risk: '回避失去承接的炸板高标。' },
  { id: 'rotation', label: '题材轮动', signal: '资金切换到低位或新分支', opportunity: '找刚启动、尚未充分轮动的题材。', risk: '回避轮动末端追涨。' },
  { id: 'weak', label: '市场走弱', signal: '情绪重心下移，高标反馈变差', opportunity: '缩仓，只观察抗跌核心与新题材试错。', risk: '回避接力和高位加速。' },
  { id: 'collapse', label: '板块崩溃', signal: '亏钱效应扩散，板块强度坍塌', opportunity: '空仓等待首批止跌并重新爆发的题材。', risk: '回避退潮抄底和弱势反抽。' },
];

const OPPORTUNITY_MAP_POSITIONS = [
  { left: '28%', top: '8%' },
  { left: '72%', top: '8%' },
  { left: '88%', top: '47%' },
  { left: '72%', top: '83%' },
  { left: '28%', top: '83%' },
  { left: '12%', top: '47%' },
] as const;

function assessOpportunityMap(
  emotion: MarketEmotionPoint | null,
  shortEmotion: ShortEmotionSnapshot | null,
  lanes: MarketMainlineLane[],
  relay: RelaySnapshot | null
): OpportunityMapAssessment {
  const value = shortEmotion?.latestValue ?? 0;
  const maxHeight = emotion?.maxHeight ?? 0;
  const activeLanes = lanes.filter((lane) => lane.ztCount > 0).length;
  const emotionEvidence = shortEmotion?.latestValue != null ? `短线情绪 ${value.toFixed(2)}（${shortEmotion.zone || '未分区'}）` : '短线情绪数据待加载';
  const heightEvidence = maxHeight > 0 ? `最高板 ${maxHeight} 板` : '最高板数据待加载';
  const laneEvidence = activeLanes > 0 ? `活跃主线 ${activeLanes} 条` : '主线数据待加载';
  const breaks = relay?.breaksToday.length || 0;

  if (value <= -4) return { stage: 'collapse', evidence: [emotionEvidence, heightEvidence, breaks > 0 ? `当日高标断板 ${breaks} 只` : '亏钱效应优先观察'] };
  if (value < 0) return { stage: 'weak', evidence: [emotionEvidence, heightEvidence, laneEvidence] };
  if (breaks > 0 && maxHeight >= 3) return { stage: 'adjustment', evidence: [heightEvidence, `当日高标断板 ${breaks} 只`, laneEvidence] };
  if (maxHeight >= 5 && activeLanes <= 2) return { stage: 'leader', evidence: [heightEvidence, laneEvidence, emotionEvidence] };
  if (activeLanes >= 3) return { stage: 'rotation', evidence: [laneEvidence, heightEvidence, emotionEvidence] };
  return { stage: 'breakout', evidence: [laneEvidence, heightEvidence, emotionEvidence] };
}

const HOME_VIEW_MODES: Record<HomeViewMode, {
  navLabel: string;
  title: string;
  description: string;
  primary: string;
  ring: string;
  accentSoft: string;
  panelClassName: string;
}> = {
  stock: {
    navLabel: '个股',
    title: '探索股票市场',
    description: '搜索股票，查看实时数据，获取 AI 分析和建议。',
    primary: '#2563eb',
    ring: '#2563eb',
    accentSoft: 'rgba(37, 99, 235, 0.12)',
    panelClassName: 'border-blue-200/70 bg-blue-50/70 dark:border-blue-400/20 dark:bg-blue-400/10',
  },
  market: {
    navLabel: '市场',
    title: '追踪市场主线',
    description: '从指数、情绪、题材和强势股切入，先看盘面，再找机会。',
    primary: '#ea580c',
    ring: '#ea580c',
    accentSoft: 'rgba(234, 88, 12, 0.14)',
    panelClassName: 'border-orange-200/70 bg-orange-50/70 dark:border-orange-400/20 dark:bg-orange-400/10',
  },
  topic: {
    navLabel: '专题',
    title: '浏览专题内容',
    description: '只承接独立专题，不混入市场栏目。',
    primary: '#c026d3',
    ring: '#c026d3',
    accentSoft: 'rgba(192, 38, 211, 0.16)',
    panelClassName: 'border-fuchsia-200/70 bg-gradient-to-r from-amber-50/80 via-rose-50/75 to-fuchsia-50/80 dark:border-fuchsia-400/20 dark:from-amber-400/10 dark:via-rose-400/10 dark:to-fuchsia-400/10',
  },
};

const MARKET_DIAGNOSTICS = [
  {
    label: '趋势',
    toneClassName: 'text-orange-600 dark:text-orange-300',
    borderClassName: 'border-orange-200/80 dark:border-orange-400/20',
  },
  {
    label: '情绪',
    toneClassName: 'text-rose-600 dark:text-rose-300',
    borderClassName: 'border-rose-200/80 dark:border-rose-400/20',
  },
  {
    label: '主线',
    toneClassName: 'text-amber-600 dark:text-amber-300',
    borderClassName: 'border-amber-200/80 dark:border-amber-400/20',
  },
  {
    label: '赚钱效应',
    toneClassName: 'text-fuchsia-600 dark:text-fuchsia-300',
    borderClassName: 'border-fuchsia-200/80 dark:border-fuchsia-400/20',
  },
] as const;

const MARKET_CARD_LABELS = MARKET_DIAGNOSTICS.map((item) => item.label);
const EMPTY_CARD_REFRESH: Record<MarketCardLabel, boolean> = {
  趋势: false,
  情绪: false,
  主线: false,
  赚钱效应: false,
};
const EMPTY_CARD_DETAILS: Record<MarketCardLabel, boolean> = {
  趋势: false,
  情绪: false,
  主线: true,
  赚钱效应: true,
};
const MARKET_TRADING_RELOAD_MS = 60_000;
const RELAY_UNLOCK_POINTS = 1000;

type MarketPageLoadMeta = {
  sessionKey: string;
  lastSyncedAt: number;
};

function toneTextClassName(tone?: 'up' | 'down' | 'normal') {
  if (tone === 'down') return 'text-emerald-600 dark:text-emerald-300';
  if (tone === 'up') return 'text-orange-600 dark:text-orange-300';
  return 'text-foreground';
}

function signedToneClassName(value: number) {
  if (value > 0) return 'text-orange-600 dark:text-orange-300';
  if (value < 0) return 'text-emerald-600 dark:text-emerald-300';
  return 'text-muted-foreground';
}

function formatSignedPct(value: number) {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function boardHeightLabel(lbc: number) {
  if (lbc <= 1) return '首板';
  return `${lbc}板`;
}

function washLabel(minutes: number) {
  return minutes >= 60 ? `洗${(minutes / 60).toFixed(1)}小时` : `洗${minutes}分`;
}

function formatThemes(themes?: string[]) {
  return themes && themes.length > 0 ? themes.slice(0, 2).join('/') : '';
}

function withThemeSummary(summary?: string, themes?: string[]) {
  const themeText = formatThemes(themes);
  if (!themeText) return summary;
  return [`题材：${themeText}`, summary].filter(Boolean).join('\n');
}

function relayRowLabel(label: string) {
  return (
    <span className="w-14 shrink-0 text-[10px] font-medium tracking-wide text-muted-foreground">
      {label}
    </span>
  );
}

type ReboundStatus = '已回封' | '临封' | '修复' | '异动';
const STATUS_ORDER: Record<ReboundStatus, number> = { 已回封: 0, 临封: 1, 修复: 2, 异动: 3 };
const STATUS_COLORS: Record<ReboundStatus, string> = {
  已回封: 'bg-rose-500',
  临封: 'bg-orange-500',
  修复: 'bg-amber-500',
  异动: 'bg-slate-400',
};
const REBOUND_PATTERN_ORDER: Record<ReboundPick['pattern'], number> = {
  连板反包: 0,
  首板反包: 1,
  炸板回封: 2,
};

/** 反包候选的当前状态：已回封看封单/时间，未回封按盘中涨幅分级 */
function reboundStatus(pick: ReboundPick): ReboundStatus {
  if (pick.sealTime != null) return '已回封';
  const change = pick.change;
  const { nearSealPct, repairPct } = getStrategy().rebound;
  if (change != null && change >= nearSealPct) return '临封';
  if (change != null && change >= repairPct) return '修复';
  return '异动';
}

function canAccessRelay(points?: number | null) {
  return (points ?? 0) >= RELAY_UNLOCK_POINTS;
}

function RelayLockedPanel({ points = 0 }: { points?: number }) {
  const missingPoints = Math.max(0, RELAY_UNLOCK_POINTS - points);

  return (
    <div className="rounded-[24px] border border-dashed border-orange-300/70 bg-orange-50/50 p-6 text-center dark:border-orange-400/30 dark:bg-orange-400/10">
      <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-orange-500/10 text-orange-600 dark:text-orange-300">
        <Lock className="h-5 w-5" />
      </div>
      <div className="mt-3 text-sm font-semibold text-foreground">龙头接力 / 异动反包</div>
      <div className="mt-2 text-sm text-muted-foreground">
        该卡片仅对积分大于等于 {RELAY_UNLOCK_POINTS} 的用户开放。
      </div>
      <div className="mt-3 text-xs text-muted-foreground">
        当前积分 {points}，还差 {missingPoints} 积分解锁。
      </div>
    </div>
  );
}

function RelayCyclePanel({
  relay,
  onSelectStock,
}: {
  relay: RelaySnapshot;
  onSelectStock: (code: string, name: string) => void;
}) {
  const { reboundStats } = relay;
  const afterClose = isAfterMarketClose();
  // 候选先按形态分组，组内再按状态强弱和分数排序
  const reboundPicks = [...relay.reboundConfirmed, ...relay.reboundWatching].sort(
    (a, b) =>
      REBOUND_PATTERN_ORDER[a.pattern] - REBOUND_PATTERN_ORDER[b.pattern] ||
      STATUS_ORDER[reboundStatus(a)] - STATUS_ORDER[reboundStatus(b)] ||
      b.score - a.score
  );
  const statusCounts = new Map<ReboundStatus, number>();
  reboundPicks.forEach((pick) => {
    const status = reboundStatus(pick);
    statusCounts.set(status, (statusCounts.get(status) || 0) + 1);
  });
  const STATUS_SUMMARY: Array<[ReboundStatus, number]> = [
    ['已回封', statusCounts.get('已回封') || 0],
    ['临封', statusCounts.get('临封') || 0],
    ['修复', statusCounts.get('修复') || 0],
    ['异动', statusCounts.get('异动') || 0],
  ];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="rounded-[24px] border border-border/70 bg-background/70 p-5">
        <div className="text-sm font-semibold text-foreground">龙头接力</div>
        <div className="mt-1 text-xs text-muted-foreground">
          空间龙头断板日的同题材首板是接力龙头的主要来源；盘中缩圈，次日 1进2 确认。
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
          {relay.promoteRate !== null ? <span className="tabular-nums">晋级率 {relay.promoteRate}%</span> : null}
          <span className="tabular-nums">首板 {relay.firstBoardCount}只</span>
          {relay.aliveLeaders.length > 0 ? (
            <span className="flex flex-wrap items-center gap-1">
              <span>存活</span>
              {relay.aliveLeaders.map((leader) => (
                <MarketStockPreviewTooltip key={leader.code} code={leader.code} name={leader.name}>
                  <button
                    type="button"
                    onClick={() => onSelectStock(leader.code, leader.name)}
                    className="rounded px-1.5 py-0.5 font-medium text-orange-600 hover:bg-muted/60 dark:text-orange-300"
                  >
                    {leader.name}
                    <span className="ml-0.5 text-[10px] text-muted-foreground">{boardHeightLabel(leader.height)}</span>
                    {leader.themes && leader.themes.length > 0 ? (
                      <span className="ml-1 text-[10px] text-muted-foreground">{formatThemes(leader.themes)}</span>
                    ) : null}
                  </button>
                </MarketStockPreviewTooltip>
              ))}
            </span>
          ) : null}
        </div>

        {relay.chain.length > 0 ? (
          <div className="mt-4 space-y-2">
            <div className="text-xs font-medium text-muted-foreground">近{relay.days}日接力链（回看）</div>
            <div className="space-y-1.5">
              {relay.chain.map((link) => (
                <div key={link.date} className="grid grid-cols-[48px_120px_16px_minmax(0,1fr)] items-start gap-x-2 text-xs">
                  <span className="w-12 shrink-0 pt-0.5 text-[10px] tabular-nums text-muted-foreground">
                    {link.date.slice(5)}
                  </span>
                  <div className="min-w-0 flex flex-col gap-1">
                    {link.leaders.map((leader) => (
                      <MarketStockPreviewTooltip key={leader.code} code={leader.code} name={leader.name}>
                        <button
                          type="button"
                          onClick={() => onSelectStock(leader.code, leader.name)}
                          className="w-full overflow-hidden rounded px-1 py-0.5 text-left text-emerald-700 hover:bg-muted/60 dark:text-emerald-300"
                        >
                          <span className="truncate">
                            {leader.name}
                            <span className="ml-0.5 text-[10px] text-muted-foreground">{boardHeightLabel(leader.height)}断</span>
                            {leader.themes && leader.themes.length > 0 ? (
                              <span className="ml-1 text-[10px] text-muted-foreground">{formatThemes(leader.themes)}</span>
                            ) : null}
                          </span>
                        </button>
                      </MarketStockPreviewTooltip>
                    ))}
                  </div>
                  <span className="pt-0.5 text-center text-muted-foreground">→</span>
                  <div className="min-w-0 flex flex-wrap items-center gap-1.5">
                    {link.successors.length === 0 ? (
                      <span className="text-muted-foreground">无接力</span>
                    ) : (
                      link.successors.map((successor) => (
                        <MarketStockPreviewTooltip
                          key={successor.code}
                          code={successor.code}
                          name={successor.name}
                          summary={withThemeSummary(undefined, successor.themes)}
                        >
                          <button
                            type="button"
                            onClick={() => onSelectStock(successor.code, successor.name)}
                            className={`rounded px-1 py-0.5 hover:bg-muted/60 ${
                              successor.becameLeader ? 'text-orange-600 dark:text-orange-300' : 'text-foreground'
                            }`}
                          >
                            {successor.name}
                            <span className="ml-0.5 text-[10px] text-muted-foreground">{boardHeightLabel(successor.maxHeight)}</span>
                            {successor.themes && successor.themes.length > 0 ? (
                              <span className="ml-1 text-[10px] text-muted-foreground">{formatThemes(successor.themes)}</span>
                            ) : null}
                          </button>
                        </MarketStockPreviewTooltip>
                      ))
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {relay.breaksToday.length > 0 ? (
          <div className="mt-4 rounded-xl bg-muted/25 p-3">
            <div className="flex items-start gap-2 text-xs">
              {relayRowLabel(afterClose ? '今日断板' : '今日未封板')}
              <div className="min-w-0 flex-1 flex flex-wrap items-center gap-1.5">
                {relay.breaksToday.map((leader) => (
                  <MarketStockPreviewTooltip key={leader.code} code={leader.code} name={leader.name}>
                    <button
                      type="button"
                      onClick={() => onSelectStock(leader.code, leader.name)}
                      className="rounded px-1.5 py-0.5 font-medium text-emerald-700 hover:bg-muted/60 dark:text-emerald-300"
                    >
                      {leader.name}
                      <span className="ml-0.5 text-[10px] text-muted-foreground">
                        {boardHeightLabel(leader.height)}
                        {leader.status === 'zb' ? '炸板' : afterClose ? '断' : ''}
                      </span>
                      {leader.themes && leader.themes.length > 0 ? (
                        <span className="ml-1 text-[10px] text-muted-foreground">{formatThemes(leader.themes)}</span>
                      ) : null}
                    </button>
                  </MarketStockPreviewTooltip>
                ))}
              </div>
            </div>
            {relay.watchlist.length > 0 ? (
              <div className="mt-2 flex items-start gap-2 text-xs">
                {relayRowLabel('首板候选')}
                <div className="min-w-0 flex-1 flex flex-wrap items-center gap-1.5">
                  {relay.watchlist.map((candidate) => (
                    <MarketStockPreviewTooltip key={candidate.code} code={candidate.code} name={candidate.name}>
                      <button
                        type="button"
                        onClick={() => onSelectStock(candidate.code, candidate.name)}
                        className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-muted/60 ${
                          candidate.sameTheme ? 'bg-orange-500/10 text-orange-700 dark:text-orange-300' : 'text-foreground'
                        }`}
                      >
                        <span className="font-medium">{candidate.name}</span>
                        <span className="tabular-nums text-[10px] text-muted-foreground">{candidate.score}分</span>
                        {candidate.turnoverRate != null ? (
                          <span className="tabular-nums text-[10px] text-muted-foreground">{candidate.turnoverRate.toFixed(1)}%</span>
                        ) : null}
                        {candidate.themes && candidate.themes.length > 0 ? (
                          <span className="text-[10px] text-muted-foreground">{formatThemes(candidate.themes)}</span>
                        ) : null}
                        {candidate.reasons.slice(0, 2).map((reason) => (
                          <span key={reason} className="rounded bg-muted/60 px-1 text-[10px] text-muted-foreground">
                            {reason}
                          </span>
                        ))}
                      </button>
                    </MarketStockPreviewTooltip>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="mt-4 text-xs text-muted-foreground">今日空间龙头未见断板，暂无接力窗口。</div>
        )}
      </div>

      <div className="rounded-[24px] border border-border/70 bg-background/70 p-5">
        <div className="text-sm font-semibold text-foreground">异动反包</div>
        <div className="mt-1 text-xs text-muted-foreground">
          连板/首板反包来自当日异动池，炸板仅作走势标记；其余当日和昨日炸板归入炸板回封（昨炸修复≥3%后展示）。
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {(
            [
              ['连板反包', reboundStats.rebreak],
              ['首板反包', reboundStats.firstBoard],
              ['炸板回封', reboundStats.reseal],
            ] as const
          ).map(([label, stats]) =>
            stats.total > 0 ? (
              <span key={label} className="tabular-nums">
                {label} {stats.continued}/{stats.total}（{Math.round((stats.continued / stats.total) * 100)}%）
              </span>
            ) : null
          )}
        </div>

        {relay.reboundConfirmed.length >= 3 ? (
          <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
            反包集中出现（{relay.reboundConfirmed.length}只）：多为退潮修复期信号，谨防次日集体分歧。
          </div>
        ) : null}

        {relay.reboundConfirmed.length + relay.reboundWatching.length > 0 ? (
          <div className="mt-4">
            <div className="text-xs font-medium text-muted-foreground">
              反包候选池 {relay.reboundConfirmed.length + relay.reboundWatching.length}只
              <span className="ml-2 font-normal text-muted-foreground">
                {STATUS_SUMMARY.map(([label, count], index) =>
                  count > 0 ? (
                    <span key={label} className="tabular-nums inline-flex items-center gap-1">
                      {index > 0 ? <span className="opacity-50">·</span> : ''}
                      <span className={`inline-block h-1.5 w-1.5 rounded-full ${STATUS_COLORS[label]}`} />
                      {label} {count}
                    </span>
                  ) : null
                )}
              </span>
            </div>
            <div className="mt-2 space-y-1">
              {(['连板反包', '首板反包', '炸板回封'] as const).map((pattern, groupIndex) => {
                const items = reboundPicks.filter((stock) => stock.pattern === pattern);
                if (items.length === 0) return null;
                return (
                  <div
                    key={pattern}
                    className={
                      groupIndex === 0
                        ? 'flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs'
                        : 'flex flex-wrap items-center gap-x-1.5 gap-y-1 border-t border-border/60 pt-1 text-xs'
                    }
                  >
                    {items.map((stock) => {
                      const status = reboundStatus(stock);
                      const change = stock.change;
                      const breakLabels = [stock.brokeToday ? '炸板' : '', stock.brokeYesterday ? '昨炸' : '']
                        .filter(Boolean)
                        .join('·');
                      const patternLabel =
                        stock.pattern === '炸板回封'
                          ? `${breakLabels || '炸板'}${stock.hasPriorSeal ? `·前${boardHeightLabel(stock.prevHeight)}·断${stock.gapDays}日` : ''}`
                          : `前${boardHeightLabel(stock.prevHeight)}·断${stock.gapDays}日${breakLabels ? `·${breakLabels}` : ''}`;
                      return (
                        <MarketStockPreviewTooltip
                          key={stock.code}
                          code={stock.code}
                          name={stock.name}
                          summary={withThemeSummary(stock.analysis || stock.reasons.join(' · ') || undefined, stock.themes)}
                        >
                          <button
                            type="button"
                            onClick={() => onSelectStock(stock.code, stock.name)}
                            className="inline-flex items-center gap-1 rounded px-1 py-0.5 text-xs hover:bg-muted/60"
                          >
                            <span
                              className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${STATUS_COLORS[status]}`}
                            />
                            <span className="font-medium text-foreground">{stock.name}</span>
                            <span className="text-[10px] text-muted-foreground">
                              {patternLabel}
                              {stock.wasLeader ? '·前龙头' : ''}
                              {stock.inMainline ? '·主线' : ''}
                            </span>
                            <span className="tabular-nums text-[10px] text-muted-foreground">
                              {status === '已回封'
                                ? `${stock.sealTime}·${stock.fund != null && stock.fund > 0 ? `${stock.fund.toFixed(1)}亿` : '--'}`
                                : change == null
                                  ? '--'
                                  : `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`}
                              {stock.turnoverRate != null ? `·换手${stock.turnoverRate.toFixed(1)}%` : ''}
                              {stock.washMinutes != null ? `·${washLabel(stock.washMinutes)}` : ''}
                              {stock.themes && stock.themes.length > 0 ? `·${formatThemes(stock.themes)}` : ''}
                            </span>
                          </button>
                        </MarketStockPreviewTooltip>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="mt-4 text-xs text-muted-foreground">异动池内暂无断板/炸板候选。</div>
        )}
      </div>
    </div>
  );
}


export default function Home() {
  const router = useRouter();
  const { isAuthenticated, isReady, user, logout } = useAuth();
  const { selectedAccount } = useAccounts();
  const [selectedStock, setSelectedStock] = useState<StockInfo | null>(null);
  const [viewMode, setViewMode] = useState<HomeViewMode>('stock');
  const [modeReady, setModeReady] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [showTopicMenu, setShowTopicMenu] = useState(false);
  const [marketSnapshot, setMarketSnapshot] = useState<MarketSnapshot>(DEFAULT_MARKET_SNAPSHOT);
  const [marketLoading, setMarketLoading] = useState(false);
  const [cardRefreshing, setCardRefreshing] = useState<Record<MarketCardLabel, boolean>>(() => ({ ...EMPTY_CARD_REFRESH }));
  const [autoRefresh, setAutoRefresh] = useState<Record<MarketCardLabel, boolean>>(() => ({ ...EMPTY_CARD_REFRESH }));
  const [loadedMarketCards, setLoadedMarketCards] = useState<Record<MarketCardLabel, boolean>>(() => ({ ...EMPTY_CARD_DETAILS }));
  const [activeMarketCard, setActiveMarketCard] = useState<MarketCardLabel | null>(null);
  const [selectedEmotionDate, setSelectedEmotionDate] = useState<string | null>(null);
  const [emotionDetailTab, setEmotionDetailTab] = useState<'ladder' | 'short' | 'map'>('ladder');
  const [shortEmotionCycle, setShortEmotionCycle] = useState<1 | 3 | 5 | 10 | 20>(5);
  const [opportunityMapFocus, setOpportunityMapFocus] = useState<OpportunityMapStageId | null>(null);
  const [opportunityMapExpanded, setOpportunityMapExpanded] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const userButtonRef = useRef<HTMLButtonElement>(null);
  const topicMenuRef = useRef<HTMLDivElement>(null);
  const marketPageLoadMetaRef = useRef<MarketPageLoadMeta | null>(null);
  const modeConfig = HOME_VIEW_MODES[viewMode];
  const emotionSeries = marketSnapshot.emotionSeries;
  const canViewRelay = canAccessRelay(user?.points);
  const selectedEmotionPoint =
    emotionSeries.find((point) => point.fullDate === selectedEmotionDate) ??
    emotionSeries[emotionSeries.length - 1] ??
    null;
  const opportunityAssessment = useMemo(
    () => assessOpportunityMap(selectedEmotionPoint, marketSnapshot.shortEmotion, marketSnapshot.mainlineLanes, marketSnapshot.relay),
    [marketSnapshot.mainlineLanes, marketSnapshot.relay, marketSnapshot.shortEmotion, selectedEmotionPoint]
  );
  const opportunityMapStage = opportunityMapFocus ?? opportunityAssessment.stage;
  const opportunityMap = OPPORTUNITY_MAP_STAGES.find((stage) => stage.id === opportunityMapStage) || OPPORTUNITY_MAP_STAGES[0];
  const topMainline = marketSnapshot.mainlineLanes[0] ?? null;

  const toggleOpportunityMap = () => {
    const nextExpanded = !opportunityMapExpanded;
    setOpportunityMapExpanded(nextExpanded);
    if (nextExpanded) {
      void refreshMarket(['情绪', '主线', '趋势']);
    }
  };

  useEffect(() => {
    if (!isReady) return;

    const viewParam = parseHomeView(new URLSearchParams(window.location.search).get('view'));
    const savedMode = parseHomeView(window.localStorage.getItem(MODE_STORAGE_KEY));
    const requested = viewParam ?? savedMode ?? 'stock';

    if (isAuthRequiredView(requested) && !isAuthenticated) {
      setViewMode('stock');
    } else {
      setViewMode(requested);
    }
    setModeReady(true);
  }, [isAuthenticated, isReady]);

  useEffect(() => {
    if (!modeReady || !isAuthenticated) return;
    window.localStorage.setItem(MODE_STORAGE_KEY, viewMode);
  }, [isAuthenticated, modeReady, viewMode]);

  useEffect(() => {
    if (!isReady || isAuthenticated) return;
    if (isAuthRequiredView(viewMode)) {
      setViewMode('stock');
    }
  }, [isAuthenticated, isReady, viewMode]);

  const getMarketSessionKey = useCallback(() => {
    const now = new Date();
    return `${yyyymmdd(now)}:${isTradingTime(now) ? 'trading' : 'offhours'}`;
  }, []);

  const shouldReloadMarketPage = useCallback(() => {
    const now = Date.now();
    const sessionKey = getMarketSessionKey();
    const current = marketPageLoadMetaRef.current;
    const inTrading = sessionKey.endsWith(':trading');
    if (!current || current.sessionKey !== sessionKey) {
      return true;
    }
    if (!inTrading) {
      return false;
    }
    return now - current.lastSyncedAt >= MARKET_TRADING_RELOAD_MS;
  }, [getMarketSessionKey]);

  const markMarketPageSynced = useCallback(() => {
    marketPageLoadMetaRef.current = {
      sessionKey: getMarketSessionKey(),
      lastSyncedAt: Date.now(),
    };
  }, [getMarketSessionKey]);

  const refreshMarket = useCallback(async (labels: MarketCardLabel[] = MARKET_CARD_LABELS) => {
    setCardRefreshing((current) => {
      const next = { ...current };
      labels.forEach((label) => {
        next[label] = true;
      });
      return next;
    });
    try {
      const results = await Promise.all(
        labels.map(async (label) => {
          if (label === '趋势') {
            const trend = await loadTrendSnapshot();
            return {
              label,
              apply: (current: MarketSnapshot): MarketSnapshot => ({
                ...current,
                turnover: trend.turnover,
                sectorTrend: trend.sectorTrend,
                diagnostics: {
                  ...current.diagnostics,
                  趋势: { facts: trend.facts },
                },
              }),
            };
          }
          if (label === '情绪') {
            const desiredEmotionDays = activeMarketCard === '情绪' ? shortEmotionCycle : 5;
            const emotion = await loadEmotionSnapshot(desiredEmotionDays);
            return {
              label,
              apply: (current: MarketSnapshot): MarketSnapshot => ({
                ...current,
                emotionSeries: emotion.emotionSeries,
                intradayEmotion: emotion.intradayEmotion ?? current.intradayEmotion,
                shortEmotion: emotion.shortEmotion ?? current.shortEmotion,
                diagnostics: {
                  ...current.diagnostics,
                  情绪: { facts: emotion.facts },
                },
              }),
            };
          }
          if (label === '主线') {
            const mainline = await loadMainlineSnapshot();
            return {
              label,
              apply: (current: MarketSnapshot): MarketSnapshot => ({
                ...current,
                mainlineLanes: mainline.mainlineLanes,
                relay: mainline.relay,
                diagnostics: {
                  ...current.diagnostics,
                  主线: { facts: mainline.facts },
                },
              }),
            };
          }
          const payoff = await loadPayoffSnapshot();
          return {
            label,
            apply: (current: MarketSnapshot): MarketSnapshot => ({
              ...current,
              payoffLists: payoff.payoffLists,
              diagnostics: {
                ...current.diagnostics,
                赚钱效应: { facts: payoff.facts },
              },
            }),
          };
        })
      );
      setMarketSnapshot((current) => results.reduce((next, result) => result.apply(next), current));
      setLoadedMarketCards((current) => {
        const next = { ...current };
        labels.forEach((label) => {
          next[label] = true;
        });
        return next;
      });
      markMarketPageSynced();
    } catch (error: unknown) {
      console.error('加载市场总览失败:', error);
    } finally {
      setMarketLoading(false);
      setCardRefreshing((current) => {
        const next = { ...current };
        labels.forEach((label) => {
          next[label] = false;
        });
        return next;
      });
    }
  }, [activeMarketCard, markMarketPageSynced, shortEmotionCycle]);

  useEffect(() => {
    if (viewMode !== 'market' || !isAuthenticated) {
      return;
    }

    if (!shouldReloadMarketPage()) {
      return;
    }

    let active = true;
    setMarketLoading(true);
    setLoadedMarketCards({ ...EMPTY_CARD_DETAILS });
    loadMarketSummarySnapshot()
      .then((snapshot) => {
        if (!active) return;
        setMarketSnapshot(snapshot);
        markMarketPageSynced();
      })
      .catch((error: unknown) => {
        console.error('加载市场总览失败:', error);
        if (active) setMarketSnapshot(DEFAULT_MARKET_SNAPSHOT);
      })
      .finally(() => {
        if (active) setMarketLoading(false);
      });

    return () => {
      active = false;
    };
  }, [isAuthenticated, markMarketPageSynced, shouldReloadMarketPage, viewMode]);

  useEffect(() => {
    if (viewMode !== 'market' || !isAuthenticated || !activeMarketCard) {
      return;
    }
    if (loadedMarketCards[activeMarketCard]) {
      return;
    }
    void refreshMarket([activeMarketCard]);
  }, [activeMarketCard, isAuthenticated, loadedMarketCards, refreshMarket, viewMode]);

  useEffect(() => {
    if (viewMode !== 'market' || !isAuthenticated) {
      return;
    }
    const enabled = MARKET_CARD_LABELS.filter((label) => autoRefresh[label]);
    if (enabled.length === 0) {
      return;
    }

    const timer = window.setInterval(() => {
      if (isTradingTime()) {
        const current = marketPageLoadMetaRef.current;
        if (!current || Date.now() - current.lastSyncedAt >= 30_000) {
          refreshMarket(enabled);
        }
      }
    }, 30000);

    return () => window.clearInterval(timer);
  }, [autoRefresh, isAuthenticated, refreshMarket, viewMode]);

  useEffect(() => {
    if (emotionSeries.length === 0) {
      setSelectedEmotionDate(null);
      return;
    }

    if (!selectedEmotionDate || !emotionSeries.some((point) => point.fullDate === selectedEmotionDate)) {
      setSelectedEmotionDate(emotionSeries[emotionSeries.length - 1].fullDate);
    }
  }, [emotionSeries, selectedEmotionDate]);

  useEffect(() => {
    const desiredEmotionDays = shortEmotionCycle;
    const shortReady = emotionSeries.length >= desiredEmotionDays;
    const intradayReady = (marketSnapshot.intradayEmotion?.points.length || 0) > 0;
    const shortEmotionReady = (marketSnapshot.shortEmotion?.days.length || 0) >= Math.min(desiredEmotionDays, 1);
    if (
      viewMode !== 'market' ||
      !isAuthenticated ||
      activeMarketCard !== '情绪' ||
      (shortReady && intradayReady && shortEmotionReady)
    ) {
      return;
    }

    let active = true;
    loadEmotionSnapshot(desiredEmotionDays)
      .then((emotionSnapshot) => {
        if (!active) return;
        setMarketSnapshot((current) => ({
          ...current,
          emotionSeries: emotionSnapshot.emotionSeries.length > 0 ? emotionSnapshot.emotionSeries : current.emotionSeries,
          intradayEmotion: emotionSnapshot.intradayEmotion ?? current.intradayEmotion,
          shortEmotion: emotionSnapshot.shortEmotion ?? current.shortEmotion,
          diagnostics: {
            ...current.diagnostics,
            情绪: {
              ...current.diagnostics.情绪,
              facts: emotionSnapshot.facts.length > 0 ? emotionSnapshot.facts : current.diagnostics.情绪.facts,
            },
          },
        }));
      })
      .catch((error: unknown) => {
        console.error('补加载情绪数据失败:', error);
      });

    return () => {
      active = false;
    };
  }, [activeMarketCard, emotionSeries.length, isAuthenticated, marketSnapshot.intradayEmotion, marketSnapshot.shortEmotion, shortEmotionCycle, viewMode]);

  // 处理点击外部关闭菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        userMenuRef.current &&
        !userMenuRef.current.contains(event.target as Node) &&
        userButtonRef.current &&
        !userButtonRef.current.contains(event.target as Node)
      ) {
        setShowUserMenu(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setShowUserMenu(false);
      }
    };

    if (showUserMenu) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [showUserMenu]);

  useEffect(() => {
    if (!showTopicMenu) {
      return;
    }

    const handleClickOutside = (event: MouseEvent) => {
      if (topicMenuRef.current && !topicMenuRef.current.contains(event.target as Node)) {
        setShowTopicMenu(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setShowTopicMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [showTopicMenu]);

  // 处理退出登录
  const handleLogout = async () => {
    try {
      await logout();
      router.push('/login');
    } catch (error) {
      console.error('退出登录失败:', error);
    }
  };

  const handleSelectMarketStock = async (code: string, name: string) => {
    if (!code) return;
    const query = code.replace(/\.(SS|SZ|SH|BJ|HK|US)$/i, '').replace(/^(SH|SZ|BJ)/i, '');
    let stock: StockInfo | null = null;
    try {
      const response = await searchStocks(query);
      if (response.success && response.data && response.data.length > 0) {
        const digits = query.replace(/\D/g, '').padStart(6, '0').slice(-6);
        stock =
          response.data.find((item) => item.symbol.replace(/\D/g, '').includes(digits)) ||
          response.data.find((item) => item.name === name) ||
          response.data[0];
      }
    } catch (error) {
      console.error('搜索股票失败:', error);
    }
    if (!stock) {
      const digits = query.replace(/\D/g, '').padStart(6, '0').slice(-6);
      const suffix = digits.startsWith('6') || digits.startsWith('5') || digits.startsWith('9')
        ? 'SH'
        : digits.startsWith('4') || digits.startsWith('8')
          ? 'BJ'
          : 'SZ';
      stock = { symbol: `${digits}.${suffix}`, name, exchange: '', currency: 'CNY' };
    }
    setViewMode('stock');
    setSelectedStock(stock);
  };

  // 处理选择股票
  const handleSelectStock = (stock: StockInfo) => {
    setSelectedStock(stock);
    
    const detailsElement = document.getElementById('stock-details-section');
    if (detailsElement) {
      detailsElement.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // 处理从收藏夹选择股票
  const handleSelectFromSaved = (symbol: string) => {
    // 这里简单处理，只设置symbol
    setSelectedStock({
      symbol,
      name: '',
      exchange: '',
      currency: '',
    });
  };

  const requestViewMode = (mode: HomeViewMode) => {
    if (!isReady) return;
    if (isAuthRequiredView(mode) && !isAuthenticated) {
      router.push(loginUrl('/', mode));
      return;
    }
    setViewMode(mode);
  };

  const cycleViewMode = () => {
    const currentIndex = VIEW_MODE_ORDER.indexOf(viewMode);
    const nextIndex = (currentIndex + 1) % VIEW_MODE_ORDER.length;
    requestViewMode(VIEW_MODE_ORDER[nextIndex]);
  };

  return (
    <div
      className="min-h-screen bg-background"
      style={
        {
          '--primary': modeConfig.primary,
          '--ring': modeConfig.ring,
        } as React.CSSProperties
      }
    >
      <header className="border-b border-border">
        <div className="container mx-auto px-4 py-4 flex items-center">
          <button
            type="button"
            onClick={cycleViewMode}
            className="group flex items-center gap-2 rounded-full px-1 py-1 text-left transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={`切换首页视角，当前为 AlphaBot | ${modeConfig.navLabel}`}
          >
            <div className="flex items-center text-2xl font-bold text-primary">
              <ChartLine className="mr-2 h-6 w-6" />
              <span>AlphaBot</span>
            </div>
            <div className="flex flex-col leading-none">
              <div className="text-lg font-medium text-muted-foreground">
              <span className="mx-1 text-border">|</span>
              <span className="text-foreground">{modeConfig.navLabel}</span>
              </div>
            </div>
          </button>
          <div className="ml-auto flex items-center space-x-4">
            {isAuthenticated ? (
              <>
                <Link href="/agent">
                  <Button variant="ghost" className="flex items-center" size="sm">
                    <Bot className="h-5 w-5 mr-1" />
                    <span>智能助手</span>
                  </Button>
                </Link>
                <div className="relative">
                  <button
                    ref={userButtonRef}
                    onClick={() => setShowUserMenu(!showUserMenu)}
                    className="flex items-center text-muted-foreground hover:text-foreground"
                  >
                    <User className="h-5 w-5 mr-1" />
                    <span>{user?.username}</span>
                    {selectedAccount && (
                      <span className="ml-2 hidden rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 md:inline">
                        {selectedAccount.name}
                      </span>
                    )}
                  </button>
                  {showUserMenu && (
                    <div
                      ref={userMenuRef}
                      className="absolute right-0 mt-2 w-48 py-2 bg-background border border-border rounded-md shadow-lg z-50"
                    >
                      <div className="px-4 py-2 border-b border-border">
                        <div className="text-sm font-medium">{user?.username}</div>
                        <div className="text-sm text-muted-foreground">积分: {user?.points}</div>
                        <div className="text-sm text-muted-foreground">
                          今日使用: {user?.daily_usage_count} / {user?.is_unlimited ? '无限制' : user?.daily_limit}
                        </div>
                      </div>
                      <AccountSwitcher />
                      <div
                        className="block px-4 py-2 text-sm text-foreground hover:bg-accent cursor-pointer"
                        onClick={() => {
                          setShowUserMenu(false);
                          setTimeout(() => router.push('/batch'), 10);
                        }}
                      >
                        <Bot className="h-4 w-4 inline mr-2" />
                        批量分析
                      </div>
                      <div
                        className="block px-4 py-2 text-sm text-foreground hover:bg-accent cursor-pointer"
                        onClick={() => {
                          setShowUserMenu(false);
                          setTimeout(() => router.push('/system'), 10);
                        }}
                      >
                        <Settings className="h-4 w-4 inline mr-2" />
                        系统管理
                      </div>
                      <button
                        onClick={() => {
                          setShowUserMenu(false);
                          setShowChangePassword(true);
                        }}
                        className="block w-full text-left px-4 py-2 text-sm text-foreground hover:bg-accent"
                      >
                        <Key className="h-4 w-4 inline mr-2" />
                        修改密码
                      </button>
                      <button
                        onClick={handleLogout}
                        className="block w-full text-left px-4 py-2 text-sm text-red-500 hover:bg-accent"
                      >
                        <LogOut className="h-4 w-4 inline mr-2" />
                        退出登录
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <Link
                href="/login"
                className="flex items-center text-muted-foreground hover:text-foreground"
              >
                <LogIn className="h-5 w-5 mr-1" />
                <span>登录</span>
              </Link>
            )}
            {/* <a
              href="https://www.jianshu.com/c/38a7568e2b6b"
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground hover:text-foreground"
            >
              简书
            </a> */}
            <a
              href="https://github.com/x-pai/AlphaBot/discussions"
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground hover:text-foreground"
            >
              讨论组
            </a>
            <a
              href="https://www.iwencai.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground hover:text-foreground"
            >
              问财
            </a>
            <Link
              href="/published/daily-market-brief"
              className="text-muted-foreground hover:text-foreground"
            >
              市场日报
            </Link>
            <a
              href="https://github.com/x-pai/alphabot"
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground hover:text-foreground"
            >
              GitHub
            </a>
            <Link
              href="/about"
              className="flex items-center text-muted-foreground hover:text-foreground"
            >
              <Info className="h-5 w-5 mr-1" />
              <span>关于我们</span>
            </Link>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-bold">{modeConfig.title}</h1>
              </div>
              <p className="text-muted-foreground">
                {isAuthenticated ? 
                  modeConfig.description :
                  '登录后可获取更多功能，包括AI分析、个性化推荐等'
                }
              </p>
            </div>
            {isAuthenticated && (
              <div>
                <CacheControl />
              </div>
            )}
          </div>
          {viewMode === 'stock' ? (
            <StockSearch onSelectStock={handleSelectStock} />
          ) : !isAuthenticated ? (
            <div className="rounded-[24px] border border-dashed border-border/70 bg-background/60 px-6 py-12 text-center">
              <div className="text-lg font-semibold text-foreground">登录后查看{modeConfig.navLabel}</div>
              <p className="mt-2 text-sm text-muted-foreground">
                {viewMode === 'market' ? '市场主线、情绪和板块强度需要登录后使用。' : '专题内容需要登录后进入。'}
              </p>
              <Link href={loginUrl('/', viewMode === 'topic' ? 'topic' : 'market')} className="mt-5 inline-flex">
                <Button>立即登录</Button>
              </Link>
            </div>
          ) : viewMode === 'market' ? (
            <div className="flex flex-col gap-6">
              <MarketSourceNotice />
              <div className="order-2 grid gap-4 xl:grid-cols-4">
                {MARKET_DIAGNOSTICS.map((item) => {
                  const dynamicCard = marketSnapshot.diagnostics[item.label];
                  const isActive = activeMarketCard === item.label;
                  const refreshing = cardRefreshing[item.label];
                  const autoOn = autoRefresh[item.label];
                  return (
                    <div
                      key={item.label}
                      role="button"
                      tabIndex={0}
                      onClick={() => setActiveMarketCard((current) => (current === item.label ? null : item.label))}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          setActiveMarketCard((current) => (current === item.label ? null : item.label));
                        }
                      }}
                      className={`rounded-[22px] border bg-background/70 px-5 py-5 text-left transition-all hover:-translate-y-0.5 ${
                        item.borderClassName
                      } ${isActive ? 'border-primary/60 bg-primary/[0.05]' : ''}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-medium text-foreground">{item.label}</div>
                        <div
                          className="flex items-center gap-1.5"
                          onClick={(event) => event.stopPropagation()}
                          onKeyDown={(event) => event.stopPropagation()}
                        >
                          <button
                            type="button"
                            title="刷新"
                            disabled={refreshing}
                            onClick={() => refreshMarket([item.label])}
                            className="rounded-full p-1 text-muted-foreground hover:bg-muted/70 hover:text-foreground disabled:opacity-50"
                          >
                            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                          </button>
                          <button
                            type="button"
                            role="switch"
                            aria-checked={autoOn}
                            title="自动刷新"
                            onClick={() =>
                              setAutoRefresh((current) => ({ ...current, [item.label]: !current[item.label] }))
                            }
                            className="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
                          >
                            <span>自动</span>
                            <span
                              className={`relative h-4 w-7 rounded-full transition-colors ${
                                autoOn ? 'bg-primary' : 'bg-muted'
                              }`}
                            >
                              <span
                                className={`absolute top-0.5 h-3 w-3 rounded-full bg-white shadow-sm transition-all ${
                                  autoOn ? 'left-3.5' : 'left-0.5'
                                }`}
                              />
                            </span>
                          </button>
                        </div>
                      </div>
                      <div className="mt-5 space-y-3">
                        {dynamicCard.facts.map((fact) => (
                          <div key={fact} className="flex items-start gap-3">
                            <span className="mt-2 h-1.5 w-1.5 rounded-full bg-primary" />
                            <span className="text-sm text-muted-foreground">{marketLoading ? '--' : fact}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="order-1 rounded-[24px] border border-orange-200/80 bg-gradient-to-r from-orange-50/80 via-background to-background px-5 py-4 dark:border-orange-400/20 dark:from-orange-950/20">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-semibold text-foreground">市场机会地图</div>
                      <span className="rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-medium text-orange-700 dark:bg-orange-950/50 dark:text-orange-200">当前观察 · {OPPORTUNITY_MAP_STAGES.find((stage) => stage.id === opportunityAssessment.stage)?.label}</span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{opportunityAssessment.evidence.join(' · ')}</div>
                  </div>
                  <button type="button" onClick={toggleOpportunityMap} className="inline-flex shrink-0 items-center justify-center rounded-full border border-orange-200 bg-background px-3 py-1.5 text-xs font-medium text-orange-700 transition-colors hover:bg-orange-100 dark:border-orange-400/30 dark:text-orange-200">
                    {cardRefreshing.情绪 || cardRefreshing.主线 || cardRefreshing.趋势 ? '正在同步数据…' : opportunityMapExpanded ? '收起地图' : '展开地图并同步数据'}
                  </button>
                </div>
                {opportunityMapExpanded ? (
                  <div className="mt-4 border-t border-orange-200/70 pt-4 dark:border-orange-400/20">
                    <div className="relative mx-auto hidden h-[360px] w-full max-w-[760px] lg:block">
                      <svg viewBox="0 0 760 380" className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
                        <defs><marker id="market-cycle-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(249,115,22,0.65)" /></marker></defs>
                        <path d="M 275 58 L 485 58 M 560 88 L 650 154 M 650 224 L 560 290 M 485 320 L 275 320 M 200 290 L 110 224 M 110 154 L 200 88" fill="none" stroke="rgba(249,115,22,0.5)" strokeWidth="2" markerEnd="url(#market-cycle-arrow)" />
                      </svg>
                      <div className="absolute left-1/2 top-1/2 w-[235px] -translate-x-1/2 -translate-y-1/2 rounded-[22px] border border-orange-200 bg-orange-50/95 px-4 py-3 text-center shadow-[0_12px_30px_rgba(249,115,22,0.10)] dark:border-orange-400/30 dark:bg-orange-950/50">
                        <div className="text-[10px] text-muted-foreground">{opportunityMapFocus ? '机会剧本' : '当前观察'}</div>
                        <div className="mt-1 text-sm font-semibold text-orange-700 dark:text-orange-200">{opportunityMap.label}</div>
                        <div className="mt-1 text-[10px] leading-4 text-muted-foreground">{opportunityMapFocus ? opportunityMap.signal : opportunityAssessment.evidence.slice(0, 2).join(' · ')}</div>
                        <div className="mt-2 border-t border-orange-200/70 pt-2 text-left dark:border-orange-400/20"><div className="text-[10px] text-foreground">优先：{opportunityMap.opportunity}</div><div className="mt-1 text-[10px] text-muted-foreground">风险：{opportunityMap.risk}</div></div>
                        <div className="mt-2 flex flex-wrap justify-center gap-1.5">
                          {opportunityMap.id === 'leader' && topMainline?.leader ? <button type="button" onClick={() => handleSelectMarketStock(topMainline.leader!.code, topMainline.leader!.name)} className="rounded-full bg-orange-500 px-2.5 py-1 text-[10px] font-medium text-white">核心龙头 · {topMainline.leader.name}</button> : opportunityMap.id === 'rotation' ? <button type="button" onClick={() => setActiveMarketCard('趋势')} className="rounded-full bg-orange-500 px-2.5 py-1 text-[10px] font-medium text-white">查看趋势排行</button> : opportunityMap.id === 'weak' || opportunityMap.id === 'collapse' ? <button type="button" onClick={() => { setEmotionDetailTab('ladder'); setActiveMarketCard('情绪'); }} className="rounded-full bg-orange-500 px-2.5 py-1 text-[10px] font-medium text-white">查看连板天梯</button> : <button type="button" onClick={() => setActiveMarketCard('主线')} className="rounded-full bg-orange-500 px-2.5 py-1 text-[10px] font-medium text-white">{opportunityMap.id === 'adjustment' ? '查看回封/断板' : '查看主线'}</button>}
                          {opportunityMapFocus ? <button type="button" onClick={() => setOpportunityMapFocus(null)} className="rounded-full border border-orange-200 px-2.5 py-1 text-[10px] text-orange-700 dark:border-orange-400/30 dark:text-orange-200">返回当前观察</button> : null}
                        </div>
                      </div>
                      {OPPORTUNITY_MAP_STAGES.map((stage, index) => {
                        const active = stage.id === opportunityMapStage;
                        return <button key={stage.id} type="button" onClick={() => setOpportunityMapFocus(stage.id)} style={OPPORTUNITY_MAP_POSITIONS[index]} className={`absolute w-[142px] -translate-x-1/2 -translate-y-1/2 rounded-[16px] border px-3 py-2.5 text-left shadow-sm transition-colors hover:border-orange-300 ${active ? 'border-orange-400 bg-orange-50 shadow-[0_10px_24px_rgba(249,115,22,0.16)] dark:border-orange-400/60 dark:bg-orange-950/40' : 'border-border/60 bg-background/90'}`}><div className="flex items-center gap-1.5"><span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold ${active ? 'bg-orange-500 text-white' : 'bg-muted text-muted-foreground'}`}>{index + 1}</span><span className="text-xs font-semibold text-foreground">{stage.label}</span></div><div className="mt-1 line-clamp-1 text-[10px] leading-4 text-muted-foreground">{stage.signal}</div></button>;
                      })}
                    </div>
                    <div className="grid gap-2 lg:hidden">
                      {OPPORTUNITY_MAP_STAGES.map((stage, index) => {
                        const active = stage.id === opportunityMapStage;
                        return <button key={stage.id} type="button" onClick={() => setOpportunityMapFocus(stage.id)} className={`rounded-[14px] border px-3 py-2 text-left text-xs ${active ? 'border-orange-400 bg-orange-50 dark:border-orange-400/50 dark:bg-orange-950/30' : 'border-border/60 bg-background/50'}`}>{index + 1}. {stage.label}</button>;
                      })}
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="order-3">
              {!activeMarketCard ? (
                <div className="rounded-[24px] border border-dashed border-border/70 bg-background/35 px-5 py-4 text-sm text-muted-foreground">
                  点击上方卡片，查看对应图表与事实对比。
                </div>
              ) : (
                <>
                  {activeMarketCard === '趋势' ? (
                    <div className="space-y-4">
                      <TurnoverMinuteChart data={marketSnapshot.turnover} />
                      <SectorTrendTrajectory
                        data={marketSnapshot.sectorTrend}
                        onSelectStock={handleSelectMarketStock}
                      />
                    </div>
                  ) : activeMarketCard === '情绪' ? (
                    <div className="space-y-4">
                      <div className="rounded-[24px] border border-border/70 bg-background/70 p-5">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                          <div>
                            <div className="text-sm font-semibold text-foreground">盘中情绪</div>
                            <div className="mt-1 text-xs text-muted-foreground">观察盘中正负情绪强弱变化。</div>
                          </div>
                          <div className="rounded-[14px] border border-orange-200/70 bg-orange-50/60 px-3 py-2 text-right dark:border-orange-400/20 dark:bg-orange-950/20">
                            <div className="text-[10px] text-muted-foreground">短线机会观察</div>
                            <div className="mt-0.5 text-xs font-semibold text-orange-700 dark:text-orange-200">
                              {OPPORTUNITY_MAP_STAGES.find((stage) => stage.id === opportunityAssessment.stage)?.label}
                            </div>
                          </div>
                        </div>
                        <div className="mt-4">
                          <IntradayEmotionChart data={marketSnapshot.intradayEmotion} />
                        </div>
                      </div>

                      <div className="rounded-[24px] border border-border/70 bg-background/70 p-5">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                          <div className="min-w-0">
                            <div className="text-sm font-semibold text-foreground">
                              {emotionDetailTab === 'ladder' ? '连板天梯' : emotionDetailTab === 'short' ? '短线情绪' : '短线机会地图'}
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              {emotionDetailTab === 'ladder'
                                ? `观察近${shortEmotionCycle}日连板高度变化。`
                                : emotionDetailTab === 'short'
                                  ? `观察近${shortEmotionCycle}日短线情绪强弱变化。`
                                  : '用情绪、连板高度和主线结构定位当前可做模式与风险。'}
                            </div>
                          </div>
                          <div className="flex items-center justify-end gap-3 self-start">
                            {emotionDetailTab !== 'map' ? (
                              <div className="inline-flex rounded-full border border-border/60 bg-background/80 p-1">
                                {([1, 3, 5, 10, 20] as const).map((cycle) => {
                                  const active = shortEmotionCycle === cycle;
                                  return (
                                    <button
                                      key={cycle}
                                      type="button"
                                      onClick={() => setShortEmotionCycle(cycle)}
                                      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                                        active ? 'bg-foreground text-background' : 'text-muted-foreground hover:text-foreground'
                                      }`}
                                    >
                                      {cycle}日
                                    </button>
                                  );
                                })}
                              </div>
                            ) : null}
                            <div className="inline-flex rounded-full border border-border/60 bg-background/80 p-1">
                              {([
                                { key: 'short', label: '短线情绪' },
                                { key: 'ladder', label: '连板天梯' },
                              ] as const).map((item) => {
                                const active = emotionDetailTab === item.key;
                                return (
                                  <button
                                    key={item.key}
                                    type="button"
                                    onClick={() => setEmotionDetailTab(item.key)}
                                    className={`rounded-full px-4 py-1.5 text-xs font-medium transition-colors ${
                                      active ? 'bg-orange-500 text-white' : 'text-muted-foreground hover:text-foreground'
                                    }`}
                                  >
                                    {item.label}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                        <div className="mt-4">
                          {emotionDetailTab === 'map' ? (
                            <div className="space-y-3">
                                <div className="relative mx-auto hidden h-[330px] max-w-[700px] md:block">
                                  <svg viewBox="0 0 760 380" className="absolute inset-0 h-full w-full" aria-hidden="true">
                                    <defs>
                                      <marker id="opportunity-cycle-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                                        <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(249,115,22,0.6)" />
                                      </marker>
                                    </defs>
                                    <path d="M 275 58 L 485 58" fill="none" stroke="rgba(249,115,22,0.48)" strokeWidth="2" markerEnd="url(#opportunity-cycle-arrow)" />
                                    <path d="M 560 88 L 650 154" fill="none" stroke="rgba(249,115,22,0.48)" strokeWidth="2" markerEnd="url(#opportunity-cycle-arrow)" />
                                    <path d="M 650 224 L 560 290" fill="none" stroke="rgba(249,115,22,0.48)" strokeWidth="2" markerEnd="url(#opportunity-cycle-arrow)" />
                                    <path d="M 485 320 L 275 320" fill="none" stroke="rgba(249,115,22,0.48)" strokeWidth="2" markerEnd="url(#opportunity-cycle-arrow)" />
                                    <path d="M 200 290 L 110 224" fill="none" stroke="rgba(249,115,22,0.48)" strokeWidth="2" markerEnd="url(#opportunity-cycle-arrow)" />
                                    <path d="M 110 154 L 200 88" fill="none" stroke="rgba(249,115,22,0.48)" strokeWidth="2" markerEnd="url(#opportunity-cycle-arrow)" />
                                  </svg>
                                  <div className="absolute left-1/2 top-1/2 w-[215px] -translate-x-1/2 -translate-y-1/2 rounded-[22px] border border-orange-200 bg-orange-50/95 px-4 py-3 text-center shadow-[0_12px_30px_rgba(249,115,22,0.10)] dark:border-orange-400/30 dark:bg-orange-950/50">
                                    <div className="text-[10px] text-muted-foreground">{opportunityMapFocus ? '机会剧本' : '当前观察'}</div>
                                    <div className="mt-1 text-sm font-semibold text-orange-700 dark:text-orange-200">{opportunityMap.label}</div>
                                    <div className="mt-1 text-[10px] leading-4 text-muted-foreground">
                                      {opportunityMapFocus ? opportunityMap.signal : opportunityAssessment.evidence.slice(0, 2).join(' · ')}
                                    </div>
                                    <div className="mt-2 border-t border-orange-200/70 pt-2 text-left dark:border-orange-400/20">
                                      <div className="text-[10px] font-medium text-foreground">优先：{opportunityMap.opportunity}</div>
                                      <div className="mt-1 text-[10px] leading-4 text-muted-foreground">风险：{opportunityMap.risk}</div>
                                    </div>
                                    <div className="mt-2 flex flex-wrap justify-center gap-1.5">
                                      {opportunityMap.id === 'leader' && topMainline?.leader ? (
                                        <button type="button" onClick={() => handleSelectMarketStock(topMainline.leader!.code, topMainline.leader!.name)} className="rounded-full bg-orange-500 px-2.5 py-1 text-[10px] font-medium text-white hover:bg-orange-600">
                                          核心龙头 · {topMainline.leader.name}
                                        </button>
                                      ) : opportunityMap.id === 'rotation' ? (
                                        <button type="button" onClick={() => setActiveMarketCard('趋势')} className="rounded-full bg-orange-500 px-2.5 py-1 text-[10px] font-medium text-white hover:bg-orange-600">查看趋势排行</button>
                                      ) : opportunityMap.id === 'adjustment' ? (
                                        <button type="button" onClick={() => setActiveMarketCard('主线')} className="rounded-full bg-orange-500 px-2.5 py-1 text-[10px] font-medium text-white hover:bg-orange-600">查看回封/断板</button>
                                      ) : opportunityMap.id === 'weak' || opportunityMap.id === 'collapse' ? (
                                        <button type="button" onClick={() => setEmotionDetailTab('ladder')} className="rounded-full bg-orange-500 px-2.5 py-1 text-[10px] font-medium text-white hover:bg-orange-600">查看连板天梯</button>
                                      ) : (
                                        <button type="button" onClick={() => setActiveMarketCard('主线')} className="rounded-full bg-orange-500 px-2.5 py-1 text-[10px] font-medium text-white hover:bg-orange-600">查看主线</button>
                                      )}
                                      {opportunityMapFocus ? <button type="button" onClick={() => setOpportunityMapFocus(null)} className="rounded-full border border-orange-200 px-2.5 py-1 text-[10px] text-orange-700 hover:bg-orange-100 dark:border-orange-400/30 dark:text-orange-200">返回当前观察</button> : null}
                                    </div>
                                  </div>
                                  {OPPORTUNITY_MAP_STAGES.map((stage, index) => {
                                    const active = stage.id === opportunityMapStage;
                                    return (
                                      <div key={stage.id} className="absolute w-[142px] -translate-x-1/2 -translate-y-1/2" style={OPPORTUNITY_MAP_POSITIONS[index]}>
                                        <button type="button" onClick={() => setOpportunityMapFocus(stage.id)} className={`w-full rounded-[16px] border px-3 py-2.5 text-left shadow-sm transition-colors hover:border-orange-300 ${active ? 'border-orange-400 bg-orange-50 shadow-[0_10px_24px_rgba(249,115,22,0.16)] dark:border-orange-400/60 dark:bg-orange-950/40' : 'border-border/60 bg-background/85'}`}>
                                          <div className="flex items-center gap-1.5">
                                            <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold ${active ? 'bg-orange-500 text-white' : 'bg-muted text-muted-foreground'}`}>{index + 1}</span>
                                            <span className="text-xs font-semibold text-foreground">{stage.label}</span>
                                          </div>
                                          <div className="mt-1 line-clamp-1 text-[10px] leading-4 text-muted-foreground">{stage.signal}</div>
                                        </button>
                                      </div>
                                    );
                                  })}
                                </div>
                                <div className="grid gap-2 md:hidden">
                                  {OPPORTUNITY_MAP_STAGES.map((stage, index) => {
                                    const active = stage.id === opportunityMapStage;
                                    return <button type="button" key={stage.id} onClick={() => setOpportunityMapFocus(stage.id)} className={`rounded-[14px] border px-3 py-2 text-left text-xs ${active ? 'border-orange-400 bg-orange-50 dark:border-orange-400/50 dark:bg-orange-950/30' : 'border-border/60 bg-background/50'}`}>{index + 1}. {stage.label}</button>;
                                  })}
                                </div>
                                <div className="rounded-[18px] border border-orange-200 bg-orange-50/80 px-4 py-3 md:hidden dark:border-orange-400/30 dark:bg-orange-950/30">
                                  <div className="text-[10px] text-muted-foreground">{opportunityMapFocus ? '机会剧本' : '当前观察'}</div>
                                  <div className="mt-1 text-sm font-semibold text-orange-700 dark:text-orange-200">{opportunityMap.label}</div>
                                  <div className="mt-1 text-[10px] leading-4 text-muted-foreground">{opportunityMapFocus ? opportunityMap.signal : opportunityAssessment.evidence.slice(0, 2).join(' · ')}</div>
                                  <div className="mt-2 text-[10px] text-foreground">优先：{opportunityMap.opportunity}</div>
                                  <div className="mt-1 text-[10px] text-muted-foreground">风险：{opportunityMap.risk}</div>
                                  <div className="mt-2 flex flex-wrap gap-1.5">
                                    {opportunityMap.id === 'leader' && topMainline?.leader ? (
                                      <button type="button" onClick={() => handleSelectMarketStock(topMainline.leader!.code, topMainline.leader!.name)} className="rounded-full bg-orange-500 px-2.5 py-1 text-[10px] font-medium text-white">核心龙头 · {topMainline.leader.name}</button>
                                    ) : opportunityMap.id === 'rotation' ? (
                                      <button type="button" onClick={() => setActiveMarketCard('趋势')} className="rounded-full bg-orange-500 px-2.5 py-1 text-[10px] font-medium text-white">查看趋势排行</button>
                                    ) : opportunityMap.id === 'weak' || opportunityMap.id === 'collapse' ? (
                                      <button type="button" onClick={() => setEmotionDetailTab('ladder')} className="rounded-full bg-orange-500 px-2.5 py-1 text-[10px] font-medium text-white">查看连板天梯</button>
                                    ) : (
                                      <button type="button" onClick={() => setActiveMarketCard('主线')} className="rounded-full bg-orange-500 px-2.5 py-1 text-[10px] font-medium text-white">{opportunityMap.id === 'adjustment' ? '查看回封/断板' : '查看主线'}</button>
                                    )}
                                    {opportunityMapFocus ? <button type="button" onClick={() => setOpportunityMapFocus(null)} className="rounded-full border border-orange-200 px-2.5 py-1 text-[10px] text-orange-700">返回当前观察</button> : null}
                                  </div>
                                </div>
                              {marketSnapshot.mainlineLanes.length > 0 ? (
                                <div className="rounded-[18px] border border-border/60 bg-background/50 px-4 py-3">
                                  <div className="text-xs text-muted-foreground">当前关联主线</div>
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    {marketSnapshot.mainlineLanes.slice(0, 3).map((lane) => (
                                      <button
                                        key={lane.name}
                                        type="button"
                                        onClick={() => lane.leader ? handleSelectMarketStock(lane.leader.code, lane.leader.name) : setActiveMarketCard('主线')}
                                        className="rounded-full bg-muted/60 px-2.5 py-1 text-xs text-foreground transition-colors hover:bg-orange-100 hover:text-orange-700 dark:hover:bg-orange-950/40 dark:hover:text-orange-200"
                                      >
                                        {lane.name}{lane.leader ? ` · ${lane.leader.name} ${lane.leader.lbc}板` : ''}
                                      </button>
                                    ))}
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          ) : (
                            <ShortEmotionChart
                              mode={emotionDetailTab}
                              cycle={shortEmotionCycle}
                              series={emotionSeries}
                              shortEmotion={marketSnapshot.shortEmotion}
                              selectedDate={selectedEmotionDate}
                              onSelectDate={setSelectedEmotionDate}
                              onSelectStock={handleSelectMarketStock}
                            />
                          )}
                        </div>
                      </div>

                      {selectedEmotionPoint && selectedEmotionPoint.geeseRows.length > 0 ? (
                        <div className="rounded-[24px] border border-border/70 bg-background/70 px-5 py-4">
                          <div className="mb-3 flex items-baseline justify-between gap-3">
                            <div className="text-sm font-semibold text-foreground">雁阵图</div>
                            <div className="text-xs text-muted-foreground">{selectedEmotionPoint.label}</div>
                          </div>
                          <div className="divide-y divide-border/50">
                            {selectedEmotionPoint.geeseRows.map((row) => {
                              const isFirst = row.progress === '首板';
                              const ratio = row.denominator > 0 ? Math.round((row.numerator / row.denominator) * 100) : 0;
                              const rateClass = isFirst
                                ? 'text-muted-foreground'
                                : ratio >= 60
                                  ? 'text-rose-600 dark:text-rose-300'
                                  : ratio >= 30
                                    ? 'text-amber-600 dark:text-amber-300'
                                    : 'text-emerald-600 dark:text-emerald-300';
                              return (
                                <div
                                  key={`${selectedEmotionPoint.fullDate}-${row.progress}`}
                                  className="grid grid-cols-1 gap-2 py-2.5 md:grid-cols-[64px_88px_minmax(0,1fr)] md:items-start"
                                >
                                  <div className="text-sm font-medium text-foreground">{row.progress}</div>
                                  <div className={`text-xs tabular-nums ${rateClass}`}>
                                    {isFirst ? `${row.numerator}只` : `${row.numerator}/${row.denominator} ${ratio}%`}
                                  </div>
                                  <div className="flex flex-wrap gap-1.5">
                                    {row.stocks.map((stock) => {
                                      const tone =
                                        stock.result === 'success'
                                          ? 'text-rose-700 dark:text-rose-300'
                                          : stock.result === 'broken'
                                            ? 'text-amber-700 dark:text-amber-300'
                                            : 'text-emerald-700 dark:text-emerald-300';
                                      const mark = isFirst ? '' : stock.result === 'success' ? '✓' : stock.result === 'broken' ? '⚡' : '✕';
                                      return (
                                        <MarketStockPreviewTooltip
                                          key={`${row.progress}-${stock.code || stock.name}`}
                                          code={stock.code}
                                          name={stock.name}
                                          summary={stock.plate ? `题材：${stock.plate}` : undefined}
                                        >
                                          <button
                                            type="button"
                                            onClick={() => handleSelectMarketStock(stock.code, stock.name)}
                                            className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs hover:bg-muted/60 ${tone}`}
                                          >
                                            {mark ? <span>{mark}</span> : null}
                                            <span>{stock.name}</span>
                                            {stock.plate ? (
                                              <span className="text-[10px] text-muted-foreground">{stock.plate}</span>
                                            ) : null}
                                          </button>
                                        </MarketStockPreviewTooltip>
                                      );
                                    })}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : activeMarketCard === '主线' ? (
                    <div className="space-y-4">
                      <div className="grid gap-4 lg:grid-cols-3">
                      {marketSnapshot.mainlineLanes.length === 0 ? (
                        <div className="rounded-[22px] border border-dashed border-border/70 bg-background/35 px-4 py-8 text-center text-sm text-muted-foreground lg:col-span-3">
                          暂无涨停主线
                        </div>
                      ) : null}
                      {marketSnapshot.mainlineLanes.map((lane) => {
                        const leader = lane.leader;
                        return (
                          <div key={lane.name} className="rounded-[22px] border border-border/70 bg-background/70 px-4 py-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="text-sm font-semibold text-foreground">{lane.name}</div>
                            {lane.value !== '--' ? (
                              <div className={`text-sm font-semibold tabular-nums ${signedToneClassName(lane.change)}`}>
                                {formatSignedPct(lane.change)}
                              </div>
                            ) : null}
                          </div>
                          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                            {lane.value !== '--' ? (
                              <span className={`tabular-nums ${signedToneClassName(lane.netFlow)}`}>{lane.value}</span>
                            ) : null}
                            <span>涨停 {lane.ztCount}</span>
                            {lane.maxHeight > 0 ? <span>最高 {lane.maxHeight}板</span> : null}
                            {lane.upCount || lane.downCount ? (
                              <span>
                                涨{lane.upCount} 跌{lane.downCount}
                              </span>
                            ) : null}
                          </div>
                          {lane.catalyst || (lane.persistDays ?? 0) > 0 ? (
                            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                              {(lane.persistDays ?? 0) > 0 ? (
                                <span className="tabular-nums">近5日活跃 {lane.persistDays} 天</span>
                              ) : null}
                              {lane.catalyst ? (
                                <span className="text-orange-600 dark:text-orange-300">催化 · {lane.catalyst}</span>
                              ) : null}
                            </div>
                          ) : null}
                          <div className="mt-5 text-xs text-muted-foreground">龙头股</div>
                          {leader ? (
                            <MarketStockPreviewTooltip code={leader.code} name={leader.name}>
                              <button
                                type="button"
                                onClick={() => handleSelectMarketStock(leader.code, leader.name)}
                                className="mt-2 flex w-full items-center justify-between gap-3 rounded-xl bg-muted/25 px-3 py-2 text-left hover:bg-muted/40"
                              >
                                <span className="truncate text-sm font-medium text-foreground">{leader.name}</span>
                                <span className="shrink-0 text-xs font-semibold text-orange-600 dark:text-orange-300">
                                  {boardHeightLabel(leader.lbc)}
                                </span>
                              </button>
                            </MarketStockPreviewTooltip>
                          ) : (
                            <div className="mt-2 text-sm text-muted-foreground">暂无涨停</div>
                          )}
                          <div className="mt-5 text-xs text-muted-foreground">跟随股</div>
                          {lane.followers.length > 0 ? (
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              {lane.followers.map((stock, index) => (
                                <MarketStockPreviewTooltip
                                  key={`${lane.name}-${stock.code || stock.name}-${index}`}
                                  code={stock.code}
                                  name={stock.name}
                                >
                                  <button
                                    type="button"
                                    onClick={() => handleSelectMarketStock(stock.code, stock.name)}
                                    className="rounded-lg border border-border/60 bg-muted/20 px-2 py-1 text-xs text-foreground hover:border-orange-300 hover:text-orange-600"
                                  >
                                    {stock.name}
                                    <span className="ml-1 text-orange-600/80 dark:text-orange-300">
                                      {boardHeightLabel(stock.lbc)}
                                    </span>
                                  </button>
                                </MarketStockPreviewTooltip>
                              ))}
                            </div>
                          ) : (
                            <div className="mt-2 text-sm text-muted-foreground">暂无跟随</div>
                          )}
                        </div>
                        );
                      })}
                      </div>

                      {marketSnapshot.relay ? (
                        canViewRelay ? (
                          <RelayCyclePanel relay={marketSnapshot.relay} onSelectStock={handleSelectMarketStock} />
                        ) : (
                          <RelayLockedPanel points={user?.points ?? 0} />
                        )
                      ) : null}
                    </div>
                  ) : (
                    <div className="grid gap-4 lg:grid-cols-3">
                      {[
                        { title: '强势股', items: marketSnapshot.payoffLists.strong },
                        { title: '热榜', items: marketSnapshot.payoffLists.hot },
                        { title: '大面', items: marketSnapshot.payoffLists.bigface },
                      ].map((column) => (
                        <div key={column.title} className="rounded-[22px] border border-border/70 bg-background/70 px-4 py-4">
                          <div className="text-sm font-semibold text-foreground">{column.title}</div>
                          <div className="mt-4 space-y-3">
                            {column.items.length === 0 ? (
                              <div className="rounded-xl bg-muted/20 px-3 py-6 text-center text-xs text-muted-foreground">
                                暂无数据
                              </div>
                            ) : null}
                            {column.items.map((item) => (
                              <div key={`${column.title}-${item.name}`} className="rounded-xl bg-muted/20 px-3 py-3">
                                <div className="flex items-center justify-between gap-3">
                                  <div className="truncate text-sm font-medium text-foreground">{item.name}</div>
                                  <div className={`text-sm font-semibold ${toneTextClassName(item.tone)}`}>{item.value}</div>
                                </div>
                                <div className="mt-1 text-xs text-muted-foreground">{item.note}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
              </div>
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-3">
              <Link
                href="/sentiment"
                className="group relative min-h-[280px] overflow-hidden rounded-[28px] border border-primary/15 bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.95),_rgba(255,255,255,0.82)_42%,_rgba(250,232,255,0.96))] p-6 transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-[0_24px_44px_rgba(192,38,211,0.14)] dark:bg-[radial-gradient(circle_at_top_left,_rgba(88,28,135,0.42),_rgba(49,46,129,0.22)_45%,_rgba(76,29,149,0.32))]"
              >
                <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-primary/12 blur-3xl transition-transform group-hover:scale-125" />
                <div className="relative flex h-full flex-col justify-between gap-6">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-xs font-medium uppercase tracking-[0.24em] text-primary/80">Theme</div>
                      <h3 className="mt-3 text-2xl font-semibold tracking-tight text-foreground">情绪指标</h3>
                    </div>
                    <Flame className="mt-1 h-5 w-5 text-primary transition-transform group-hover:scale-110" />
                  </div>
                  <div>
                    <p className="max-w-xs text-sm leading-6 text-muted-foreground">
                      市场温度、风格切换、强弱节奏。
                    </p>
                    <div className="mt-6 inline-flex items-center rounded-full border border-primary/20 bg-background/80 px-3 py-1 text-sm text-foreground">
                      进入专题
                    </div>
                  </div>
                </div>
              </Link>
              <Link
                href="/worldcup"
                className="group relative min-h-[280px] overflow-hidden rounded-[28px] border border-primary/15 bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.94),_rgba(255,255,255,0.8)_42%,_rgba(254,242,242,0.96))] p-6 transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-[0_24px_44px_rgba(192,38,211,0.14)] dark:bg-[radial-gradient(circle_at_top_left,_rgba(127,29,29,0.30),_rgba(88,28,135,0.22)_45%,_rgba(76,29,149,0.30))]"
              >
                <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-primary/10 blur-3xl transition-transform group-hover:scale-125" />
                <div className="relative flex h-full flex-col justify-between gap-6">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-xs font-medium uppercase tracking-[0.24em] text-primary/80">Event</div>
                      <h3 className="mt-3 text-2xl font-semibold text-foreground">世界杯专题</h3>
                    </div>
                    <Trophy className="mt-1 h-5 w-5 text-primary transition-transform group-hover:scale-110" />
                  </div>
                  <div>
                    <p className="max-w-xs text-sm leading-6 text-muted-foreground">
                      事件驱动内容与专题玩法入口。
                    </p>
                    <div className="mt-6 inline-flex items-center rounded-full border border-primary/20 bg-background/80 px-3 py-1 text-sm text-foreground">
                      进入专题
                    </div>
                  </div>
                </div>
              </Link>
              <div className="relative min-h-[280px] overflow-hidden rounded-[28px] border border-dashed border-primary/20 bg-background/70 p-6">
                <div className="absolute -right-8 -top-8 h-28 w-28 rounded-full bg-primary/8 blur-3xl" />
                <div className="relative flex h-full flex-col justify-between">
                  <div>
                    <div className="text-xs font-medium uppercase tracking-[0.24em] text-primary/80">More</div>
                    <h3 className="mt-3 text-2xl font-semibold tracking-tight text-foreground">更多专题</h3>
                  </div>
                  <p className="max-w-xs text-sm leading-6 text-muted-foreground">
                    预留给后续事件型、栏目型或阶段性专题。
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 修改密码对话框 */}
        <ChangePasswordDialog
          isOpen={showChangePassword}
          onClose={() => setShowChangePassword(false)}
        />

        {viewMode === 'stock' && selectedStock ? (
          <div id="stock-details-section" className="grid grid-cols-1 lg:grid-cols-3 gap-8 scroll-mt-8">
            <div className="lg:col-span-2 space-y-8">              
              <StockDetail symbol={selectedStock.symbol} />
              <StockChart symbol={selectedStock.symbol} />
              {isAuthenticated ? (
                <AIAnalysis symbol={selectedStock.symbol} />
              ) : (
                <div className="border border-border rounded-lg p-6 text-center">
                  <Bot className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium mb-2">AI 智能分析</h3>
                  <p className="text-muted-foreground mb-4">
                    登录后即可获取AI智能分析服务，包括：
                  </p>
                  <ul className="text-sm text-muted-foreground space-y-2 mb-6">
                    <li>• 技术指标分析</li>
                    <li>• 趋势预测</li>
                    <li>• 风险评估</li>
                    <li>• 个性化建议</li>
                  </ul>
                  <Link href="/login">
                    <Button>
                      立即登录
                    </Button>
                  </Link>
                </div>
              )}
            </div>
            <div>
              {isAuthenticated ? (
                <SavedStocks onSelectStock={handleSelectFromSaved} />
              ) : (
                <div className="border border-border rounded-lg p-6">
                  <h3 className="text-lg font-medium mb-2">收藏夹</h3>
                  <p className="text-muted-foreground mb-4">
                    登录后可以收藏关注的股票，随时查看最新动态
                  </p>
                  <Link href="/login">
                    <Button variant="outline" className="w-full">
                      登录以使用
                    </Button>
                  </Link>
                </div>
              )}
            </div>
          </div>
        ) : viewMode === 'stock' ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 flex items-center justify-center p-16 border border-dashed border-border rounded-lg">
              <div className="text-center">
                <Search className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h2 className="text-xl font-medium mb-2">搜索股票</h2>
                <p className="text-muted-foreground">
                  输入股票代码或名称开始探索
                </p>
              </div>
            </div>
            <div>
              {isAuthenticated ? (
                <SavedStocks onSelectStock={handleSelectFromSaved} />
              ) : (
                <div className="border border-border rounded-lg p-6">
                  <h3 className="text-lg font-medium mb-2">收藏夹</h3>
                  <p className="text-muted-foreground mb-4">
                    登录后可以收藏关注的股票，随时查看最新动态
                  </p>
                  <Link href="/login">
                    <Button variant="outline" className="w-full">
                      登录以使用
                    </Button>
                  </Link>
                </div>
              )}
            </div>
          </div>
        ) : null}
      </main>

      <footer className="border-t border-border mt-16">
        <div className="container mx-auto px-4 py-8">
          <div className="text-center text-muted-foreground text-sm">
            <p>AlphaBot &copy; {new Date().getFullYear()}</p>
            <p className="mt-2">
              免责声明：本应用提供的数据和分析仅供参考，不构成投资建议。投资决策请结合个人风险承受能力和专业意见。
            </p>
          </div>
        </div>
      </footer>

      {isAuthenticated && viewMode !== 'topic' && (
        <div ref={topicMenuRef} className="fixed bottom-4 right-4 z-40 flex flex-col items-end gap-2 md:bottom-5 md:right-5">
          {showTopicMenu && (
            <>
              <Link
                href="/worldcup"
                className="flex items-center gap-2 rounded-2xl border border-border/70 bg-background/88 px-3.5 py-2.5 text-sm text-foreground shadow-[0_10px_24px_rgba(15,23,42,0.08)] backdrop-blur transition-all duration-200 hover:-translate-y-0.5 hover:border-emerald-500/25 hover:bg-emerald-500/[0.05] dark:border-border/70 dark:bg-card/88 dark:shadow-[0_14px_30px_rgba(2,6,23,0.28)] dark:hover:border-emerald-400/25 dark:hover:bg-emerald-400/[0.08]"
                onClick={() => setShowTopicMenu(false)}
              >
                <Trophy className="h-4 w-4 text-emerald-500 dark:text-emerald-300" />
                世界杯专题
              </Link>
              <Link
                href="/sentiment"
                className="flex items-center gap-2 rounded-2xl border border-border/70 bg-background/88 px-3.5 py-2.5 text-sm text-foreground shadow-[0_10px_24px_rgba(15,23,42,0.08)] backdrop-blur transition-all duration-200 hover:-translate-y-0.5 hover:border-amber-500/25 hover:bg-amber-500/[0.05] dark:border-border/70 dark:bg-card/88 dark:shadow-[0_14px_30px_rgba(2,6,23,0.28)] dark:hover:border-amber-400/25 dark:hover:bg-amber-400/[0.08]"
                onClick={() => setShowTopicMenu(false)}
              >
                <Flame className="h-4 w-4 text-amber-500 dark:text-amber-300" />
                情绪指标
              </Link>
            </>
          )}
          <button
            type="button"
            onClick={() => setShowTopicMenu((value) => !value)}
            aria-expanded={showTopicMenu}
            className={`flex items-center rounded-full border border-border/60 bg-background/88 text-foreground shadow-[0_10px_24px_rgba(15,23,42,0.10)] backdrop-blur transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/20 hover:bg-card/96 dark:bg-slate-950/84 dark:text-white dark:shadow-[0_14px_34px_rgba(2,6,23,0.30)] dark:hover:border-cyan-400/15 dark:hover:bg-slate-950 ${
              showTopicMenu ? 'gap-2 px-3.5 py-2.5 text-sm font-medium' : 'h-11 w-11 justify-center'
            }`}
          >
            <Sparkles className={`h-4 w-4 text-cyan-500 transition-transform duration-200 dark:text-cyan-300 ${showTopicMenu ? 'rotate-45' : ''}`} />
            {showTopicMenu ? '收起专题' : <span className="sr-only">打开专题</span>}
          </button>
        </div>
      )}
    </div>
  );
}
