'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, AuthState } from '@/types/user';
import { authService } from '../services/auth';

interface AuthContextType extends AuthState {
  login: (token: string) => Promise<void>;
  logout: () => void;
  updateUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  isAuthenticated: false,
  user: null,
  token: null,
  login: async () => {},
  logout: () => {},
  updateUser: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    user: null,
    token: null,
  });

  useEffect(() => {
    // 在组件挂载时检查本地存储的token
    const token = localStorage.getItem('auth_token');
    if (token) {
      setState(prev => ({ ...prev, token, isAuthenticated: true }));
      // 获取用户信息
      authService.getUserInfo()
        .then(user => {
          setState(prev => ({ ...prev, user }));
        })
        .catch(() => {
          // 如果获取用户信息失败，清除token
          localStorage.removeItem('auth_token');
          setState({
            isAuthenticated: false,
            user: null,
            token: null,
          });
        });
    }
  }, []);

  const login = async (token: string) => {
    localStorage.setItem('auth_token', token);
    setState(prev => ({ ...prev, token, isAuthenticated: true }));
    
    try {
      const user = await authService.getUserInfo();
      setState(prev => ({ ...prev, user }));
    } catch (error) {
      console.error('Error fetching user info:', error);
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    setState({
      isAuthenticated: false,
      user: null,
      token: null,
    });
  };

  const updateUser = async () => {
    try {
      const user = await authService.getUserInfo();
      setState(prev => ({ ...prev, user }));
    } catch (error) {
      console.error('Error updating user info:', error);
      throw error;
    }
  };

  return (
    <AuthContext.Provider value={{ ...state, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
} 