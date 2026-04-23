'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { Button } from '../../components/ui/button';
import BatchAnalysis from '../../components/BatchAnalysis';
import { useAuth } from '@/lib/contexts/AuthContext';

export default function BatchPage() {
  const { user } = useAuth();
  if (!user?.is_unlimited) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">达到1000积分后可使用</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">批量分析</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            一次性批量分析工具。输入 6 位纯数字股票代码，单次最多分析 10 个；刷新页面后不会保留本次结果。
          </p>
        </div>
        <Link href="/">
          <Button variant="outline" size="sm" className="flex items-center">
            <ArrowLeft className="h-4 w-4 mr-2" />
            返回主页
          </Button>
        </Link>
      </div>
      
      <BatchAnalysis />
    </div>
  );
} 
