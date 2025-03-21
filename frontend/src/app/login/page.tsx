'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/contexts/AuthContext';
import LoginDialog from '@/components/LoginDialog';

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated } = useAuth();
  const registered = searchParams.get('registered') === 'true';

  useEffect(() => {
    if (isAuthenticated) {
      router.push('/');
    }
  }, [isAuthenticated, router]);

  const handleClose = () => {
    router.push('/');
  };

  return (
    <LoginDialog
      isOpen={true}
      onClose={handleClose}
    />
  );
} 