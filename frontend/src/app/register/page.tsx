'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import RegisterDialog from '@/components/RegisterDialog';

export default function RegisterPage() {
  const [isOpen, setIsOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    setIsOpen(true);
  }, []);

  const handleClose = () => {
    setIsOpen(false);
    router.push('/');
  };

  return <RegisterDialog isOpen={isOpen} onClose={handleClose} />;
} 