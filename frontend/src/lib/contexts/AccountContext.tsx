'use client';

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { AccountConnection, AccountConnectionCreatePayload } from '@/types/user';
import { createAccountConnection, deleteAccountConnection, listAccounts } from '@/lib/api';
import { useAuth } from '@/lib/contexts/AuthContext';

interface AccountContextType {
  accounts: AccountConnection[];
  selectedAccount: AccountConnection | null;
  isLoading: boolean;
  error: string | null;
  reloadAccounts: () => Promise<void>;
  selectAccount: (account: AccountConnection | null) => void;
  createAccount: (payload: AccountConnectionCreatePayload) => Promise<{ success: boolean; error?: string }>;
  deleteAccount: (accountId: number) => Promise<{ success: boolean; error?: string }>;
}

const AccountContext = createContext<AccountContextType>({
  accounts: [],
  selectedAccount: null,
  isLoading: false,
  error: null,
  reloadAccounts: async () => {},
  selectAccount: () => {},
  createAccount: async () => ({ success: false, error: 'AccountContext 未初始化' }),
  deleteAccount: async () => ({ success: false, error: 'AccountContext 未初始化' }),
});

export const useAccounts = () => useContext(AccountContext);

const STORAGE_KEY = 'selected_account_id';

export function AccountProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [accounts, setAccounts] = useState<AccountConnection[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<AccountConnection | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectAccount = useCallback((account: AccountConnection | null) => {
    setSelectedAccount(account);
    if (typeof window === 'undefined') return;
    if (account) {
      localStorage.setItem(STORAGE_KEY, String(account.id));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const reloadAccounts = useCallback(async () => {
    if (!isAuthenticated) {
      setAccounts([]);
      setSelectedAccount(null);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const response = await listAccounts();
      if (!response.success || !response.data) {
        throw new Error(response.error || '加载账户列表失败');
      }
      const nextAccounts = response.data;
      setAccounts(nextAccounts);

      const savedId = typeof window !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null;
      const savedAccount = nextAccounts.find((item) => String(item.id) === savedId);
      const defaultAccount = nextAccounts.find((item) => item.is_default) || nextAccounts[0] || null;
      selectAccount(savedAccount || defaultAccount || null);
    } catch (err) {
      setAccounts([]);
      setSelectedAccount(null);
      setError(err instanceof Error ? err.message : '加载账户列表失败');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, selectAccount]);

  const createAccount = useCallback(async (payload: AccountConnectionCreatePayload) => {
    const response = await createAccountConnection(payload);
    if (!response.success) {
      return { success: false, error: response.error || '创建账户失败' };
    }
    await reloadAccounts();
    return { success: true };
  }, [reloadAccounts]);

  const deleteAccount = useCallback(async (accountId: number) => {
    const response = await deleteAccountConnection(accountId);
    if (!response.success) {
      return { success: false, error: response.error || '删除账户失败' };
    }
    await reloadAccounts();
    return { success: true };
  }, [reloadAccounts]);

  useEffect(() => {
    void reloadAccounts();
  }, [reloadAccounts]);

  return (
    <AccountContext.Provider
      value={{
        accounts,
        selectedAccount,
        isLoading,
        error,
        reloadAccounts,
        selectAccount,
        createAccount,
        deleteAccount,
      }}
    >
      {children}
    </AccountContext.Provider>
  );
}
