import { ApiResponse } from '@/types';
import * as api from '../api';

export interface InviteCode {
  code: string;
  used: boolean;
  used_by?: string;
  used_at?: string;
  created_at: string;
}

export const inviteService = {
  async getInviteCodes(): Promise<InviteCode[]> {
    try {
      const response = await api.get<ApiResponse<InviteCode[]>>('/user/invite-codes');

      if (!response.success) {
        throw new Error(response.error || '获取邀请码列表失败');
      }

      if (!response.data || !Array.isArray(response.data)) {
        console.error('Invalid data format:', response.data);
        throw new Error('返回数据格式错误');
      }

      const formattedCodes = response.data.map(code => {
        return {
          code: code.code,
          used: code.used,
          used_by: code.used_by,
          used_at: code.used_at ? new Date(code.used_at).toISOString() : undefined,
          created_at: new Date(code.created_at).toISOString()
        };
      });

      return formattedCodes;
    } catch (error: any) {
      console.error('Error fetching invite codes:', error);
      if (error.response?.data?.error) {
        throw new Error(error.response.data.error);
      }
      throw error;
    }
  },

  async generateInviteCode(): Promise<string> {
    try {
      const response = await api.post<ApiResponse<string>>('/user/invite-codes');
      console.log('Generate invite code response:', response);

      if (!response.success) {
        throw new Error(response.error || '生成邀请码失败');
      }

      if (!response.data) {
        throw new Error('返回数据格式错误');
      }

      return response.data;
    } catch (error: any) {
      console.error('Error generating invite code:', error);
      if (error.response?.data?.error) {
        throw new Error(error.response.data.error);
      }
      throw error;
    }
  }
}; 