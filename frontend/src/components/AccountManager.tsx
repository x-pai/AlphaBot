'use client';

import React, { useMemo, useState } from 'react';
import { useAccounts } from '@/lib/contexts/AccountContext';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { ChevronDown, ChevronUp, PlusCircle, RefreshCw, Trash2, Wallet } from 'lucide-react';

type Provider = 'ths' | 'qmt';

const THS_DEFAULT_BASE_URL = 'http://trade.10jqka.com.cn:8088';
const THS_DEFAULT_YYBID = '997376';
const QMT_DEFAULT_ENDPOINT = 'http://127.0.0.1:9101';

export default function AccountManager() {
  const { accounts, selectedAccount, isLoading, error, reloadAccounts, createAccount, deleteAccount, selectAccount } = useAccounts();
  const [provider, setProvider] = useState<Provider>('ths');
  const [name, setName] = useState('My THS');
  const [isDefault, setIsDefault] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [thsCapitalAccount, setThsCapitalAccount] = useState('');
  const [thsUsername, setThsUsername] = useState('');
  const [thsBaseUrl, setThsBaseUrl] = useState(THS_DEFAULT_BASE_URL);
  const [thsYybid, setThsYybid] = useState(THS_DEFAULT_YYBID);
  const [thsShAccount, setThsShAccount] = useState('');
  const [thsSzAccount, setThsSzAccount] = useState('');
  const [thsShMarketCode, setThsShMarketCode] = useState('2');
  const [thsSzMarketCode, setThsSzMarketCode] = useState('1');

  const [qmtEndpoint, setQmtEndpoint] = useState(QMT_DEFAULT_ENDPOINT);
  const [qmtAccountId, setQmtAccountId] = useState('');
  const [qmtApiKey, setQmtApiKey] = useState('');

  const providerHint = useMemo(() => (
    provider === 'ths'
      ? '填写同花顺账户参数，前端会自动组装成后端配置。'
      : '填写 QMT connector 地址和账户标识，后续可继续扩展。'
  ), [provider]);

  const resetProviderFields = (next: Provider) => {
    setName(next === 'ths' ? 'My THS' : 'My QMT');
    setSubmitError(null);
    setMessage(null);
  };

  const buildConfig = () => {
    if (provider === 'ths') {
      const shareholderAccounts = Object.fromEntries(
        Object.entries({
          sh: thsShAccount.trim(),
          sz: thsSzAccount.trim(),
        }).filter(([, value]) => Boolean(value))
      );
      const marketCodes = Object.fromEntries(
        Object.entries({
          sh: thsShMarketCode.trim(),
          sz: thsSzMarketCode.trim(),
        }).filter(([, value]) => Boolean(value))
      );

      return {
        capital_account: thsCapitalAccount.trim(),
        username: thsUsername.trim(),
        base_url: thsBaseUrl.trim() || THS_DEFAULT_BASE_URL,
        department_id: thsYybid.trim() || THS_DEFAULT_YYBID,
        shareholder_accounts: shareholderAccounts,
        market_codes: marketCodes,
      };
    }

    return {
      endpoint: qmtEndpoint.trim() || QMT_DEFAULT_ENDPOINT,
      account_id: qmtAccountId.trim(),
      ...(qmtApiKey.trim() ? { api_key: qmtApiKey.trim() } : {}),
    };
  };

  const validate = () => {
    if (provider === 'ths') {
      if (!thsCapitalAccount.trim()) return '请输入 THS 资金账号';
      return null;
    }

    if (!qmtAccountId.trim()) return '请输入 QMT 账户标识';
    return null;
  };

  const handleSubmit = async () => {
    const validationError = validate();
    if (validationError) {
      setSubmitError(validationError);
      return;
    }

    setSubmitting(true);
    setMessage(null);
    setSubmitError(null);

    const result = await createAccount({
      provider,
      name: name.trim() || provider.toUpperCase(),
      is_default: isDefault,
      config_json: buildConfig(),
      currency: 'CNY',
    });

    if (result.success) {
      setMessage('账户已创建并刷新列表');
    } else {
      setSubmitError(result.error || '创建账户失败');
    }
    setSubmitting(false);
  };

  const handleDelete = async (accountId: number, accountName: string) => {
    if (!window.confirm(`确定删除账户“${accountName}”吗？删除后它将不再出现在可切换列表中。`)) {
      return;
    }

    setDeletingId(accountId);
    setMessage(null);
    setSubmitError(null);
    const result = await deleteAccount(accountId);
    if (result.success) {
      setMessage('账户已删除');
    } else {
      setSubmitError(result.error || '删除账户失败');
    }
    setDeletingId(null);
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">账户管理</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              管理当前用户的 THS / QMT 外部账户连接，并设置默认账户。
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={reloadAccounts} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
        </div>

        {(error || submitError) && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
            {submitError || error}
          </div>
        )}
        {message && (
          <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300">
            {message}
          </div>
        )}

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div className="space-y-4 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
            <div className="space-y-2">
              <Label htmlFor="account-provider">账户类型</Label>
              <select
                id="account-provider"
                value={provider}
                onChange={(e) => {
                  const next = e.target.value as Provider;
                  setProvider(next);
                  resetProviderFields(next);
                }}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="ths">THS</option>
                <option value="qmt">QMT</option>
              </select>
            </div>

            <Input label="账户名称" value={name} onChange={(e) => setName(e.target.value)} placeholder="例如 My THS" />

            <div className="flex items-center gap-2">
              <input
                id="is-default-account"
                type="checkbox"
                checked={isDefault}
                onChange={(e) => setIsDefault(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300"
              />
              <Label htmlFor="is-default-account">设为默认账户</Label>
            </div>

            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/50">
              <div className="mb-3 text-sm font-medium text-slate-900 dark:text-white">
                {provider === 'ths' ? 'THS 连接参数' : 'QMT 连接参数'}
              </div>
              <p className="mb-4 text-xs text-slate-500 dark:text-slate-400">{providerHint}</p>

              {provider === 'ths' ? (
                <div className="grid gap-3">
                  <Input label="资金账号" value={thsCapitalAccount} onChange={(e) => setThsCapitalAccount(e.target.value)} placeholder="例如 1234567890" />
                  <Input label="用户名" value={thsUsername} onChange={(e) => setThsUsername(e.target.value)} placeholder="例如 skill_1776408129180" />
                  <Input label="上海股东账号" value={thsShAccount} onChange={(e) => setThsShAccount(e.target.value)} placeholder="例如 A123456789" />
                  <Input label="深圳股东账号" value={thsSzAccount} onChange={(e) => setThsSzAccount(e.target.value)} placeholder="例如 0151234567" />
                  <button
                    type="button"
                    onClick={() => setShowAdvanced((value) => !value)}
                    className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-600 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                  >
                    <span>高级设置</span>
                    {showAdvanced ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </button>
                  {showAdvanced && (
                    <div className="grid gap-3 rounded-md border border-dashed border-slate-200 p-3 dark:border-slate-700">
                      <Input label="交易接口地址" value={thsBaseUrl} onChange={(e) => setThsBaseUrl(e.target.value)} placeholder={THS_DEFAULT_BASE_URL} />
                      <Input label="营业部编号" value={thsYybid} onChange={(e) => setThsYybid(e.target.value)} placeholder={THS_DEFAULT_YYBID} />
                      <div className="grid gap-3 sm:grid-cols-2">
                        <Input label="上海市场代码" value={thsShMarketCode} onChange={(e) => setThsShMarketCode(e.target.value)} placeholder="留空则传 {}" />
                        <Input label="深圳市场代码" value={thsSzMarketCode} onChange={(e) => setThsSzMarketCode(e.target.value)} placeholder="留空则传 {}" />
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="grid gap-3">
                  <Input label="Connector 地址" value={qmtEndpoint} onChange={(e) => setQmtEndpoint(e.target.value)} placeholder={QMT_DEFAULT_ENDPOINT} />
                  <Input label="账户标识" value={qmtAccountId} onChange={(e) => setQmtAccountId(e.target.value)} placeholder="例如 demo001" />
                  <Input label="API Key" value={qmtApiKey} onChange={(e) => setQmtApiKey(e.target.value)} placeholder="可选" />
                </div>
              )}
            </div>

            <Button onClick={handleSubmit} isLoading={submitting} className="w-full">
              <PlusCircle className="mr-2 h-4 w-4" />
              新增账户
            </Button>
          </div>

          <div className="space-y-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
            <div className="text-sm font-medium text-slate-900 dark:text-white">已接入账户</div>
            {accounts.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
                还没有可用账户，先新增一个 THS 或 QMT 账户。
              </div>
            ) : (
              accounts.map((account) => {
                const active = selectedAccount?.id === account.id;
                return (
                  <button
                    key={account.id}
                    onClick={() => selectAccount(account)}
                    className={`w-full rounded-xl border px-4 py-4 text-left transition-colors ${
                      active
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30'
                        : 'border-slate-200 hover:border-slate-300 dark:border-slate-700 dark:hover:border-slate-600'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <div className="rounded-lg bg-slate-100 p-2 dark:bg-slate-800">
                          <Wallet className="h-4 w-4" />
                        </div>
                        <div>
                          <div className="font-medium text-slate-900 dark:text-white">{account.name}</div>
                          <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                            {account.provider}
                          </div>
                        </div>
                      </div>
                      <div className="text-right text-xs text-slate-500 dark:text-slate-400">
                        {account.is_default ? <div>默认账户</div> : <div>已接入</div>}
                        <div>{account.currency || 'CNY'}</div>
                      </div>
                    </div>
                    {typeof account.cash_balance === 'number' && (
                      <div className="mt-3 text-sm text-slate-600 dark:text-slate-300">
                        可用资金: {account.cash_balance.toLocaleString()}
                      </div>
                    )}
                    <div className="mt-3 flex justify-end">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={deletingId === account.id}
                        onClick={(event) => {
                          event.stopPropagation();
                          void handleDelete(account.id, account.name);
                        }}
                        className="text-red-600 hover:text-red-700"
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        {deletingId === account.id ? '删除中...' : '删除'}
                      </Button>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
