'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import SentimentMetricsPrototype from '@/components/SentimentMetricsPrototype';
import { Button } from '@/components/ui/button';

export default function SentimentPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">情绪指标统计</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            原型页先验证信息架构和图表交互，后续可无缝接入真实数据接口。
          </p>
        </div>
        <Link href="/">
          <Button variant="outline" size="sm" className="flex items-center">
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回主页
          </Button>
        </Link>
      </div>

      <SentimentMetricsPrototype />
    </div>
  );
}
