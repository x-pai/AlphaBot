'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, ArrowRight, CalendarClock, ExternalLink, Goal, LineChart as LineChartIcon, RefreshCw, ShieldCheck } from 'lucide-react';
import { getWorldCupMatchDetail } from '@/lib/api';
import { WorldCupMatchDetail } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

function formatDollar(value: number) {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatSignedDollar(value?: number | null) {
  if (value === undefined || value === null) {
    return '--';
  }
  const prefix = value > 0 ? '+' : '';
  return `${prefix}$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function formatPct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
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

function formatPercent(value?: number) {
  if (value === undefined || value === null) {
    return '--';
  }
  return `${(value * 100).toFixed(1)}%`;
}

function strategyVariant(strategy?: string): 'success' | 'warning' | 'secondary' | 'outline' {
  if (strategy === '价值单') return 'success';
  if (strategy === '一致性单') return 'warning';
  if (strategy === '市场共识') return 'secondary';
  return 'outline';
}

function bankrollStatusVariant(status?: string): 'success' | 'warning' | 'destructive' | 'secondary' | 'outline' {
  if (status === 'won') return 'success';
  if (status === 'open') return 'warning';
  if (status === 'lost') return 'destructive';
  if (status === 'push' || status === 'void') return 'secondary';
  return 'outline';
}

function bankrollStatusLabel(status?: string) {
  if (status === 'won') return '已命中';
  if (status === 'lost') return '已失手';
  if (status === 'open') return '已下注';
  if (status === 'push') return '走水';
  if (status === 'void') return '取消';
  return '未入账';
}

export default function WorldCupMatchDetailPage() {
  const params = useParams<{ matchId: string }>();
  const [match, setMatch] = useState<WorldCupMatchDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshingAi, setRefreshingAi] = useState(false);

  useEffect(() => {
    const load = async (refresh = false) => {
      if (refresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      const response = await getWorldCupMatchDetail(params.matchId, refresh, false);
      if (response.success && response.data) {
        setMatch(response.data);
      } else {
        setMatch(null);
      }
      setLoading(false);
      setRefreshing(false);
    };

    if (params.matchId) {
      load();
    }
  }, [params.matchId]);

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="mt-4 h-[460px] w-full" />
      </div>
    );
  }

  if (!match) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center text-red-500">未找到对应比赛</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{match.stage}</Badge>
            {match.group_name && <Badge variant="outline">{match.group_name}</Badge>}
            {match.source === 'polymarket_live' && <Badge variant="success">LIVE</Badge>}
          </div>
          <h1 className="mt-3 text-2xl font-bold">
            {match.home_team} vs {match.away_team}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {formatKickoff(match.kickoff_at)} · {match.venue}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            isLoading={refreshing}
            onClick={async () => {
              setRefreshing(true);
              const response = await getWorldCupMatchDetail(params.matchId, true);
              if (response.success && response.data) {
                setMatch(response.data);
              }
              setRefreshing(false);
            }}
          >
            {!refreshing && <RefreshCw className="mr-2 h-4 w-4" />}
            刷新数据
          </Button>
          {match.external_url && (
            <a href={match.external_url} target="_blank" rel="noreferrer">
              <Button variant="outline" size="sm" className="flex items-center">
                {match.source === 'polymarket_live' ? 'Polymarket' : 'ESPN'}
                <ExternalLink className="ml-2 h-4 w-4" />
              </Button>
            </a>
          )}
          <Link href="/worldcup/matches">
            <Button variant="outline" size="sm">返回列表</Button>
          </Link>
          <Link href="/worldcup">
            <Button variant="outline" size="sm" className="flex items-center">
              <ArrowLeft className="mr-2 h-4 w-4" />
              返回专题
            </Button>
          </Link>
        </div>
      </div>

      <section className="rounded-2xl border border-border bg-card shadow-sm">
        <div className="border-b border-border px-6 py-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">{match.stage}</Badge>
                {match.group_name && <Badge variant="outline">{match.group_name}</Badge>}
                <Badge variant={match.status === 'settled' ? 'outline' : 'warning'}>
                  {match.status === 'settled' ? '已结算' : match.status === 'live' ? '进行中' : '未开赛'}
                </Badge>
              </div>
              <div className="mt-4 flex items-end gap-4">
                <div>
                  <div className="text-3xl font-semibold">{match.home_team}</div>
                  <div className="mt-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">vs</div>
                  <div className="mt-1 text-3xl font-semibold">{match.away_team}</div>
                </div>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-border bg-background px-4 py-3">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  <CalendarClock className="h-3.5 w-3.5" />
                  Kickoff
                </div>
                <div className="mt-2 text-sm font-medium">{formatKickoff(match.kickoff_at)}</div>
              </div>
              <div className="rounded-xl border border-border bg-background px-4 py-3">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  <Goal className="h-3.5 w-3.5" />
                  Venue
                </div>
                <div className="mt-2 text-sm font-medium">{match.venue}</div>
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-4 px-6 py-6 lg:grid-cols-[1.15fr_0.85fr]">
          <div>
            <div className="grid gap-3 sm:grid-cols-3">
              {(match.markets.find((market) => market.market_type === 'h2h')?.options || match.key_market.options).length > 0 ? (
                (match.markets.find((market) => market.market_type === 'h2h')?.options || match.key_market.options).map((option) => (
                  <div key={option.label} className="rounded-2xl border border-border bg-background p-4">
                    <div className="text-xs text-muted-foreground">{option.label}</div>
                    <div className="mt-2 text-3xl font-semibold">{formatProb(option.probability)}</div>
                    <div className="mt-1 text-sm text-muted-foreground">@ {option.odds.toFixed(2)}</div>
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-border bg-background p-4 sm:col-span-3">
                  <div className="text-sm font-medium">暂无主市场概率</div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    这场比赛的赔率/预测市场还没有同步进来。
                  </div>
                </div>
              )}
            </div>

            <div className="mt-4 rounded-2xl border border-primary/20 bg-primary/5 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-xs text-muted-foreground">市场主推方向</div>
                  <div className="mt-1 text-2xl font-semibold">{match.featured_pick.side}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-muted-foreground">建议下注金额</div>
                  <div className="mt-1 text-2xl font-semibold">{formatDollar(match.featured_pick.stake_amount)}</div>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Badge variant={strategyVariant(match.featured_pick.strategy)}>
                  {match.featured_pick.strategy}
                </Badge>
                <Badge variant="outline">信心 {match.featured_pick.confidence}</Badge>
                <Badge variant="warning">Edge {match.featured_pick.edge}%</Badge>
                <Badge variant="secondary">仓位 {match.featured_pick.stake_pct}%</Badge>
              </div>
              {(match.featured_pick.book_probability !== undefined || match.featured_pick.fair_probability !== undefined) && (
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl border border-primary/10 bg-background px-3 py-3">
                    <div className="text-xs text-muted-foreground">比较对象</div>
                    <div className="mt-1 font-medium">{match.featured_pick.signal_label || match.featured_pick.side}</div>
                  </div>
                  <div className="rounded-xl border border-primary/10 bg-background px-3 py-3">
                    <div className="text-xs text-muted-foreground">Book 概率</div>
                    <div className="mt-1 font-medium">{formatPercent(match.featured_pick.book_probability)}</div>
                  </div>
                  <div className="rounded-xl border border-primary/10 bg-background px-3 py-3">
                    <div className="text-xs text-muted-foreground">
                      {match.featured_pick.strategy === '价值单' ? 'Fair / Polymarket' : '比较基准'}
                    </div>
                    <div className="mt-1 font-medium">
                      {match.featured_pick.fair_probability !== undefined
                        ? formatPercent(match.featured_pick.fair_probability)
                        : `Edge ${match.featured_pick.edge.toFixed(2)}%`}
                    </div>
                  </div>
                </div>
              )}
              <div className="mt-4 space-y-2">
                {match.featured_pick.rationale.map((item) => (
                  <div key={item} className="rounded-xl border border-primary/10 bg-background px-3 py-2 text-sm text-muted-foreground">
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <Card className="mt-4 rounded-2xl">
              <CardHeader className="border-b border-border pb-4">
                <div className="flex items-center justify-between gap-3">
                  <CardTitle className="text-base">AI 解读</CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    isLoading={refreshingAi}
                    onClick={async () => {
                      setRefreshingAi(true);
                      const response = await getWorldCupMatchDetail(params.matchId, false, true);
                      if (response.success && response.data) {
                        setMatch(response.data);
                      }
                      setRefreshingAi(false);
                    }}
                  >
                    {!refreshingAi && <RefreshCw className="mr-2 h-4 w-4" />}
                    刷新 AI 解读
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4 pt-5">
                {match.ai_analysis_error ? (
                  <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4">
                    <div className="text-xs text-destructive">AI 分析出错</div>
                    <div className="mt-2 text-sm leading-6 text-muted-foreground">{match.ai_analysis_error}</div>
                  </div>
                ) : match.ai_analysis ? (
                  <>
                    <div className="rounded-xl border border-border bg-background p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="text-xs text-muted-foreground">总结</div>
                        <Badge variant="outline">{match.ai_analysis.source === 'llm' ? 'LLM' : '未知来源'}</Badge>
                      </div>
                      <div className="mt-2 text-sm leading-6">{match.ai_analysis.summary || '暂无总结。'}</div>
                      {match.ai_analysis.generated_at && (
                        <div className="mt-3 text-xs text-muted-foreground">
                          生成时间：{formatKickoff(match.ai_analysis.generated_at)}
                        </div>
                      )}
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="rounded-xl border border-border bg-background p-4">
                        <div className="text-xs text-muted-foreground">支持逻辑</div>
                        <div className="mt-2 text-sm leading-6">{match.ai_analysis.bull_case || '--'}</div>
                      </div>
                      <div className="rounded-xl border border-border bg-background p-4">
                        <div className="text-xs text-muted-foreground">反方风险</div>
                        <div className="mt-2 text-sm leading-6">{match.ai_analysis.bear_case || '--'}</div>
                      </div>
                    </div>
                    <div className="rounded-xl border border-border bg-background p-4">
                      <div className="text-xs text-muted-foreground">市场解读</div>
                      <div className="mt-2 text-sm leading-6">{match.ai_analysis.market_note || '--'}</div>
                    </div>
                    <div className="rounded-xl border border-border bg-background p-4">
                      <div className="text-xs text-muted-foreground">信心说明</div>
                      <div className="mt-2 text-sm leading-6">{match.ai_analysis.confidence_note || '--'}</div>
                    </div>
                    <div className="rounded-xl border border-border bg-background p-4">
                      <div className="text-xs text-muted-foreground">风险提示</div>
                      <div className="mt-2 space-y-2">
                        {(match.ai_analysis.risk_flags || []).length > 0 ? (
                          match.ai_analysis.risk_flags?.map((item) => (
                            <div key={item} className="text-sm text-muted-foreground">
                              {item}
                            </div>
                          ))
                        ) : (
                          <div className="text-sm text-muted-foreground">暂无额外风险提示。</div>
                        )}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="rounded-xl border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
                    当前还没有可展示的 AI 解读。
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="rounded-2xl">
            <CardHeader className="border-b border-border pb-4">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">Polymarket 参考概率</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pt-5">
              <div className="space-y-3">
                {Object.entries(match.polymarket_probabilities).length > 0 ? (
                  Object.entries(match.polymarket_probabilities).map(([key, value]) => (
                    <div key={key} className="rounded-xl border border-border bg-background p-4">
                      <div className="flex items-center justify-between text-sm">
                        <span>
                          {key === 'home'
                            ? match.home_team
                            : key === 'draw'
                              ? '平局'
                              : key === 'away'
                                ? match.away_team
                                : key}
                        </span>
                        <span className="font-semibold">{formatPct(value)}</span>
                      </div>
                      <div className="mt-3 h-2 rounded-full bg-muted">
                        <div className="h-2 rounded-full bg-primary" style={{ width: `${value * 100}%` }} />
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-xl border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
                    暂无 Polymarket 概率数据。
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <Card className="mt-6 rounded-2xl">
        <CardHeader className="border-b border-border pb-4">
          <CardTitle className="text-base">Bankroll 入账状态</CardTitle>
        </CardHeader>
        <CardContent className="pt-5">
          {match.bankroll_bet ? (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-xl border border-border bg-background p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs text-muted-foreground">状态</div>
                  <Badge variant={bankrollStatusVariant(match.bankroll_bet.status)}>
                    {bankrollStatusLabel(match.bankroll_bet.status)}
                  </Badge>
                </div>
                <div className="mt-2 font-semibold">{match.bankroll_bet.side || '--'}</div>
                <div className="mt-1 text-sm text-muted-foreground">
                  {match.bankroll_bet.signal_label || '未记录标的'}
                </div>
              </div>
              <div className="rounded-xl border border-border bg-background p-4">
                <div className="text-xs text-muted-foreground">下注快照</div>
                <div className="mt-2 font-semibold">
                  {formatDollar(match.bankroll_bet.stake_amount || 0)}
                  <span className="ml-2 text-sm font-normal text-muted-foreground">
                    @ {(match.bankroll_bet.odds || 0).toFixed(2)}
                  </span>
                </div>
                <div className="mt-1 text-sm text-muted-foreground">
                  仓位 {match.bankroll_bet.stake_pct || 0}% · {match.bankroll_bet.strategy || '--'}
                </div>
              </div>
              <div className="rounded-xl border border-border bg-background p-4">
                <div className="text-xs text-muted-foreground">已实现盈亏</div>
                <div className="mt-2 font-semibold">{formatSignedDollar(match.bankroll_bet.pnl)}</div>
                <div className="mt-1 text-sm text-muted-foreground">
                  赛果 {match.bankroll_bet.result_label || '待结算'}
                </div>
              </div>
              <div className="rounded-xl border border-border bg-background p-4">
                <div className="text-xs text-muted-foreground">时间</div>
                <div className="mt-2 text-sm font-medium">下注：{formatKickoff(match.bankroll_bet.placed_at || undefined)}</div>
                <div className="mt-1 text-sm text-muted-foreground">
                  结算：{formatKickoff(match.bankroll_bet.settled_at || undefined)}
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
              当前这场比赛还没有进入 bankroll 账本。通常需要到开赛时间，且形成有效的 `h2h` 推荐后才会自动落账。
            </div>
          )}
        </CardContent>
      </Card>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        {match.markets.length > 0 ? (
          match.markets.map((market) => (
            <Card key={`${market.market_type}-${market.title}`} className="rounded-2xl">
              <CardHeader className="border-b border-border pb-4">
                <CardTitle className="text-base">
                  {market.title}{market.line ? ` · ${market.line}` : ''}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-5">
                <div className="space-y-3">
                  {market.options.map((option) => (
                    <div key={option.label} className="rounded-md bg-muted/60 p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{option.label}</span>
                        <span>{option.odds.toFixed(2)}</span>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        去水后概率 {formatPct(option.probability)}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))
        ) : (
          <Card className="rounded-2xl lg:col-span-3">
            <CardContent className="p-6 text-sm text-muted-foreground">
              当前没有可展示的盘口明细，等待真实赔率或预测市场同步。
            </CardContent>
          </Card>
        )}
      </div>

      <Card className="mt-6 rounded-2xl">
        <CardHeader className="border-b border-border pb-4">
          <div className="flex items-center gap-2">
            <LineChartIcon className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">盘口变化</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="pt-5">
          <div className="grid gap-3 md:grid-cols-2">
            {match.line_movement.length > 0 ? (
              match.line_movement.map((item) => (
                <div key={item.label} className="rounded-2xl border border-border bg-background p-4">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium">{item.label}</div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="mt-2 text-sm text-muted-foreground">盘口 {item.line}</div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                    <div className="rounded-lg bg-muted/50 px-3 py-2">
                      <div className="text-xs text-muted-foreground">主队</div>
                      <div className="mt-1 font-medium">{item.home_odds.toFixed(2)}</div>
                    </div>
                    <div className="rounded-lg bg-muted/50 px-3 py-2">
                      <div className="text-xs text-muted-foreground">客队</div>
                      <div className="mt-1 font-medium">{item.away_odds.toFixed(2)}</div>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-dashed border-border bg-background p-4 text-sm text-muted-foreground md:col-span-2">
                暂无盘口变化数据。
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
