'use client';

import React, { useState } from 'react';
import IndexedDBCacheManager from '../../components/IndexedDBCacheManager';
import TaskManager from '../../components/TaskManager';
import InviteCodeManager from '../../components/InviteCodeManager';
import McpTokenManager from '../../components/McpTokenManager';
import ExternalMcpOverview from '../../components/ExternalMcpOverview';
import { Button } from '../../components/ui/button';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

type SystemTab = 'cache' | 'tasks' | 'invites' | 'mcp' | 'external-mcp';

const SystemPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<SystemTab>('cache');

  const tabs: { id: SystemTab; label: string }[] = [
    { id: 'cache', label: '缓存管理' },
    { id: 'tasks', label: '定时任务' },
    { id: 'invites', label: '邀请码管理' },
    { id: 'mcp', label: 'MCP 管理' },
    { id: 'external-mcp', label: '外部 MCP' },
  ];

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold dark:text-white">系统管理</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">管理缓存、任务、邀请码以及 MCP 访问凭证。</p>
        </div>
        <Link href="/">
          <Button variant="outline" size="sm" className="flex items-center">
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回主页
          </Button>
        </Link>
      </div>

      <div className="mb-6 border-b border-gray-200 dark:border-gray-700">
        <nav className="-mb-px flex flex-wrap gap-x-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`border-b-2 px-5 py-4 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 dark:text-gray-400 dark:hover:border-gray-600 dark:hover:text-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="dark:text-white">
        {activeTab === 'cache' && <IndexedDBCacheManager />}
        {activeTab === 'tasks' && <TaskManager />}
        {activeTab === 'invites' && <InviteCodeManager />}
        {activeTab === 'mcp' && <McpTokenManager />}
        {activeTab === 'external-mcp' && <ExternalMcpOverview />}
      </div>
    </div>
  );
};

export default SystemPage;
