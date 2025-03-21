import React, { useState, useEffect, useRef } from 'react';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { searchStocks } from '../lib/api';
import { StockInfo } from '../types';
import { Search } from 'lucide-react';

interface StockSearchProps {
  onSelectStock: (stock: StockInfo) => void;
}

export default function StockSearch({ onSelectStock }: StockSearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<StockInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  // 处理搜索
  const handleSearch = async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    try {
      const response = await searchStocks(query);
      if (response.success && response.data) {
        setResults(response.data);
        setShowResults(true);
      } else {
        setResults([]);
        setShowResults(true);
      }
    } catch (error) {
      console.error('搜索出错:', error);
      setResults([]);
      setShowResults(true);
    } finally {
      setLoading(false);
    }
  };

  // 处理点击外部关闭结果
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setShowResults(false);
      }
    }
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // 处理选择股票
  const handleSelectStock = (stock: StockInfo) => {
    onSelectStock(stock);
    setShowResults(false);
    setQuery('');
  };

  return (
    <div className="relative w-full" ref={searchRef}>
      <div className="flex gap-2">
        <Input
          placeholder="输入股票代码或名称搜索..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1"
          id="stock-search"
          name="stock-search"
        />
        <Button onClick={handleSearch} isLoading={loading} className="min-w-[80px]">
          {!loading && <Search className="h-4 w-4 mr-2" />}
          <span className="whitespace-nowrap">搜索</span>
        </Button>
      </div>
      
      {showResults && results.length > 0 && (
        <div className="absolute z-10 mt-1 w-full bg-card rounded-md border border-border shadow-lg animate-in">
          <ul className="py-1 max-h-60 overflow-auto">
            {results.map((stock) => (
              <li
                key={stock.symbol}
                className="px-4 py-2 hover:bg-muted cursor-pointer"
                onClick={() => handleSelectStock(stock)}
              >
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-medium">{stock.symbol}</span>
                    <span className="ml-2 text-muted-foreground">{stock.name}</span>
                  </div>
                  <div className="flex items-center">
                    {stock.price && (
                      <span className="font-medium">
                        {stock.price.toFixed(2)}
                      </span>
                    )}
                    {stock.changePercent && (
                      <span
                        className={`ml-2 px-1.5 py-0.5 rounded text-xs ${
                          stock.changePercent > 0
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                            : stock.changePercent < 0
                            ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                            : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
                        }`}
                      >
                        {stock.changePercent > 0 ? '+' : ''}
                        {stock.changePercent.toFixed(2)}%
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {stock.exchange} · {stock.currency}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {showResults && query && results.length === 0 && (
        <div className="absolute z-10 mt-1 w-full bg-card rounded-md border border-border shadow-lg p-4 text-center animate-in">
          未找到匹配的股票
        </div>
      )}
    </div>
  );
} 