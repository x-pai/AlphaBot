'use client';

import { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import AsyncAIAnalysis from '@/components/AsyncAIAnalysis';
import AIAnalysis from '@/components/AIAnalysis';

export default function AsyncAIDemo() {
  const [symbol, setSymbol] = useState('AAPL');
  const [inputSymbol, setInputSymbol] = useState('AAPL');

  const handleSearch = () => {
    setSymbol(inputSymbol.toUpperCase());
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">异步AI分析演示</h1>
      
      <div className="mb-8">
        <Card>
          <CardHeader>
            <CardTitle>输入股票代码</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-end gap-4">
              <div className="flex-1">
                <Label htmlFor="symbol-input" className="mb-2 block">股票代码</Label>
                <Input
                  id="symbol-input"
                  value={inputSymbol}
                  onChange={(e) => setInputSymbol(e.target.value)}
                  placeholder="例如：AAPL, MSFT, GOOGL"
                />
              </div>
              <Button onClick={handleSearch}>搜索</Button>
            </div>
          </CardContent>
        </Card>
      </div>
      
      {symbol && (
        <div className="grid md:grid-cols-1 gap-8">
          <div>
            <AIAnalysis symbol={symbol} />
          </div>
        </div>
      )}
      
      <div className="mt-8 text-center text-sm text-gray-500">
        <p>本示例展示了如何使用异步AI分析功能。使用右上角的开关可以切换同步/异步模式。</p>
        <p>异步模式下，分析任务会在后台进行，不会阻塞用户界面。</p>
      </div>
    </div>
  );
} 