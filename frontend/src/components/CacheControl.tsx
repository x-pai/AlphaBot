import React, { useState } from 'react';
import { Button } from './ui/button';
import { clearCache, cleanupCache } from '../lib/api';
import { Trash2, RefreshCw } from 'lucide-react';

export default function CacheControl() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [showMessage, setShowMessage] = useState(false);

  // 清空所有缓存
  const handleClearCache = async () => {
    setLoading(true);
    setMessage(null);
    
    try {
      console.log('Clearing all cache');
      const response = await clearCache();
      if (response.success) {
        setMessage('缓存已成功清空');
        setShowMessage(true);
        // 3秒后自动隐藏消息
        setTimeout(() => {
          setShowMessage(false);
        }, 3000);
      } else {
        setMessage(response.error || '清空缓存失败');
        setShowMessage(true);
      }
    } catch (err) {
      console.error('清空缓存时发生错误:', err);
      setMessage('清空缓存时发生错误');
      setShowMessage(true);
    } finally {
      setLoading(false);
      setShowConfirm(false);
    }
  };

  // 清理过期缓存
  const handleCleanupCache = async () => {
    setLoading(true);
    setMessage(null);
    
    try {
      console.log('Cleaning up expired cache');
      const response = await cleanupCache();
      if (response.success) {
        setMessage(response.data?.message || '过期缓存已成功清理');
        setShowMessage(true);
        // 3秒后自动隐藏消息
        setTimeout(() => {
          setShowMessage(false);
        }, 3000);
      } else {
        setMessage(response.error || '清理过期缓存失败');
        setShowMessage(true);
      }
    } catch (err) {
      console.error('清理过期缓存时发生错误:', err);
      setMessage('清理过期缓存时发生错误');
      setShowMessage(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {showConfirm ? (
        <div className="p-4 border rounded-md bg-red-50 mb-4">
          <p className="mb-3 text-sm">确定要清空所有缓存吗？这将删除所有本地存储的数据。</p>
          <div className="flex space-x-2">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => setShowConfirm(false)}
              disabled={loading}
            >
              取消
            </Button>
            <Button 
              variant="outline" 
              size="sm"
              className="text-red-500 hover:text-red-600 hover:bg-red-50"
              onClick={handleClearCache}
              disabled={loading}
            >
              {loading ? '清空中...' : '确认清空'}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex space-x-2">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={handleCleanupCache}
            disabled={loading}
          >
            {loading ? (
              <div className="flex items-center">
                <div className="animate-spin h-3 w-3 mr-1 border-2 border-current border-t-transparent rounded-full"></div>
                处理中...
              </div>
            ) : (
              <>
                <RefreshCw className="h-4 w-4 mr-1" />
                清理过期缓存
              </>
            )}
          </Button>
          
          <Button 
            variant="outline" 
            size="sm"
            className="text-red-500 hover:text-red-600 hover:bg-red-50"
            onClick={() => setShowConfirm(true)}
            disabled={loading}
          >
            <Trash2 className="h-4 w-4 mr-1" />
            清空所有缓存
          </Button>
        </div>
      )}
      
      {/* 操作结果消息 */}
      {showMessage && message && (
        <div className={`mt-2 text-sm p-2 rounded-md animate-in fade-in slide-in-from-top-5 duration-300 ${
          message.includes('成功') 
            ? 'bg-green-50 text-green-600' 
            : 'bg-red-50 text-red-600'
        }`}>
          {message}
        </div>
      )}
    </div>
  );
} 