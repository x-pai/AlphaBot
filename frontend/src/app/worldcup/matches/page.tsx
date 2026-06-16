'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, ChevronRight, Goal, Hourglass } from 'lucide-react';
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

export default function WorldCupMatchesPage() {
  const [matches, setMatches] = useState<WorldCupMatchSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const response = await getWorldCupMatches(status ? { status } : {});
      if (response.success && response.data) {
        setMatches(response.data);
      } else {
        setMatches([]);
      }
      setLoading(false);
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
                    </div>
                    <Badge variant={match.status === 'settled' ? 'outline' : 'warning'}>
                      {match.status === 'settled' ? '已结算' : '未开赛'}
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
                    {match.key_market.options.slice(0, 2).map((option) => (
                      <div key={option.label} className="rounded-xl border border-border bg-background px-3 py-3">
                        <div className="text-[11px] text-muted-foreground">{option.label}</div>
                        <div className="mt-1 text-lg font-semibold">{formatProb(option.probability)}</div>
                        <div className="text-xs text-muted-foreground">@ {option.odds.toFixed(2)}</div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-5 rounded-xl border border-primary/20 bg-primary/5 p-4">
                    <div className="text-xs text-muted-foreground">模型推荐</div>
                    <div className="mt-1 font-semibold">{match.featured_pick.side}</div>
                    <div className="mt-3 flex items-center justify-between text-sm">
                      <span>信心 {match.featured_pick.confidence}</span>
                      <span>{formatDollar(match.featured_pick.stake_amount)}</span>
                    </div>
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
