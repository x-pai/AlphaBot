'use client';

import Link from 'next/link';
import React, { useEffect, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

interface CollectionItem {
  entry_slug: string;
  title: string;
  published_at: string;
  url: string;
}

export default function DailyMarketBriefCollectionPage() {
  const [items, setItems] = useState<CollectionItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/reports/collections/daily-market-brief`);
        const json = await response.json();
        if (!active) return;
        if (json.success && json.data) {
          setItems((json.data.items || []) as CollectionItem[]);
        } else {
          setError(json.error || '加载合集失败');
        }
      } catch {
        if (active) {
          setError('加载合集失败');
        }
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="container mx-auto px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold dark:text-white">市场日报</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            查看最近 30 天自动发布的市场报告，盘前日报聚焦隔夜变化与当天开盘计划。
          </p>
        </div>
        <Link href="/">
          <Button variant="outline" size="sm" className="flex items-center">
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回主页
          </Button>
        </Link>
      </div>

      {error ? (
        <p className="text-sm text-muted-foreground">{error}</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">还没有已发布内容。</p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <Link
              key={item.entry_slug}
              href={`/published/daily-market-brief/${item.entry_slug}`}
              className="block rounded-lg border border-border bg-card px-4 py-3 transition-colors hover:border-blue-200 hover:bg-blue-50/40 dark:hover:border-blue-900 dark:hover:bg-blue-950/20"
            >
              <div className="text-sm font-medium text-foreground">{item.title}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {new Date(item.published_at).toLocaleString()}
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
