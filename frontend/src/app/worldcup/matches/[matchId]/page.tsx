'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, ArrowRight, CalendarClock, Goal, LineChart as LineChartIcon, ShieldCheck } from 'lucide-react';
import { getWorldCupMatchDetail } from '@/lib/api';
import { WorldCupMatchDetail } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

function formatDollar(value: number) {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatPct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatProb(value: number) {
  return `${Math.round(value * 100)}c`;
}

export default function WorldCupMatchDetailPage() {
  const params = useParams<{ matchId: string }>();
  const [match, setMatch] = useState<WorldCupMatchDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const response = await getWorldCupMatchDetail(params.matchId);
      if (response.success && response.data) {
        setMatch(response.data);
      } else {
        setMatch(null);
      }
      setLoading(false);
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
          </div>
          <h1 className="mt-3 text-2xl font-bold">
            {match.home_team} vs {match.away_team}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {new Date(match.kickoff_at).toLocaleString('zh-CN')} · {match.venue}
          </p>
        </div>
        <div className="flex items-center gap-3">
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
                  {match.status === 'settled' ? '已结算' : '未开赛'}
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
                <div className="mt-2 text-sm font-medium">{new Date(match.kickoff_at).toLocaleString('zh-CN')}</div>
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
              {(match.markets.find((market) => market.market_type === 'h2h')?.options || []).map((option) => (
                <div key={option.label} className="rounded-2xl border border-border bg-background p-4">
                  <div className="text-xs text-muted-foreground">{option.label}</div>
                  <div className="mt-2 text-3xl font-semibold">{formatProb(option.probability)}</div>
                  <div className="mt-1 text-sm text-muted-foreground">@ {option.odds.toFixed(2)}</div>
                </div>
              ))}
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
                <Badge variant="outline">信心 {match.featured_pick.confidence}</Badge>
                <Badge variant="warning">Edge {match.featured_pick.edge}%</Badge>
                <Badge variant="secondary">仓位 {match.featured_pick.stake_pct}%</Badge>
              </div>
              <div className="mt-4 space-y-2">
                {match.featured_pick.rationale.map((item) => (
                  <div key={item} className="rounded-xl border border-primary/10 bg-background px-3 py-2 text-sm text-muted-foreground">
                    {item}
                  </div>
                ))}
              </div>
            </div>
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
                {Object.entries(match.polymarket_probabilities).map(([key, value]) => (
                  <div key={key} className="rounded-xl border border-border bg-background p-4">
                    <div className="flex items-center justify-between text-sm">
                      <span>{key === 'home' ? match.home_team : key === 'draw' ? '平局' : match.away_team}</span>
                      <span className="font-semibold">{formatPct(value)}</span>
                    </div>
                    <div className="mt-3 h-2 rounded-full bg-muted">
                      <div className="h-2 rounded-full bg-primary" style={{ width: `${value * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        {match.markets.map((market) => (
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
        ))}
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
            {match.line_movement.map((item) => (
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
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
