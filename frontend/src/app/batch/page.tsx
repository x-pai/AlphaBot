'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { Button } from '../../components/ui/button';
import BatchAnalysis from '../../components/BatchAnalysis';

export default function BatchPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">批量分析</h1>
        <Link href="/">
          <Button variant="outline" size="sm" className="flex items-center">
            <ArrowLeft className="h-4 w-4 mr-2" />
            返回主页
          </Button>
        </Link>
      </div>
      
      <BatchAnalysis />
    </div>
  );
} 