import React, { useState, useEffect, useCallback } from 'react';
import { indexedDBCache, CacheStats } from '../lib/indexedDBCache';

const IndexedDBCacheManager: React.FC = () => {
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [pattern, setPattern] = useState<string>('');
  const [message, setMessage] = useState<string | null>(null);

  // 使用 useCallback 优化函数
  const loadCacheStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const stats = await indexedDBCache.getStats();
      setCacheStats(stats);
    } catch (err) {
      setError('获取缓存统计信息时发生错误');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  // 清空所有缓存
  const handleClearCache = async () => {
    if (!window.confirm('确定要清空所有缓存吗？此操作不可撤销。')) {
      return;
    }
    
    setLoading(true);
    setError(null);
    setMessage(null);
    
    try {
      await indexedDBCache.clear();
      setMessage('缓存已成功清空');
      loadCacheStats(); // 重新加载统计信息
    } catch (err) {
      setError('清空缓存时发生错误');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // 清除匹配模式的缓存
  const handleClearPattern = async () => {
    if (!pattern.trim()) {
      setError('请输入有效的模式');
      return;
    }
    
    setLoading(true);
    setError(null);
    setMessage(null);
    
    try {
      const count = await indexedDBCache.clearPattern(pattern);
      setMessage(`已成功清除匹配 "${pattern}" 的 ${count} 个缓存项`);
      setPattern(''); // 清空输入
      loadCacheStats(); // 重新加载统计信息
    } catch (err) {
      setError('清除缓存模式时发生错误');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // 清理过期缓存
  const handleCleanupCache = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    
    try {
      const count = await indexedDBCache.cleanup();
      setMessage(`已成功清理 ${count} 个过期缓存项`);
      loadCacheStats(); // 重新加载统计信息
    } catch (err) {
      setError('清理过期缓存时发生错误');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // 自动隐藏消息
  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => {
        setMessage(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  // 组件加载时获取缓存统计信息
  useEffect(() => {
    // 确保IndexedDB已初始化
    indexedDBCache.init().then(() => {
      loadCacheStats();
    }).catch(err => {
      setError('初始化缓存服务时发生错误');
      console.error(err);
    });
  }, [loadCacheStats]);

  return (
    <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6 transition-colors duration-200">
      <h2 className="text-xl font-semibold mb-4 dark:text-white">IndexedDB 缓存管理</h2>
      
      {/* 错误提示 */}
      {error && (
        <div className="bg-red-100 dark:bg-red-900/30 border border-red-400 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded mb-4 flex justify-between items-center">
          <span>{error}</span>
          <button 
            onClick={() => setError(null)} 
            className="text-red-700 dark:text-red-400 hover:text-red-900 dark:hover:text-red-300"
            aria-label="关闭错误提示"
          >
            ✕
          </button>
        </div>
      )}
      
      {/* 成功消息 */}
      {message && (
        <div className="bg-green-100 dark:bg-green-900/30 border border-green-400 dark:border-green-800 text-green-700 dark:text-green-400 px-4 py-3 rounded mb-4 flex justify-between items-center">
          <span>{message}</span>
          <button 
            onClick={() => setMessage(null)} 
            className="text-green-700 dark:text-green-400 hover:text-green-900 dark:hover:text-green-300"
            aria-label="关闭成功提示"
          >
            ✕
          </button>
        </div>
      )}
      
      {/* 缓存统计信息 */}
      {loading && !cacheStats ? (
        <div className="flex justify-center my-8">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 dark:border-blue-400"></div>
        </div>
      ) : cacheStats ? (
        <div className="mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded transition-colors duration-200 hover:shadow-md">
              <p className="text-sm text-gray-500 dark:text-gray-400">总缓存项</p>
              <p className="text-2xl font-bold dark:text-white">{cacheStats.totalItems}</p>
            </div>
            <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded transition-colors duration-200 hover:shadow-md">
              <p className="text-sm text-gray-500 dark:text-gray-400">活跃缓存项</p>
              <p className="text-2xl font-bold dark:text-white">{cacheStats.activeItems}</p>
            </div>
            <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded transition-colors duration-200 hover:shadow-md">
              <p className="text-sm text-gray-500 dark:text-gray-400">过期缓存项</p>
              <p className="text-2xl font-bold dark:text-white">{cacheStats.expiredItems}</p>
            </div>
            <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded flex items-center justify-center transition-colors duration-200 hover:shadow-md">
              <button 
                onClick={loadCacheStats}
                className="text-blue-500 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center"
                disabled={loading}
                aria-label="刷新缓存统计"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" />
                </svg>
                {loading ? '刷新中...' : '刷新统计'}
              </button>
            </div>
          </div>
          
          {/* 缓存键列表 */}
          {cacheStats.cacheKeys.length > 0 && (
            <div className="mt-6">
              <h3 className="text-lg font-medium mb-2 dark:text-white">缓存键列表 ({cacheStats.cacheKeys.length})</h3>
              <div className="max-h-60 overflow-y-auto bg-gray-50 dark:bg-gray-700 p-3 rounded border border-gray-200 dark:border-gray-600 transition-colors duration-200">
                {cacheStats.cacheKeys.map((key, index) => (
                  <div key={index} className="text-sm py-1 border-b border-gray-200 dark:border-gray-600 last:border-0 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 px-2 rounded transition-colors duration-150">
                    {key}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <p className="dark:text-white text-center py-4">无法获取缓存统计信息</p>
      )}
      
      {/* 缓存操作 */}
      <div className="space-y-6">
        <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded transition-colors duration-200">
          <h3 className="text-lg font-medium mb-3 dark:text-white">清除特定模式的缓存</h3>
          <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-2">
            <input
              type="text"
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
              placeholder="输入缓存键模式"
              className="flex-1 border dark:border-gray-600 rounded px-3 py-2 dark:bg-gray-800 dark:text-white focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent outline-none transition-all duration-200"
              id="indexeddb-cache-pattern"
              name="indexeddb-cache-pattern"
              aria-label="缓存键模式"
            />
            <button
              onClick={handleClearPattern}
              disabled={loading || !pattern.trim()}
              className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-blue-300 dark:disabled:bg-blue-800 transition-colors duration-200 focus:ring-2 focus:ring-blue-300 focus:ring-offset-2 dark:focus:ring-offset-gray-800"
              aria-label="清除匹配模式的缓存"
            >
              {loading ? '处理中...' : '清除'}
            </button>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
            例如: "get_stock_info" 将清除所有包含该字符串的缓存项
          </p>
        </div>
        
        <div className="flex flex-col sm:flex-row sm:space-x-4 space-y-2 sm:space-y-0">
          <button
            onClick={handleCleanupCache}
            disabled={loading}
            className="bg-yellow-500 text-white px-4 py-2 rounded hover:bg-yellow-600 disabled:bg-yellow-300 dark:disabled:bg-yellow-800 transition-colors duration-200 focus:ring-2 focus:ring-yellow-300 focus:ring-offset-2 dark:focus:ring-offset-gray-800 flex-1 flex justify-center items-center"
            aria-label="清理过期缓存"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1z" clipRule="evenodd" />
              <path fillRule="evenodd" d="M10.293 10.293a1 1 0 011.414 0L14 12.586l2.293-2.293a1 1 0 111.414 1.414L15.414 14l2.293 2.293a1 1 0 01-1.414 1.414L14 15.414l-2.293 2.293a1 1 0 01-1.414-1.414L12.586 14l-2.293-2.293a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
            {loading ? '清理中...' : '清理过期缓存'}
          </button>
          
          <button
            onClick={handleClearCache}
            disabled={loading}
            className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600 disabled:bg-red-300 dark:disabled:bg-red-800 transition-colors duration-200 focus:ring-2 focus:ring-red-300 focus:ring-offset-2 dark:focus:ring-offset-gray-800 flex-1 flex justify-center items-center"
            aria-label="清空所有缓存"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            {loading ? '清空中...' : '清空所有缓存'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default IndexedDBCacheManager; 