'use client';

import React, { useEffect, useState } from 'react';
import ChannelManager from '@/components/ChannelManager';
import IndexedDBCacheManager from '../../components/IndexedDBCacheManager';
import TaskManager from '../../components/TaskManager';
import InviteCodeManager from '../../components/InviteCodeManager';
import McpTokenManager from '../../components/McpTokenManager';
import ExternalMcpOverview from '../../components/ExternalMcpOverview';
import AccountManager from '../../components/AccountManager';
import SkillManager from '../../components/SkillManager';
import { Button } from '../../components/ui/button';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

type SystemTab = 'cache' | 'tasks' | 'invites' | 'accounts' | 'mcp' | 'external-mcp' | 'skills' | 'channels';

const SystemPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<SystemTab>('cache');

  useEffect(() => {
    const selectLinkedTab = () => {
      if (window.location.hash === '#channels') setActiveTab('channels');
    };
    selectLinkedTab();
    window.addEventListener('hashchange', selectLinkedTab);
    return () => window.removeEventListener('hashchange', selectLinkedTab);
  }, []);

  useEffect(() => {
    document.getElementById(`system-tab-${activeTab}`)?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [activeTab]);

  const tabs: { id: SystemTab; label: string }[] = [
    { id: 'cache', label: '缓存管理' },
    { id: 'tasks', label: '定时任务' },
    { id: 'invites', label: '邀请码管理' },
    { id: 'accounts', label: '账户管理' },
    { id: 'mcp', label: 'MCP 管理' },
    { id: 'external-mcp', label: '外部 MCP' },
    { id: 'skills', label: '技能管理' },
    { id: 'channels', label: '消息渠道' },
  ];

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold dark:text-white">系统管理</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">管理系统服务、消息渠道与个人接收目标。</p>
        </div>
        <Link href="/" className="shrink-0">
          <Button variant="outline" size="sm" className="flex items-center whitespace-nowrap">
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回主页
          </Button>
        </Link>
      </div>

      <div className="mb-6 overflow-x-auto border-b border-gray-200 dark:border-gray-700">
        <nav className="flex min-w-max gap-x-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              id={`system-tab-${tab.id}`}
              aria-current={activeTab === tab.id ? 'page' : undefined}
              onClick={() => { setActiveTab(tab.id); window.history.replaceState(null, '', tab.id === 'channels' ? '#channels' : window.location.pathname); }}
              className={`shrink-0 border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
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
        {activeTab === 'accounts' && <AccountManager />}
        {activeTab === 'mcp' && <McpTokenManager />}
        {activeTab === 'external-mcp' && <ExternalMcpOverview />}
        {activeTab === 'skills' && <SkillManager />}
        {activeTab === 'channels' && <ChannelManager />}
      </div>
    </div>
  );
};

export default SystemPage;
