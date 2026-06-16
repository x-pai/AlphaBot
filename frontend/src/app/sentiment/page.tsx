'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft, Flame, LineChart, TimerReset } from 'lucide-react';
import SentimentMetricsPrototype from '@/components/SentimentMetricsPrototype';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export default function SentimentPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6 overflow-hidden rounded-[28px] border border-amber-500/20 bg-card">
        <div className="relative px-6 py-6">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(251,191,36,0.16),transparent_34%),linear-gradient(135deg,rgba(251,191,36,0.08),transparent_55%)]" />
          <div className="relative flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
                Chart-First Signal Lab
              </div>
              <div className="mt-3 flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-amber-500/20 bg-slate-950 text-amber-300">
                  <Flame className="h-5 w-5" />
                </div>
                <h1 className="text-3xl font-bold text-foreground">情绪指标</h1>
              </div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                用图区间回放来观察情绪阈值、极端点与市场回落速度，首屏先把重点图表亮出来。
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Badge variant="warning"><LineChart className="mr-1 h-3.5 w-3.5" />阈值读图</Badge>
                <Badge variant="warning"><TimerReset className="mr-1 h-3.5 w-3.5" />区间回放</Badge>
                <Badge variant="outline">原型验证中</Badge>
              </div>
            </div>
            <Link href="/">
              <Button variant="outline" size="sm" className="flex items-center bg-background/70">
                <ArrowLeft className="mr-2 h-4 w-4" />
                返回主页
              </Button>
            </Link>
          </div>
        </div>
      </div>

      <SentimentMetricsPrototype />
    </div>
  );
}
