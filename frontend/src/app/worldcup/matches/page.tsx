'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, ChevronRight, Goal, Hourglass, RefreshCw } from 'lucide-react';
import { getWorldCupMatches } from '@/lib/api';
import { WorldCupMatchSummary } from '@/types';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

const FILTERS = [
  { label: '全部', value: '' },
  { label: '未开赛', value: 'upcoming' },
  { label: '已结算', value: 'settled' },
];

function formatDollar(value: number) {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatProb(value: number) {
  return `${Math.round(value * 100)}c`;
}

function strategyVariant(strategy?: string): 'success' | 'warning' | 'secondary' | 'outline' {
  if (strategy === '价值单') return 'success';
  if (strategy === '一致性单') return 'warning';
  if (strategy === '市场共识') return 'secondary';
  return 'outline';
}

function signalTierVariant(signalTier?: string | null): 'default' | 'secondary' | 'outline' {
  if (signalTier === 'core') return 'default';
  if (signalTier === 'satellite') return 'secondary';
  return 'outline';
}

function signalTierLabel(signalTier?: string | null) {
  if (signalTier === 'core') return '主仓';
  if (signalTier === 'satellite') return '卫星';
  if (signalTier === 'probe') return '试探';
  return '待定';
}

function signalGradeVariant(signalGrade?: string | null): 'success' | 'warning' | 'destructive' | 'outline' {
  if (signalGrade === 'strong') return 'success';
  if (signalGrade === 'caution') return 'warning';
  if (signalGrade === 'high_risk') return 'destructive';
  return 'outline';
}

function signalGradeLabel(signalGrade?: string | null) {
  if (signalGrade === 'strong') return '强信号';
  if (signalGrade === 'caution') return '谨慎';
  if (signalGrade === 'high_risk') return '高风险';
  return '待定';
}

export default function WorldCupMatchesPage() {
  const [matches, setMatches] = useState<WorldCupMatchSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [status, setStatus] = useState('');

  useEffect(() => {
    const load = async (refresh = false) => {
      if (refresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      const response = await getWorldCupMatches(status ? { status, refresh } : { refresh });
      if (response.success && response.data) {
        setMatches(response.data);
      } else {
        setMatches([]);
      }
      setLoading(false);
      setRefreshing(false);
    };

    load();
  }, [status]);

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">世界杯事件流</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            按更接近预测市场的卡片方式浏览所有比赛和推荐信号。
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            isLoading={refreshing}
            onClick={async () => {
              setRefreshing(true);
              const response = await getWorldCupMatches(status ? { status, refresh: true } : { refresh: true });
              if (response.success && response.data) {
                setMatches(response.data);
              }
              setRefreshing(false);
            }}
          >
            {!refreshing && <RefreshCw className="mr-2 h-4 w-4" />}
            刷新数据
          </Button>
          <Link href="/worldcup">
            <Button variant="outline" size="sm">返回专题</Button>
          </Link>
          <Link href="/">
            <Button variant="outline" size="sm" className="flex items-center">
              <ArrowLeft className="mr-2 h-4 w-4" />
              返回主页
            </Button>
          </Link>
        </div>
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        {FILTERS.map((filter) => (
          <Button
            key={filter.label}
            variant={status === filter.value ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setStatus(filter.value)}
          >
            {filter.label}
          </Button>
        ))}
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-72 w-full" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {matches.map((match) => (
            <Link key={match.match_id} href={`/worldcup/matches/${match.match_id}`}>
              <Card className="h-full rounded-2xl transition-colors hover:bg-muted/40">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">{match.stage}</Badge>
                      {match.group_name && <Badge variant="outline">{match.group_name}</Badge>}
                      {match.source === 'polymarket_live' && <Badge variant="success">LIVE</Badge>}
                    </div>
                    <Badge variant={match.status === 'settled' ? 'outline' : 'warning'}>
                      {match.status === 'settled' ? '已结算' : match.status === 'live' ? '进行中' : '未开赛'}
                    </Badge>
                  </div>

                  <div className="mt-4 flex items-center justify-between">
                    <div>
                      <div className="text-lg font-semibold">{match.home_team}</div>
                      <div className="mt-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">vs</div>
                      <div className="mt-1 text-lg font-semibold">{match.away_team}</div>
                    </div>
                    <ChevronRight className="h-5 w-5 text-muted-foreground" />
                  </div>

                  <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
                    <Hourglass className="h-4 w-4" />
                    {new Date(match.kickoff_at).toLocaleString('zh-CN')}
                  </div>

                  <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
                    <Goal className="h-4 w-4" />
                    {match.venue}
                  </div>

                  <div className="mt-5 grid grid-cols-2 gap-2">
                    {match.key_market.options.length > 0 ? (
                      match.key_market.options.slice(0, 2).map((option) => (
                        <div key={option.label} className="rounded-xl border border-border bg-background px-3 py-3">
                          <div className="text-[11px] text-muted-foreground">{option.label}</div>
                          <div className="mt-1 text-lg font-semibold">{formatProb(option.probability)}</div>
                          <div className="text-xs text-muted-foreground">@ {option.odds.toFixed(2)}</div>
                        </div>
                      ))
                    ) : (
                      <div className="col-span-2 rounded-xl border border-dashed border-border bg-background px-3 py-3 text-sm text-muted-foreground">
                        盘口待同步
                      </div>
                    )}
                  </div>

                  <div className="mt-5 rounded-xl border border-primary/20 bg-primary/5 p-4">
                    <div className="text-xs text-muted-foreground">模型推荐</div>
                    <div className="mt-1 font-semibold">{match.featured_pick.side}</div>
                    <div className="mt-3 flex items-center justify-between text-sm">
                      <span>信心 {match.featured_pick.confidence}</span>
                      <span>{formatDollar(match.featured_pick.stake_amount)}</span>
                    </div>
                    <div className="mt-3">
                      <Badge variant={strategyVariant(match.featured_pick.strategy)}>
                        {match.featured_pick.strategy}
                      </Badge>
                      {match.featured_pick.signal_tier && (
                        <Badge variant={signalTierVariant(match.featured_pick.signal_tier)} className="ml-2">
                          {signalTierLabel(match.featured_pick.signal_tier)}
                        </Badge>
                      )}
                      {match.featured_pick.signal_grade && (
                        <Badge variant={signalGradeVariant(match.featured_pick.signal_grade)} className="ml-2">
                          {signalGradeLabel(match.featured_pick.signal_grade)}
                        </Badge>
                      )}
                    </div>
                    {match.featured_pick.warning_message && (
                      <div className="mt-3 rounded-xl border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
                        {match.featured_pick.warning_message}
                      </div>
                    )}
                  </div>

                  <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
                    <span>{match.key_market.title}</span>
                    <span>{match.key_market.line || '主盘'}</span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
