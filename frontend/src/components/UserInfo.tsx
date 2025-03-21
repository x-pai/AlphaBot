'use client';

import { useAuth } from '@/lib/contexts/AuthContext';

export default function UserInfo() {
  const { user, logout } = useAuth();

  if (!user) {
    return null;
  }

  return (
    <div className="bg-white shadow rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">用户信息</h3>
        <button
          onClick={logout}
          className="text-sm text-red-600 hover:text-red-800"
        >
          退出登录
        </button>
      </div>
      <div className="space-y-3">
        <div>
          <p className="text-sm text-gray-500">用户名</p>
          <p className="text-base font-medium">{user.username}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500">积分</p>
          <p className="text-base font-medium">{user.points}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500">今日使用次数</p>
          <p className="text-base font-medium">
            {user.daily_usage_count} / {user.is_unlimited ? '无限制' : user.daily_limit}
          </p>
        </div>
        {!user.is_unlimited && (
          <div className="text-sm text-gray-600">
            <p>达到1000积分后可无限制使用</p>
            <div className="w-full bg-gray-200 rounded-full h-2.5 mt-2">
              <div
                className="bg-blue-600 h-2.5 rounded-full"
                style={{ width: `${(user.points / 1000) * 100}%` }}
              ></div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
} 