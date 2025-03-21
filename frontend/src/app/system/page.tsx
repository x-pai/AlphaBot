'use client';

import React, { useState } from 'react';
import IndexedDBCacheManager from '../../components/IndexedDBCacheManager';
import TaskManager from '../../components/TaskManager';
import DataUpdater from '../../components/DataUpdater';
import { Button } from '../../components/ui/button';
import Link from 'next/link';
import { Home, ArrowLeft } from 'lucide-react';

const SystemPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'cache' | 'tasks' | 'data'>('cache');

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold dark:text-white">系统管理</h1>
        <Link href="/">
          <Button variant="outline" size="sm" className="flex items-center">
            <ArrowLeft className="h-4 w-4 mr-2" />
            返回主页
          </Button>
        </Link>
      </div>
      
      {/* 标签页导航 */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="flex -mb-px">
          <button
            onClick={() => setActiveTab('cache')}
            className={`py-4 px-6 text-center border-b-2 font-medium text-sm ${
              activeTab === 'cache'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
          >
            缓存管理
          </button>
          <button
            onClick={() => setActiveTab('tasks')}
            className={`py-4 px-6 text-center border-b-2 font-medium text-sm ${
              activeTab === 'tasks'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
          >
            定时任务
          </button>
          <button
            onClick={() => setActiveTab('data')}
            className={`py-4 px-6 text-center border-b-2 font-medium text-sm ${
              activeTab === 'data'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
          >
            数据更新
          </button>
        </nav>
      </div>
      
      {/* 标签页内容 */}
      <div className="dark:text-white">
        {activeTab === 'cache' && <IndexedDBCacheManager />}
        {activeTab === 'tasks' && <TaskManager />}
        {activeTab === 'data' && <DataUpdater />}
      </div>
    </div>
  );
};

export default SystemPage; 