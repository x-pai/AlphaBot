'use client';

import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/lib/contexts/AuthContext';
import { authService } from '@/lib/services/auth';

interface ChangePasswordDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ChangePasswordDialog({ isOpen, onClose }: ChangePasswordDialogProps) {
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const oldPassword = formData.get('oldPassword') as string;
    const newPassword = formData.get('newPassword') as string;
    const confirmPassword = formData.get('confirmPassword') as string;

    // 验证新密码
    if (newPassword !== confirmPassword) {
      setError('两次输入的新密码不一致');
      setLoading(false);
      return;
    }

    try {
      await authService.changePassword(oldPassword, newPassword);
      setSuccess('密码修改成功');
      // 清空表单
      (event.target as HTMLFormElement).reset();
      // 3秒后关闭对话框
      setTimeout(() => {
        onClose();
        setSuccess('');
      }, 3000);
    } catch (error: any) {
      setError(error.message || '修改密码失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px] gap-6">
        <DialogHeader>
          <DialogTitle>修改密码</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-md bg-red-50 p-3">
              <div className="text-sm text-red-700">{error}</div>
            </div>
          )}

          {success && (
            <div className="rounded-md bg-green-50 p-3">
              <div className="text-sm text-green-700">{success}</div>
            </div>
          )}

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="oldPassword">当前密码</Label>
              <Input
                id="oldPassword"
                name="oldPassword"
                type="password"
                required
                placeholder="请输入当前密码"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="newPassword">新密码</Label>
              <Input
                id="newPassword"
                name="newPassword"
                type="password"
                required
                placeholder="请输入新密码"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword">确认新密码</Label>
              <Input
                id="confirmPassword"
                name="confirmPassword"
                type="password"
                required
                placeholder="请再次输入新密码"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 transition-colors"
          >
            {loading ? '修改中...' : '修改密码'}
          </button>
        </form>
      </DialogContent>
    </Dialog>
  );
} 