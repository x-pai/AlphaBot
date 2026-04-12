'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@/lib/contexts/AuthContext';
import { listExternalMcpServers, refreshExternalMcpServers } from '@/lib/api';
import { ExternalMcpServerInfo } from '@/types/user';
import { Button } from './ui/button';
import { RefreshCw, PlugZap } from 'lucide-react';

export default function ExternalMcpOverview() {
  const { user } = useAuth();
  const [servers, setServers] = useState<ExternalMcpServerInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadServers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listExternalMcpServers();
      if (!response.success || !response.data) {
        throw new Error(response.error || '获取外部 MCP 服务失败');
      }
      setServers(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取外部 MCP 服务失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRefresh = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const response = await refreshExternalMcpServers();
      if (!response.success || !response.data) {
        throw new Error(response.error || '刷新外部 MCP 服务失败');
      }
      setServers(response.data.servers);
      setMessage('外部 MCP 工具已刷新');
    } catch (err) {
      setError(err instanceof Error ? err.message : '刷新外部 MCP 服务失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.is_admin) {
      loadServers();
    }
  }, [loadServers, user?.is_admin]);

  if (!user?.is_admin) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">只有管理员可以查看外部 MCP 服务</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <PlugZap className="h-5 w-5 text-slate-500" />
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">外部 MCP 服务</h2>
          </div>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            展示当前通过配置接入的外部 MCP 服务，以及 AlphaBot 已发现的工具。
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          刷新发现
        </Button>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
          {error}
        </div>
      )}
      {message && (
        <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300">
          {message}
        </div>
      )}

      <div className="mt-6 space-y-4">
        {servers.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
            当前没有配置外部 MCP 服务
          </div>
        ) : (
          servers.map((server) => (
            <div key={server.id} className="rounded-xl border border-slate-200 p-5 dark:border-slate-700">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-lg font-semibold text-slate-900 dark:text-white">{server.id}</div>
                  <div className="mt-1 break-all text-sm text-slate-500 dark:text-slate-400">{server.base_url}</div>
                </div>
                <div className="text-sm text-slate-600 dark:text-slate-300">
                  {server.enabled ? '已启用' : '已禁用'} · {server.tool_count} 个工具
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2 text-xs">
                {(server.header_names.length > 0 ? server.header_names : ['无鉴权 Header']).map((headerName) => (
                  <span key={headerName} className="rounded-full bg-slate-100 px-3 py-1 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                    {headerName}
                  </span>
                ))}
                {server.timeout_seconds ? (
                  <span className="rounded-full bg-blue-50 px-3 py-1 text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
                    timeout {server.timeout_seconds}s
                  </span>
                ) : null}
              </div>

              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      <th className="px-3 py-2">工具名</th>
                      <th className="px-3 py-2">暴露名</th>
                      <th className="px-3 py-2">接口描述</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {server.tools.length === 0 ? (
                      <tr>
                        <td colSpan={3} className="px-3 py-4 text-sm text-slate-500 dark:text-slate-400">
                          暂未发现工具
                        </td>
                      </tr>
                    ) : (
                      server.tools.map((tool) => (
                        <tr key={tool.full_name} className="text-sm text-slate-700 dark:text-slate-200">
                          <td className="px-3 py-3 font-medium">{tool.full_name}</td>
                          <td className="px-3 py-3 font-mono">{tool.llm_name}</td>
                          <td className="px-3 py-3 text-slate-600 dark:text-slate-300">
                            {tool.description || '暂无描述'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
