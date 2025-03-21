'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from './ui/card';
import { Button } from './ui/button';
import { getSavedStocks, deleteSavedStock } from '../lib/api';
import { SavedStock } from '../types';
import { Bookmark, Trash2, RefreshCw, Clock, AlertCircle, ChevronRight, Info } from 'lucide-react';
import { Skeleton } from './ui/skeleton';
import { Badge } from './ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { authService } from '@/lib/services/auth';

interface SavedStocksProps {
  onSelectStock: (symbol: string) => void;
}

export default function SavedStocks({ onSelectStock }: SavedStocksProps) {
  const [stocks, setStocks] = useState<SavedStock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadSavedStocks();
  }, []);

  const loadSavedStocks = async () => {
    try {
      const response = await authService.getSavedStocks();
      if (response.success && Array.isArray(response.data)) {
        setStocks(response.data);
        setError('');
      } else {
        setError(response.error || '加载收藏股票失败');
      }
    } catch (error: any) {
      setError(error.message || '加载收藏股票失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (symbol: string) => {
    try {
      const response = await authService.deleteSavedStock(symbol);
      if (response.success) {
        setStocks(stocks.filter(stock => stock.symbol !== symbol));
        setError('');
      } else {
        setError(response.error || '删除收藏失败');
      }
    } catch (error: any) {
      setError(error.message || '删除收藏失败');
    }
  };

  // 格式化日期
  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString();
    } catch (err) {
      console.error('格式化日期出错:', err);
      return '未知日期';
    }
  };

  // 处理选择股票
  const handleSelectStock = (symbol: string) => {
    setSelectedSymbol(symbol);
    onSelectStock(symbol);
  };

  // 处理刷新
  const handleRefresh = () => {
    loadSavedStocks();
  };

  if (loading) {
    return (
      <Card className="w-full h-full overflow-hidden transition-all duration-300">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-xl flex items-center">
            <Bookmark className="mr-2 h-5 w-5 text-primary" />
            收藏的股票
          </CardTitle>
          <Button variant="ghost" size="sm" disabled>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center space-x-2">
                <Skeleton className="h-10 w-full" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <div className="bg-white shadow rounded-lg p-4">
        <div className="text-red-600">{error}</div>
      </div>
    );
  }

  return (
    <Card className="w-full h-full overflow-hidden transition-all duration-300">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-xl flex items-center">
          <Bookmark className="mr-2 h-5 w-5 text-primary" />
          收藏的股票
        </CardTitle>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                disabled={loading || refreshing}
              >
                <RefreshCw className={`h-4 w-4 ${loading || refreshing ? 'animate-spin' : ''}`} />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>刷新收藏列表</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="p-3 mb-3 bg-red-500/10 border border-red-500/20 rounded-md flex items-center text-red-500 text-sm">
            <AlertCircle className="h-4 w-4 mr-2 flex-shrink-0" />
            {error}
          </div>
        )}
        
        {stocks.length === 0 ? (
          <div className="py-8 text-center">
            <div className="bg-secondary/50 p-4 rounded-md">
              <Bookmark className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-muted-foreground">暂无收藏的股票</p>
              <p className="text-xs text-muted-foreground mt-2">
                搜索并查看股票详情后，点击&quot;收藏&quot;按钮添加到此列表
              </p>
            </div>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {stocks.map((stock) => (
              <li 
                key={stock.symbol} 
                className={`py-3 px-2 rounded-md transition-colors duration-200 hover:bg-secondary/30 cursor-pointer ${
                  selectedSymbol === stock.symbol ? 'bg-primary/10 border-l-2 border-primary pl-2' : ''
                }`}
                onClick={() => handleSelectStock(stock.symbol)}
              >
                <div className="flex justify-between items-center">
                  <div className="flex-1">
                    <div className="flex items-center">
                      <span className="font-medium">{stock.symbol}</span>
                      <span className="ml-2 text-muted-foreground">
                        {stock.stock.name}
                      </span>
                      {selectedSymbol === stock.symbol && (
                        <Badge variant="success" className="ml-2">已选择</Badge>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1 flex items-center">
                      <Clock className="h-3 w-3 mr-1" />
                      添加于: {formatDate(stock.added_at)}
                    </div>
                    {stock.notes && (
                      <div className="text-sm mt-1 text-muted-foreground bg-secondary/50 p-1 rounded">
                        <Info className="h-3 w-3 inline mr-1" />
                        {stock.notes}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center">
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDelete(stock.symbol);
                            }}
                            className="text-red-500 hover:text-red-700 hover:bg-red-500/10 mr-1"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>从收藏中删除</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
      {stocks.length > 0 && (
        <CardFooter className="border-t pt-3 pb-3">
          <div className="w-full text-center text-xs text-muted-foreground">
            点击股票查看详细信息
          </div>
        </CardFooter>
      )}
    </Card>
  );
}