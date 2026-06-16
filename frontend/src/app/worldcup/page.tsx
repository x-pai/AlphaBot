'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft, Activity, CircleDollarSign, Trophy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import WorldCupOverview from '@/components/WorldCupOverview';
import { Badge } from '@/components/ui/badge';

export default function WorldCupPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6 overflow-hidden rounded-[28px] border border-emerald-500/20 bg-card">
        <div className="relative px-6 py-6">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(16,185,129,0.18),transparent_34%),linear-gradient(135deg,rgba(16,185,129,0.08),transparent_60%)]" />
          <div className="relative flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
                Event Market Desk
              </div>
              <div className="mt-3 flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-emerald-500/20 bg-slate-950 text-emerald-300">
                  <Trophy className="h-5 w-5" />
                </div>
                <h1 className="text-3xl font-bold">世界杯专题</h1>
              </div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                把赔率市场、预测市场和 bankroll 执行放在同一屏里，直接跟踪整届赛事的仓位变化。
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Badge variant="success"><Activity className="mr-1 h-3.5 w-3.5" />市场概率</Badge>
                <Badge variant="success"><CircleDollarSign className="mr-1 h-3.5 w-3.5" />Bankroll</Badge>
                <Badge variant="outline">赛事执行面板</Badge>
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

      <WorldCupOverview />
    </div>
  );
}
