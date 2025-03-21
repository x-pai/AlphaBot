import React, { useState, useEffect } from 'react';
import { updateStockData, updateAllStocks } from '../lib/api';

const DataUpdater: React.FC = () => {
  const [symbol, setSymbol] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  // 更新特定股票数据
  const handleUpdateStock = async () => {
    if (!symbol.trim()) {
      setError('请输入股票代码');
      return;
    }
    
    setLoading(true);
    setError(null);
    setMessage(null);
    
    try {
      const response = await updateStockData(symbol);
      if (response.success) {
        setMessage(response.data?.message || `已开始更新股票 ${symbol} 的数据`);
        setSymbol(''); // 清空输入
      } else {
        setError(response.error || '更新股票数据失败');
      }
    } catch (err) {
      setError('更新股票数据时发生错误');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // 更新所有股票数据
  const handleUpdateAllStocks = async () => {
    if (!window.confirm('确定要更新所有股票数据吗？这可能需要一些时间。')) {
      return;
    }
    
    setLoading(true);
    setError(null);
    setMessage(null);
    
    try {
      const response = await updateAllStocks();
      if (response.success) {
        setMessage(response.data?.message || '已开始更新所有股票数据');
      } else {
        setError(response.error || '更新所有股票数据失败');
      }
    } catch (err) {
      setError('更新所有股票数据时发生错误');
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

  return (
    <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6 transition-colors duration-200">
      <h2 className="text-xl font-semibold mb-4 dark:text-white">数据更新</h2>
      
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
      
      {/* 更新特定股票 */}
      <div className="mb-8 bg-gray-50 dark:bg-gray-700 p-5 rounded border border-gray-200 dark:border-gray-600 transition-colors duration-200">
        <h3 className="text-lg font-medium mb-3 dark:text-white flex items-center">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 text-blue-500 dark:text-blue-400" viewBox="0 0 20 20" fill="currentColor">
            <path d="M5 4a1 1 0 00-2 0v7.268a2 2 0 000 3.464V16a1 1 0 102 0v-1.268a2 2 0 000-3.464V4zM11 4a1 1 0 10-2 0v1.268a2 2 0 000 3.464V16a1 1 0 102 0V8.732a2 2 0 000-3.464V4zM16 3a1 1 0 011 1v7.268a2 2 0 010 3.464V16a1 1 0 11-2 0v-1.268a2 2 0 010-3.464V4a1 1 0 011-1z" />
          </svg>
          更新特定股票数据
        </h3>
        <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-2">
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="输入股票代码"
            className="flex-1 border dark:border-gray-600 rounded px-3 py-2 dark:bg-gray-800 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all duration-200"
            id="stock-symbol"
            name="stock-symbol"
          />
          <button
            onClick={handleUpdateStock}
            disabled={loading || !symbol.trim()}
            className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-blue-300 dark:disabled:bg-blue-800 transition-colors duration-200 focus:ring-2 focus:ring-blue-300 focus:ring-offset-2 dark:focus:ring-offset-gray-800 flex items-center"
          >
            {loading ? '更新中...' : '更新'}
          </button>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          输入股票代码，例如: AAPL, MSFT, GOOG
        </p>
      </div>
      
      {/* 更新所有股票 */}
      <div>
        <h3 className="text-lg font-medium mb-2">更新所有股票数据</h3>
        <button
          onClick={handleUpdateAllStocks}
          disabled={loading}
          className="bg-indigo-500 text-white px-4 py-2 rounded hover:bg-indigo-600 disabled:bg-indigo-300"
        >
          {loading ? '更新中...' : '更新所有股票'}
        </button>
        <p className="text-sm text-gray-500 mt-1">
          这将清除所有股票数据的缓存，下次访问时将获取最新数据
        </p>
      </div>
    </div>
  );
};

export default DataUpdater; 