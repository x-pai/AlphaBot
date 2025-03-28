'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/lib/contexts/AuthContext';
import { Button } from './ui/button';
import { RefreshCw, Plus } from 'lucide-react';
import { inviteService, InviteCode } from '@/lib/services/invite';

export default function InviteCodeManager() {
  const [inviteCodes, setInviteCodes] = useState<InviteCode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const { user } = useAuth();

  // 加载邀请码列表
  const loadInviteCodes = async () => {
    setLoading(true);
    setError(null);
    try {
      const codes = await inviteService.getInviteCodes();
      setInviteCodes(codes);
    } catch (err: any) {
      console.error('Error in InviteCodeManager:', err);
      setError(err.message || '加载邀请码失败');
    } finally {
      setLoading(false);
    }
  };

  // 生成新的邀请码
  const handleGenerateCode = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      console.log('Generating new invite code...');
      const code = await inviteService.generateInviteCode();
      console.log('Generated code:', code);
      setMessage('成功生成新的邀请码');
      await loadInviteCodes(); // 重新加载列表
    } catch (err: any) {
      console.error('Error generating invite code:', err);
      setError(err.message || '生成邀请码失败');
    } finally {
      setLoading(false);
    }
  };

  // 初始加载
  useEffect(() => {
    loadInviteCodes();
  }, []);

  if (!user?.is_admin) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">只有管理员可以管理邀请码</p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6 transition-colors duration-200">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold dark:text-white">邀请码管理</h2>
        <div className="flex space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadInviteCodes}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleGenerateCode}
            disabled={loading}
          >
            <Plus className="h-4 w-4 mr-1" />
            生成邀请码
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/30 border border-red-400 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {message && (
        <div className="bg-green-50 dark:bg-green-900/30 border border-green-400 dark:border-green-800 text-green-700 dark:text-green-400 px-4 py-3 rounded mb-4">
          {message}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-700">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                邀请码
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                状态
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                使用者
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                使用时间
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                创建时间
              </th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-4 text-center text-gray-500 dark:text-gray-400">
                  加载中...
                </td>
              </tr>
            ) : inviteCodes.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-4 text-center text-gray-500 dark:text-gray-400">
                  暂无邀请码
                </td>
              </tr>
            ) : (
              inviteCodes.map((code) => (
                <tr key={code.code} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                    {code.code}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      code.used
                        ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                        : 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                    }`}>
                      {code.used ? '已使用' : '未使用'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {code.used_by || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {code.used_at ? new Date(code.used_at).toLocaleString() : '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {new Date(code.created_at).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
} 