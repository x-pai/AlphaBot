'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/lib/contexts/AuthContext';
import {
  createMcpToken,
  getMcpStatus,
  listAdminMcpTokens,
  listMcpTokens,
  revokeAdminMcpToken,
  revokeMcpToken,
} from '@/lib/api';
import { McpStatus, McpTokenCreatePayload, McpTokenInfo } from '@/types/user';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { RefreshCw, KeyRound, Trash2, Shield, Copy } from 'lucide-react';

const defaultStatus: McpStatus = {
  can_use_mcp: false,
  mcp_usage_available: false,
  points: 0,
  mcp_daily_usage_count: 0,
  mcp_daily_limit: 50,
};

function formatDateTime(value?: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleString();
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export default function McpTokenManager() {
  const { user, updateUser } = useAuth();
  const [status, setStatus] = useState<McpStatus>(defaultStatus);
  const [tokens, setTokens] = useState<McpTokenInfo[]>([]);
  const [adminTokens, setAdminTokens] = useState<McpTokenInfo[]>([]);
  const [name, setName] = useState('Cursor Desktop');
  const [expiresAt, setExpiresAt] = useState('');
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createdToken, setCreatedToken] = useState<McpTokenCreatePayload | null>(null);

  const pointsGap = useMemo(() => Math.max(0, 200 - (user?.points || 0)), [user?.points]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statusResp, tokenResp] = await Promise.all([
        getMcpStatus(),
        listMcpTokens(),
      ]);

      if (!statusResp.success || !statusResp.data) {
        throw new Error(statusResp.error || '加载 MCP 状态失败');
      }
      if (!tokenResp.success || !tokenResp.data) {
        throw new Error(tokenResp.error || '加载 MCP Token 失败');
      }

      setStatus(statusResp.data);
      setTokens(tokenResp.data);

      if (user?.is_admin) {
        const adminResp = await listAdminMcpTokens();
        if (!adminResp.success || !adminResp.data) {
          throw new Error(adminResp.error || '加载全量 MCP Token 失败');
        }
        setAdminTokens(adminResp.data);
      } else {
        setAdminTokens([]);
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, '加载 MCP 信息失败'));
    } finally {
      setLoading(false);
    }
  }, [user?.is_admin]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    setMessage(null);
    setCreatedToken(null);
    try {
      const payload = {
        name,
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
      };
      const response = await createMcpToken(payload);
      if (!response.success || !response.data) {
        throw new Error(response.error || '创建 MCP Token 失败');
      }
      setCreatedToken(response.data);
      setMessage('MCP Token 已创建。明文只展示这一次，请立即保存。');
      await Promise.all([loadData(), updateUser()]);
    } catch (err: unknown) {
      setError(getErrorMessage(err, '创建 MCP Token 失败'));
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (tokenId: number, admin = false) => {
    setError(null);
    setMessage(null);
    try {
      const response = admin ? await revokeAdminMcpToken(tokenId) : await revokeMcpToken(tokenId);
      if (!response.success) {
        throw new Error(response.error || '撤销 MCP Token 失败');
      }
      setMessage('MCP Token 已撤销');
      await Promise.all([loadData(), updateUser()]);
    } catch (err: unknown) {
      setError(getErrorMessage(err, '撤销 MCP Token 失败'));
    }
  };

  const handleCopy = async (token: string) => {
    try {
      await navigator.clipboard.writeText(token);
      setMessage('Token 已复制到剪贴板');
    } catch {
      setError('复制失败，请手动复制');
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="text-sm text-slate-500 dark:text-slate-400">MCP 使用资格</div>
          <div className="mt-3 text-2xl font-semibold text-slate-900 dark:text-white">
            {status.can_use_mcp ? '已开启' : '未达到门槛'}
          </div>
          <div className="mt-2 text-sm text-slate-600 dark:text-slate-300">
            {status.can_use_mcp ? '当前账号可以创建并使用 MCP Token' : `还需要 ${pointsGap} 积分才能开启 MCP`}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="text-sm text-slate-500 dark:text-slate-400">今日 MCP 调用</div>
          <div className="mt-3 text-2xl font-semibold text-slate-900 dark:text-white">
            {status.mcp_daily_usage_count} / {user?.is_unlimited ? '无限制' : status.mcp_daily_limit}
          </div>
          <div className="mt-2 text-sm text-slate-600 dark:text-slate-300">
            MCP 工具调用单独计数，默认每日 50 次。
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="text-sm text-slate-500 dark:text-slate-400">接入地址</div>
          <div className="mt-3 break-all text-sm font-medium text-slate-900 dark:text-white">
            /mcp
          </div>
          <div className="mt-2 text-sm text-slate-600 dark:text-slate-300">
            使用 Bearer MCP Token 连接，和主 API 共用同一账号数据。
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">个人 MCP Token</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              为 Cursor、Claude Desktop 等客户端创建独立连接凭证。
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={loadData} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
        </div>

        {error && <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">{error}</div>}
        {message && <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300">{message}</div>}

        <div className="mt-6 grid gap-4 md:grid-cols-[2fr_2fr_auto]">
          <Input value={name} onChange={(e) => setName(e.target.value)} label="Token 名称" placeholder="例如 Cursor Desktop" />
          <Input value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} label="过期时间" type="datetime-local" />
          <div className="flex items-end">
            <Button onClick={handleCreate} isLoading={creating} disabled={!status.can_use_mcp || !name.trim()} className="w-full md:w-auto">
              <KeyRound className="mr-2 h-4 w-4" />
              创建 Token
            </Button>
          </div>
        </div>

        {createdToken && (
          <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-amber-900 dark:text-amber-200">新 Token 明文</div>
                <div className="mt-2 break-all rounded-lg bg-white/80 px-3 py-2 font-mono text-sm text-slate-900 dark:bg-slate-900 dark:text-slate-100">
                  {createdToken.token}
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={() => handleCopy(createdToken.token)}>
                <Copy className="mr-2 h-4 w-4" />复制
              </Button>
            </div>
          </div>
        )}

        <div className="mt-6 overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">
                <th className="px-3 py-3">名称</th>
                <th className="px-3 py-3">前缀</th>
                <th className="px-3 py-3">状态</th>
                <th className="px-3 py-3">最近使用</th>
                <th className="px-3 py-3">过期时间</th>
                <th className="px-3 py-3">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {tokens.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-6 text-center text-sm text-slate-500 dark:text-slate-400">
                    暂无 MCP Token
                  </td>
                </tr>
              ) : (
                tokens.map((token) => (
                  <tr key={token.id} className="text-sm text-slate-700 dark:text-slate-200">
                    <td className="px-3 py-4 font-medium">{token.name}</td>
                    <td className="px-3 py-4 font-mono">{token.token_prefix}</td>
                    <td className="px-3 py-4">{token.is_active ? '有效' : '已撤销'}</td>
                    <td className="px-3 py-4">{formatDateTime(token.last_used_at)}</td>
                    <td className="px-3 py-4">{formatDateTime(token.expires_at)}</td>
                    <td className="px-3 py-4">
                      <Button variant="ghost" size="sm" onClick={() => handleRevoke(token.id)} disabled={!token.is_active}>
                        <Trash2 className="mr-2 h-4 w-4" />撤销
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {user?.is_admin && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <Shield className="h-5 w-5 text-slate-500" />
            <div>
              <h2 className="text-xl font-semibold text-slate-900 dark:text-white">管理员视图</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">查看并撤销所有用户的 MCP Token。</p>
            </div>
          </div>

          <div className="mt-6 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  <th className="px-3 py-3">用户</th>
                  <th className="px-3 py-3">名称</th>
                  <th className="px-3 py-3">前缀</th>
                  <th className="px-3 py-3">状态</th>
                  <th className="px-3 py-3">最近使用 IP</th>
                  <th className="px-3 py-3">创建时间</th>
                  <th className="px-3 py-3">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {adminTokens.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-3 py-6 text-center text-sm text-slate-500 dark:text-slate-400">
                      暂无全量 Token 记录
                    </td>
                  </tr>
                ) : (
                  adminTokens.map((token) => (
                    <tr key={token.id} className="text-sm text-slate-700 dark:text-slate-200">
                      <td className="px-3 py-4">{token.username || token.user_id || '-'}</td>
                      <td className="px-3 py-4 font-medium">{token.name}</td>
                      <td className="px-3 py-4 font-mono">{token.token_prefix}</td>
                      <td className="px-3 py-4">{token.is_active ? '有效' : '已撤销'}</td>
                      <td className="px-3 py-4">{token.last_used_ip || '-'}</td>
                      <td className="px-3 py-4">{formatDateTime(token.created_at)}</td>
                      <td className="px-3 py-4">
                        <Button variant="ghost" size="sm" onClick={() => handleRevoke(token.id, true)} disabled={!token.is_active}>
                          <Trash2 className="mr-2 h-4 w-4" />撤销
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
