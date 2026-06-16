'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  ArrowRight,
  CalendarClock,
  CircleDollarSign,
  ExternalLink,
  Goal,
  Hourglass,
  LineChart as LineChartIcon,
  RefreshCw,
  Trophy,
  TrendingUp,
} from 'lucide-react';
import { getWorldCupOverview } from '@/lib/api';
import { WorldCupOverview as WorldCupOverviewData } from '@/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Skeleton } from './ui/skeleton';

function formatDollar(value: number) {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatPct(value: number) {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatProb(value: number) {
  return `${Math.round(value * 100)}c`;
}

function formatKickoff(value?: string) {
  if (!value) {
    return '--';
  }
  return new Date(value).toLocaleString('zh-CN');
}

function strategyVariant(strategy?: string): 'success' | 'warning' | 'secondary' | 'outline' {
  if (strategy === '价值单') return 'success';
  if (strategy === '一致性单') return 'warning';
  if (strategy === '市场共识') return 'secondary';
  return 'outline';
}

export default function WorldCupOverview() {
  const [overview, setOverview] = useState<WorldCupOverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async (refresh = false) => {
      if (refresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      const response = await getWorldCupOverview(refresh);
      if (response.success && response.data) {
        setOverview(response.data);
        setError(null);
      } else {
        setError(response.error || '加载世界杯专题失败');
      }
      setLoading(false);
      setRefreshing(false);
    };

    load();
  }, []);

  const highlight = useMemo(() => {
    if (!overview?.featured_matches?.length) {
      return null;
    }
    return overview.featured_matches[0];
  }, [overview]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-[420px] w-full" />
      </div>
    );
  }

  if (error || !overview) {
    return (
      <Card>
        <CardContent className="p-6 text-center text-red-500">
          {error || '加载世界杯专题失败'}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card shadow-sm">
        <div className="border-b border-border px-6 py-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Goal className="h-5 w-5 text-primary" />
                <h2 className="text-xl font-semibold">{overview.tournament} 市场预测专题</h2>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                用赔率市场与预测市场构建一套可持续更新的世界杯事件面板。
              </p>
              {overview.last_updated_at && (
                <p className="mt-2 text-xs text-muted-foreground">
                  最近同步：{formatKickoff(overview.last_updated_at)}
                </p>
              )}
            </div>
            <div className="flex flex-col items-stretch gap-3">
              <Button
                variant="outline"
                size="sm"
                isLoading={refreshing}
                onClick={async () => {
                  setRefreshing(true);
                  const response = await getWorldCupOverview(true);
                  if (response.success && response.data) {
                    setOverview(response.data);
                    setError(null);
                  } else {
                    setError(response.error || '刷新世界杯专题失败');
                  }
                  setRefreshing(false);
                }}
                className="self-end"
              >
                {!refreshing && <RefreshCw className="mr-2 h-4 w-4" />}
                刷新数据
              </Button>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-xl border border-border bg-background px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Bankroll</div>
                  <div className="mt-1 text-lg font-semibold">{formatDollar(overview.bankroll)}</div>
                </div>
                <div className="rounded-xl border border-border bg-background px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">ROI</div>
                  <div className="mt-1 text-lg font-semibold">{formatPct(overview.roi)}</div>
                </div>
                <div className="rounded-xl border border-border bg-background px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Open</div>
                  <div className="mt-1 text-lg font-semibold">{overview.open_positions}</div>
                </div>
                <div className="rounded-xl border border-border bg-background px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Settled</div>
                  <div className="mt-1 text-lg font-semibold">{overview.settled_matches}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-4 px-6 py-6 lg:grid-cols-[1.15fr_0.85fr]">
          {highlight && (
            <div className="rounded-2xl border border-border bg-background p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{highlight.stage}</Badge>
                  {highlight.group_name && <Badge variant="outline">{highlight.group_name}</Badge>}
                  {highlight.source === 'polymarket_live' && <Badge variant="success">LIVE</Badge>}
                  <Badge variant="warning">主推</Badge>
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatKickoff(highlight.kickoff_at)}
                </div>
              </div>

              <div className="mt-4 flex items-end justify-between gap-4">
                <div>
                  <div className="text-2xl font-semibold">{highlight.home_team}</div>
                  <div className="mt-1 text-sm text-muted-foreground">vs {highlight.away_team}</div>
                </div>
                <div className="rounded-full border border-border px-4 py-2 text-sm font-medium text-muted-foreground">
                  {highlight.venue}
                </div>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                {highlight.key_market.options.length > 0 ? (
                  highlight.key_market.options.map((option) => (
                    <div key={option.label} className="rounded-xl border border-border bg-card p-4">
                      <div className="text-xs text-muted-foreground">{option.label}</div>
                      <div className="mt-2 text-2xl font-semibold">{formatProb(option.probability)}</div>
                      <div className="mt-1 text-sm text-muted-foreground">@ {option.odds.toFixed(2)}</div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-xl border border-dashed border-border bg-card p-4 sm:col-span-3">
                    <div className="text-sm font-medium">暂无预测市场</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      真实赛程已接入，等待对应比赛的盘口或预测市场同步。
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-5 rounded-xl border border-primary/20 bg-primary/5 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="text-xs text-muted-foreground">推荐方向</div>
                    <div className="mt-1 text-lg font-semibold">{highlight.featured_pick.side}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-muted-foreground">建议金额</div>
                    <div className="mt-1 text-lg font-semibold">{formatDollar(highlight.featured_pick.stake_amount)}</div>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge variant={strategyVariant(highlight.featured_pick.strategy)}>
                    {highlight.featured_pick.strategy}
                  </Badge>
                  <Badge variant="outline">信心 {highlight.featured_pick.confidence}</Badge>
                  <Badge variant="warning">Edge {highlight.featured_pick.edge}%</Badge>
                  <Badge variant="secondary">仓位 {highlight.featured_pick.stake_pct}%</Badge>
                </div>
                <div className="mt-4">
                  <div className="flex flex-wrap gap-2">
                    <Link href={`/worldcup/matches/${highlight.match_id}`}>
                      <Button size="sm" className="flex items-center">
                        打开事件页
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </Button>
                    </Link>
                    {highlight.external_url && (
                      <a href={highlight.external_url} target="_blank" rel="noreferrer">
                        <Button size="sm" variant="outline" className="flex items-center">
                          {highlight.source === 'polymarket_live' ? 'Polymarket' : 'ESPN'}
                          <ExternalLink className="ml-2 h-4 w-4" />
                        </Button>
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="grid gap-4">
            <Card>
              <CardHeader className="border-b border-border pb-4">
                <div className="flex items-center gap-2">
                  <Trophy className="h-4 w-4 text-primary" />
                  <CardTitle className="text-base">重点市场</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="pt-5">
                <div className="space-y-3">
                  {overview.market_heat.map((item) => (
                    <div key={item.label} className="rounded-xl border border-border bg-background p-4">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">{item.label}</span>
                        <span className="font-semibold">{item.value.toFixed(0)}%</span>
                      </div>
                      <div className="mt-3 h-2 rounded-full bg-muted">
                        <div
                          className="h-2 rounded-full bg-primary"
                          style={{ width: `${Math.min(100, item.value)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="border-b border-border pb-4">
                <div className="flex items-center gap-2">
                  <Hourglass className="h-4 w-4 text-primary" />
                  <CardTitle className="text-base">下一场时间</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="pt-5">
                <div className="text-2xl font-semibold">
                  {formatKickoff(overview.next_match_at)}
                </div>
                <div className="mt-2 text-sm text-muted-foreground">
                  默认以最近一场高关注度比赛作为专题流的首条卡片。
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader className="border-b border-border pb-4">
            <div className="flex items-center gap-2">
              <LineChartIcon className="h-4 w-4 text-primary" />
              <CardTitle className="text-base">资金曲线</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="h-[320px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={overview.bankroll_curve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="label" tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }} />
                  <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--card)',
                      borderColor: 'var(--border)',
                      borderRadius: '0.5rem',
                    }}
                    formatter={(value: number) => [formatDollar(Number(value)), '资金']}
                  />
                  <Line
                    type="monotone"
                    dataKey="bankroll"
                    stroke="#2563eb"
                    strokeWidth={3}
                    dot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4">
          <Card>
            <CardHeader className="border-b border-border pb-4">
              <CardTitle className="text-base">阶段表现</CardTitle>
            </CardHeader>
            <CardContent className="pt-5">
              <div className="space-y-3">
                {overview.phase_breakdown.map((phase) => (
                  <div key={phase.phase} className="rounded-lg border border-border p-3">
                    <div className="flex items-center justify-between">
                      <div className="font-medium">{phase.phase}</div>
                      <Badge variant={phase.roi >= 0 ? 'success' : 'destructive'}>
                        {formatPct(phase.roi)}
                      </Badge>
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      {phase.matches} 场 · 命中率 {phase.hit_rate.toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b border-border pb-4">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">市场热度</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pt-5">
              <div className="space-y-3">
                {overview.market_heat.map((item) => (
                  <div key={item.label}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span>{item.label}</span>
                      <span className="font-medium">{item.value.toFixed(0)}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-muted">
                      <div
                        className="h-2 rounded-full bg-primary"
                        style={{ width: `${Math.min(100, item.value)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <section className="rounded-2xl border border-border bg-card shadow-sm">
        <div className="border-b border-border px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold">事件流</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                更接近市场面板的卡片布局，优先展示概率、方向和金额。
              </p>
            </div>
            <Link href="/worldcup/matches">
              <Button variant="outline" size="sm">全部比赛</Button>
            </Link>
          </div>
        </div>
        <div className="grid gap-4 px-6 py-6 md:grid-cols-3">
          {overview.featured_matches.map((match) => (
            <Link key={match.match_id} href={`/worldcup/matches/${match.match_id}`}>
              <div className="h-full rounded-2xl border border-border bg-background p-4 transition-colors hover:bg-muted/50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">{match.stage}</Badge>
                    {match.source === 'polymarket_live' && <Badge variant="success">LIVE</Badge>}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {new Date(match.kickoff_at).toLocaleDateString('zh-CN')}
                  </span>
                </div>
                <div className="mt-4 space-y-1">
                  <div className="text-lg font-semibold">{match.home_team}</div>
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">vs</div>
                  <div className="text-lg font-semibold">{match.away_team}</div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  {match.key_market.options.length > 0 ? (
                    match.key_market.options.slice(0, 2).map((option) => (
                      <div key={option.label} className="rounded-xl border border-border bg-card px-3 py-3">
                        <div className="text-[11px] text-muted-foreground">{option.label}</div>
                        <div className="mt-1 text-lg font-semibold">{formatProb(option.probability)}</div>
                      </div>
                    ))
                  ) : (
                    <div className="col-span-2 rounded-xl border border-dashed border-border bg-card px-3 py-3 text-sm text-muted-foreground">
                      待同步盘口
                    </div>
                  )}
                </div>
                <div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-3">
                  <div className="text-xs text-muted-foreground">推荐</div>
                  <div className="mt-1 font-semibold">{match.featured_pick.side}</div>
                  <div className="mt-2 flex items-center justify-between text-sm">
                    <span>信心 {match.featured_pick.confidence}</span>
                    <span>{formatDollar(match.featured_pick.stake_amount)}</span>
                  </div>
                  <div className="mt-3">
                    <Badge variant={strategyVariant(match.featured_pick.strategy)}>
                      {match.featured_pick.strategy}
                    </Badge>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
