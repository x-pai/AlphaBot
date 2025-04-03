'use client';

import React, { useEffect } from 'react';
import AgentChat from '@/components/AgentChat';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/contexts/AuthContext';
import { Bot, ArrowRight } from 'lucide-react';
import Link from 'next/link';

export default function AgentPage() {
  const { isAuthenticated } = useAuth();
  const router = useRouter();

  // 处理选择股票
  const handleSelectStock = (symbol: string) => {
    router.push(`/stocks/${symbol}`);
  };

  return (
    <div className="min-h-screen flex flex-col bg-white dark:bg-gray-900">
      {!isAuthenticated ? (
        <div className="flex flex-col items-center justify-center h-[85vh] px-4">
          <div className="flex flex-col items-center max-w-md text-center">
            <div className="bg-blue-600 p-3 rounded-full mb-6">
              <Bot className="h-10 w-10 text-white" />
            </div>
            <h1 className="text-3xl font-semibold mb-4">
              AlphaBot 智能股票分析助手
            </h1>
            <p className="text-gray-500 dark:text-gray-400 mb-8">
              登录后使用AI驱动的智能助手，获取专业的股票分析和投资建议
            </p>
            
            <Link 
              href="/login" 
              className="inline-flex h-10 items-center justify-center rounded-md bg-blue-600 hover:bg-blue-700 px-6 text-sm font-medium text-white transition-colors focus-visible:outline-none"
            >
              登录继续使用
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>

            <div className="text-xs text-gray-400 dark:text-gray-500 mt-12">
              结果仅供参考，不构成投资建议
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 relative h-full">
          <AgentChat onSelectStock={handleSelectStock} />
        </div>
      )}
    </div>
  );
} 