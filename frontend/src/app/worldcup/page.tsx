'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import WorldCupOverview from '@/components/WorldCupOverview';

export default function WorldCupPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">世界杯市场预测专题</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            融合赔率市场与预测市场的专题面板，跟踪整届赛事的信号、仓位和资金曲线。
          </p>
        </div>
        <Link href="/">
          <Button variant="outline" size="sm" className="flex items-center">
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回主页
          </Button>
        </Link>
      </div>

      <WorldCupOverview />
    </div>
  );
}
