'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/lib/contexts/AuthContext';

const publicPaths = ['/', '/login', '/register', '/about'];

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // 如果是首页且已登录，重定向到仪表板
    if (pathname === '/' && isAuthenticated) {
      router.push('/');
      return;
    }
    
    // 如果不是公开路径且未登录，重定向到登录页
    if (!isAuthenticated && !publicPaths.includes(pathname)) {
      router.push('/login');
    } else if (isAuthenticated && ['/login', '/register'].includes(pathname)) {
      router.push('/');
    }
  }, [isAuthenticated, pathname, router]);

  // 如果在公共路径上，直接显示内容
  if (publicPaths.includes(pathname)) {
    return <>{children}</>;
  }

  // 如果需要认证但未认证，返回 null（将被重定向）
  if (!isAuthenticated) {
    return null;
  }

  // 已认证，显示内容
  return <>{children}</>;
} 