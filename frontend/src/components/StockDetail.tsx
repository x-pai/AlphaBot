import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { getStockInfo, saveStock, deleteSavedStock } from '../lib/api';
import { StockInfo } from '../types';
import { Bookmark, BookmarkCheck, RefreshCw, TrendingUp, TrendingDown, Clock, Info, AlertCircle } from 'lucide-react';
import { Skeleton } from './ui/skeleton';
import { Badge } from './ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { authService } from '@/lib/services/auth';

interface StockDetailProps {
  symbol: string;
}

export default function StockDetail({ symbol }: StockDetailProps) {
  const [stockInfo, setStockInfo] = useState<StockInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSaved, setIsSaved] = useState(false);
  const [notes, setNotes] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const loadStockInfo = useCallback(async (forceRefresh: boolean = false) => {
    if (!symbol) return;
    
    if (forceRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    
    try {
      const response = await getStockInfo(symbol, forceRefresh);
      if (response.success && response.data) {
        setStockInfo(response.data);
        setLastUpdated(new Date());
      } else {
        setError(response.error || '加载股票信息失败');
        setStockInfo(null);
      }
    } catch (err) {
      console.error('加载股票信息出错:', err);
      setError('加载股票信息时出错');
      setStockInfo(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [symbol]);

  useEffect(() => {
    loadStockInfo();
    const checkIfSaved = async () => {
      try {
        const response = await authService.getSavedStocks();
        if (response.success && Array.isArray(response.data)) {
          setIsSaved(response.data.some(s => s.symbol === symbol));
          const savedStock = response.data.find(s => s.symbol === symbol);
          if (savedStock) {
            setNotes(savedStock.notes || '');
          }
        }
      } catch (err) {
        console.error('检查收藏状态出错:', err);
      }
    };
    checkIfSaved();
  }, [symbol, loadStockInfo]);

  const handleSaveStock = async () => {
    if (!stockInfo) return;
    
    setSavingNotes(true);
    try {
      const response = await authService.saveStock(stockInfo.symbol, notes);
      if (response.success) {
        setIsSaved(true);
        setError(null);
      } else {
        setError(response.error || '保存股票失败');
      }
    } catch (err: any) {
      console.error('保存股票出错:', err);
      setError(err.message || '保存股票时出错');
    } finally {
      setSavingNotes(false);
    }
  };

  // 取消收藏股票
  const handleRemoveStock = async () => {
    if (!stockInfo) return;
    
    setRemoving(true);
    try {
      const response = await authService.deleteSavedStock(stockInfo.symbol);
      if (response.success) {
        setIsSaved(false);
        setNotes('');
        setError(null);
      } else {
        setError(response.error || '取消收藏失败');
      }
    } catch (err: any) {
      console.error('取消收藏出错:', err);
      setError(err.message || '取消收藏时出错');
    } finally {
      setRemoving(false);
    }
  };

  const formatNumber = (num: number | undefined, decimals = 2) => {
    if (num === undefined) return '-';
    return num.toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatMarketCap = (marketCap: number | undefined) => {
    if (marketCap === undefined) return '-';
    
    if (marketCap >= 1000000000000) {
      return `${(marketCap / 1000000000000).toFixed(2)}万亿`;
    } else if (marketCap >= 100000000) {
      return `${(marketCap / 100000000).toFixed(2)}亿`;
    } else if (marketCap >= 10000) {
      return `${(marketCap / 10000).toFixed(2)}万`;
    }
    
    return formatNumber(marketCap, 0);
  };

  // 行业标签数据
  const industryTags = ['科技', '互联网', '软件服务'];

  return (
    <Card className="w-full">
      {loading && (
        <CardContent className="p-4">
          <div className="flex justify-between">
            <Skeleton className="h-7 w-28" />
            <Skeleton className="h-7 w-20" />
          </div>
          <div className="grid grid-cols-4 gap-3 mt-3">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        </CardContent>
      )}
      
      {error && (
        <CardContent className="p-4 text-center">
          <AlertCircle className="h-10 w-10 text-red-500 mx-auto mb-3" />
          <div className="text-red-500 font-medium mb-2">{error}</div>
          <Button 
            onClick={() => loadStockInfo(true)} 
            variant="outline"
            size="sm"
            className="mx-auto"
          >
            <RefreshCw className="h-4 w-4 mr-1" />
            重试
          </Button>
        </CardContent>
      )}
      
      {!loading && !error && stockInfo && (
        <CardContent className="p-4">
          <div className="flex justify-between items-start mb-4 pb-3 border-b border-border">
            <div>
              <div className="flex items-center">
                <span className="text-lg font-semibold">{stockInfo.symbol}</span>
                {stockInfo.marketStatus && (
                  <Badge variant={stockInfo.marketStatus === 'open' ? 'success' : 'secondary'} className="ml-2 text-xs">
                    {stockInfo.marketStatus === 'open' ? '交易中' : '已收盘'}
                  </Badge>
                )}
              </div>
              <div className="text-sm mt-1 text-foreground">{stockInfo.name}</div>
              <div className="flex flex-wrap gap-1 mt-1">
                {industryTags.map((tag, index) => (
                  <Badge key={index} variant="outline" className="text-xs bg-primary/10 text-primary border-primary/20">
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
            
            <div className="text-right">
              <div className="text-xl font-bold">
                {stockInfo.price !== undefined ? formatNumber(stockInfo.price) : '-'}
              </div>
              
              {stockInfo.change !== undefined && stockInfo.changePercent !== undefined && (
                <div
                  className={`text-sm ${
                    stockInfo.change > 0
                      ? 'text-green-500'
                      : stockInfo.change < 0
                      ? 'text-red-500'
                      : 'text-muted-foreground'
                  }`}
                >
                  {stockInfo.change > 0 ? (
                    <TrendingUp className="h-3 w-3 inline mr-1" />
                  ) : stockInfo.change < 0 ? (
                    <TrendingDown className="h-3 w-3 inline mr-1" />
                  ) : null}
                  {stockInfo.change > 0 ? '+' : ''}
                  {formatNumber(stockInfo.change)} ({stockInfo.changePercent > 0 ? '+' : ''}
                  {formatNumber(stockInfo.changePercent)}%)
                </div>
              )}
              
              <div className="flex items-center justify-end mt-1 text-xs text-muted-foreground">
                {lastUpdated && (
                  <span className="mr-2">
                    <Clock className="h-3 w-3 inline mr-1" />
                    {lastUpdated.toLocaleTimeString()}
                  </span>
                )}
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => loadStockInfo(true)}
                  disabled={refreshing}
                  className="h-6 px-1"
                >
                  <RefreshCw className={`h-3 w-3 ${refreshing ? 'animate-spin' : ''}`} />
                </Button>
              </div>
            </div>
          </div>
          
          <TooltipProvider>
            <div className="grid grid-cols-4 gap-3 mb-4">
              <div className="bg-secondary/50 rounded-md p-3">
                <div className="text-xs text-muted-foreground">市值</div>
                <div className="font-medium text-sm mt-1">
                  {formatMarketCap(stockInfo.marketCap)}
                </div>
              </div>
              
              <div className="bg-secondary/50 rounded-md p-3">
                <div className="text-xs text-muted-foreground">成交量</div>
                <div className="font-medium text-sm mt-1">
                  {stockInfo.volume ? formatNumber(stockInfo.volume, 0) : '-'}
                </div>
              </div>
              
              {stockInfo.pe && (
                <div className="bg-secondary/50 rounded-md p-3">
                  <div className="text-xs text-muted-foreground">市盈率</div>
                  <div className="font-medium text-sm mt-1">
                    {formatNumber(stockInfo.pe)}
                  </div>
                </div>
              )}
              
              {stockInfo.dividend && (
                <div className="bg-secondary/50 rounded-md p-3">
                  <div className="text-xs text-muted-foreground">股息率</div>
                  <div className="font-medium text-sm mt-1">
                    {formatNumber(stockInfo.dividend)}%
                  </div>
                </div>
              )}
            </div>
          </TooltipProvider>
          
          <div className="flex items-center gap-2">
            <Input
              placeholder="添加笔记（可选）"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={isSaved}
              className="flex-1 h-9 text-sm"
              id="stock-notes"
              name="stock-notes"
            />
            {isSaved ? (
              <Button
                onClick={handleRemoveStock}
                className="h-9 min-w-[80px] px-2 bg-red-500 hover:bg-red-600 text-white"
                disabled={removing}
                size="sm"
              >
                {!removing && <BookmarkCheck className="h-3 w-3 mr-1" />}
                <span className="text-xs whitespace-nowrap">{removing ? '取消中...' : '取消收藏'}</span>
              </Button>
            ) : (
              <Button
                onClick={handleSaveStock}
                className="h-9 min-w-[80px] px-2"
                disabled={savingNotes}
                size="sm"
              >
                {!savingNotes && <Bookmark className="h-3 w-3 mr-1" />}
                <span className="text-xs whitespace-nowrap">{savingNotes ? '保存中...' : '收藏'}</span>
              </Button>
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
} 