import { LoginForm, RegisterForm, AuthResponse, User, SavedStock } from '@/types/user';
import { ApiResponse } from '@/types';
import * as api from '../api';

export const authService = {
  async login(data: LoginForm): Promise<AuthResponse> {
    try {
      const response = await api.login(data);
      if (!response.success || !response.data) {
        throw new Error(response.error || '登录失败');
      }
      // 保存令牌到 localStorage
      localStorage.setItem('auth_token', response.data.access_token);
      return response.data;
    } catch (error) {
      console.error('Error logging in:', error);
      throw error;
    }
  },

  async register(data: RegisterForm): Promise<void> {
    try {
      const response = await api.register(data);
      if (!response.success || !response.data) {
        throw new Error(response.error || '注册失败');
      }
      // 注册成功，不需要返回数据
    } catch (error) {
      console.error('Error registering:', error);
      throw error;
    }
  },

  async getUserInfo(): Promise<User> {
    try {
      const response = await api.getUserInfo();
      if (!response.success || !response.data) {
        throw new Error(response.error || '获取用户信息失败');
      }
      return response.data;
    } catch (error) {
      console.error('Error fetching user info:', error);
      throw error;
    }
  },

  async checkUsage(): Promise<any> {
    try {
      const response = await api.checkUsage();
      if (!response.success) {
        throw new Error(response.error || '检查使用情况失败');
      }
      return response.data;
    } catch (error) {
      console.error('Error checking usage:', error);
      throw error;
    }
  },

  async getSavedStocks(): Promise<{ success: boolean; data?: SavedStock[]; error?: string }> {
    try {
      const response = await api.getSavedStocks();
      if (!response.success || !response.data) {
        throw new Error(response.error || '获取收藏股票失败');
      }
      return response;
    } catch (error) {
      console.error('Error getting saved stocks:', error);
      throw error;
    }
  },

  async saveStock(symbol: string, notes?: string): Promise<{ success: boolean; data?: SavedStock; error?: string }> {
    try {
      const response = await api.saveStock(symbol, notes);
      if (!response.success) {
        throw new Error(response.error || '收藏股票失败');
      }
      return response;
    } catch (error) {
      console.error('Error saving stock:', error);
      throw error;
    }
  },

  async deleteSavedStock(symbol: string): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await api.deleteSavedStock(symbol);
      if (!response.success) {
        throw new Error(response.error || '取消收藏失败');
      }
      return response;
    } catch (error) {
      console.error('Error deleting saved stock:', error);
      throw error;
    }
  },

  async changePassword(oldPassword: string, newPassword: string): Promise<void> {
    try {
      const response = await api.changePassword(oldPassword, newPassword);
      if (!response.success) {
        throw new Error(response.error || '修改密码失败');
      }
    } catch (error) {
      console.error('Error changing password:', error);
      throw error;
    }
  },

  async logout(): Promise<{ success: boolean; error?: string }> {
    try {
      // 调用后端退出登录接口
      const response = await api.logout();
      
      // 即使后端请求失败，也要清除本地状态
      localStorage.removeItem('auth_token');
      
      // 返回响应结果
      return response;
    } catch (error: any) {
      console.error('Error logging out:', error);
      // 即使发生错误，也要清除本地存储
      localStorage.removeItem('auth_token');
      return {
        success: false,
        error: error.message || '退出登录失败'
      };
    }
  },

  isLoggedIn(): boolean {
    return typeof window !== 'undefined' && !!localStorage.getItem('auth_token');
  }
}; 