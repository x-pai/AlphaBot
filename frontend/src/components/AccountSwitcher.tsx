'use client';

import React from 'react';
import { useAccounts } from '@/lib/contexts/AccountContext';

export default function AccountSwitcher() {
  const { accounts, selectedAccount, selectAccount, isLoading } = useAccounts();

  return (
    <div className="px-4 py-2 border-b border-border">
      <div className="text-xs text-muted-foreground">当前账户</div>
      {isLoading ? (
        <div className="mt-2 text-sm text-foreground">加载中...</div>
      ) : accounts.length === 0 ? (
        <div className="mt-2 text-sm text-muted-foreground">后端未配置可用账户</div>
      ) : (
        <select
          value={selectedAccount?.id ?? ''}
          onChange={(e) => {
            const next = accounts.find((item) => item.id === Number(e.target.value)) || null;
            selectAccount(next);
          }}
          className="mt-2 flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
        >
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name} ({account.provider.toUpperCase()})
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
