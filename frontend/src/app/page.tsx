'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/lib/contexts/AuthContext';
import StockSearch from '../components/StockSearch';
import StockDetail from '../components/StockDetail';
import StockChart from '../components/StockChart';
import AIAnalysis from '../components/AIAnalysis';
import SavedStocks from '../components/SavedStocks';
import CacheControl from '../components/CacheControl';
import { StockInfo } from '../types';
import { ChartLine, Search, Settings, Info, Bot, LogIn, User, LogOut } from 'lucide-react';
import { Button } from '../components/ui/button';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

export default function Home() {
  const router = useRouter();
  const { isAuthenticated, user, logout } = useAuth();
  const [selectedStock, setSelectedStock] = useState<StockInfo | null>(null);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const userButtonRef = useRef<HTMLButtonElement>(null);

  // 处理点击外部关闭菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        userMenuRef.current &&
        !userMenuRef.current.contains(event.target as Node) &&
        userButtonRef.current &&
        !userButtonRef.current.contains(event.target as Node)
      ) {
        setShowUserMenu(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setShowUserMenu(false);
      }
    };

    if (showUserMenu) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [showUserMenu]);

  // 处理退出登录
  const handleLogout = async () => {
    try {
      await logout();
      router.push('/login');
    } catch (error) {
      console.error('退出登录失败:', error);
    }
  };

  // 处理选择股票
  const handleSelectStock = (stock: StockInfo) => {
    setSelectedStock(stock);
    
    const detailsElement = document.getElementById('stock-details-section');
    if (detailsElement) {
      detailsElement.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // 处理从收藏夹选择股票
  const handleSelectFromSaved = (symbol: string) => {
    // 这里简单处理，只设置symbol
    setSelectedStock({
      symbol,
      name: '',
      exchange: '',
      currency: '',
    });
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="container mx-auto px-4 py-4 flex items-center">
          <div className="flex items-center text-2xl font-bold text-primary">
            <ChartLine className="h-6 w-6 mr-2" />
            <span>AlphaBot</span>
          </div>
          <div className="ml-auto flex items-center space-x-4">
            {isAuthenticated ? (
              <>
                <div className="relative">
                  <button
                    ref={userButtonRef}
                    onClick={() => setShowUserMenu(!showUserMenu)}
                    className="flex items-center text-muted-foreground hover:text-foreground"
                  >
                    <User className="h-5 w-5 mr-1" />
                    <span>{user?.username}</span>
                  </button>
                  {showUserMenu && (
                    <div
                      ref={userMenuRef}
                      className="absolute right-0 mt-2 w-48 py-2 bg-background border border-border rounded-md shadow-lg z-50"
                    >
                      <div className="px-4 py-2 border-b border-border">
                        <div className="text-sm font-medium">{user?.username}</div>
                        <div className="text-sm text-muted-foreground">积分: {user?.points}</div>
                        <div className="text-sm text-muted-foreground">
                          今日使用: {user?.daily_usage_count} / {user?.is_unlimited ? '无限制' : user?.daily_limit}
                        </div>
                      </div>
                      <Link
                        href="/system"
                        className="block px-4 py-2 text-sm text-foreground hover:bg-accent"
                        onClick={() => setShowUserMenu(false)}
                      >
                        <Settings className="h-4 w-4 inline mr-2" />
                        系统管理
                      </Link>
                      <button
                        onClick={handleLogout}
                        className="block w-full text-left px-4 py-2 text-sm text-red-500 hover:bg-accent"
                      >
                        <LogOut className="h-4 w-4 inline mr-2" />
                        退出登录
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <Link
                href="/login"
                className="flex items-center text-muted-foreground hover:text-foreground"
              >
                <LogIn className="h-5 w-5 mr-1" />
                <span>登录</span>
              </Link>
            )}
            <a
              href="https://www.jianshu.com/c/38a7568e2b6b"
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground hover:text-foreground"
            >
              简书
            </a>
            <a
              href="https://x-pai.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground hover:text-foreground"
            >
              X-PAI
            </a>
            <a
              href="https://github.com/x-pai/ai-stock-assistant"
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground hover:text-foreground"
            >
              GitHub
            </a>
            <Link
              href="/about"
              className="flex items-center text-muted-foreground hover:text-foreground"
            >
              <Info className="h-5 w-5 mr-1" />
              <span>关于我们</span>
            </Link>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
            <div>
              <h1 className="text-3xl font-bold mb-2">探索股票市场</h1>
              <p className="text-muted-foreground">
                {isAuthenticated ? 
                  '搜索股票，查看实时数据，获取AI分析和建议' :
                  '登录后可获取更多功能，包括AI分析、个性化推荐等'
                }
              </p>
            </div>
            {isAuthenticated && (
              <div>
                <CacheControl />
              </div>
            )}
          </div>
          <StockSearch onSelectStock={handleSelectStock} />
        </div>

        {selectedStock ? (
          <div id="stock-details-section" className="grid grid-cols-1 lg:grid-cols-3 gap-8 scroll-mt-8">
            <div className="lg:col-span-2 space-y-8">              
              <StockDetail symbol={selectedStock.symbol} />
              <StockChart symbol={selectedStock.symbol} />
              {isAuthenticated ? (
                <AIAnalysis symbol={selectedStock.symbol} />
              ) : (
                <div className="border border-border rounded-lg p-6 text-center">
                  <Bot className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium mb-2">AI 智能分析</h3>
                  <p className="text-muted-foreground mb-4">
                    登录后即可获取AI智能分析服务，包括：
                  </p>
                  <ul className="text-sm text-muted-foreground space-y-2 mb-6">
                    <li>• 技术指标分析</li>
                    <li>• 趋势预测</li>
                    <li>• 风险评估</li>
                    <li>• 个性化建议</li>
                  </ul>
                  <Link href="/login">
                    <Button>
                      立即登录
                    </Button>
                  </Link>
                </div>
              )}
            </div>
            <div>
              {isAuthenticated ? (
                <SavedStocks onSelectStock={handleSelectFromSaved} />
              ) : (
                <div className="border border-border rounded-lg p-6">
                  <h3 className="text-lg font-medium mb-2">收藏夹</h3>
                  <p className="text-muted-foreground mb-4">
                    登录后可以收藏关注的股票，随时查看最新动态
                  </p>
                  <Link href="/login">
                    <Button variant="outline" className="w-full">
                      登录以使用
                    </Button>
                  </Link>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 flex items-center justify-center p-16 border border-dashed border-border rounded-lg">
              <div className="text-center">
                <Search className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h2 className="text-xl font-medium mb-2">搜索股票</h2>
                <p className="text-muted-foreground">
                  输入股票代码或名称开始探索
                </p>
              </div>
            </div>
            <div>
              {isAuthenticated ? (
                <SavedStocks onSelectStock={handleSelectFromSaved} />
              ) : (
                <div className="border border-border rounded-lg p-6">
                  <h3 className="text-lg font-medium mb-2">收藏夹</h3>
                  <p className="text-muted-foreground mb-4">
                    登录后可以收藏关注的股票，随时查看最新动态
                  </p>
                  <Link href="/login">
                    <Button variant="outline" className="w-full">
                      登录以使用
                    </Button>
                  </Link>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      <footer className="border-t border-border mt-16">
        <div className="container mx-auto px-4 py-8">
          <div className="text-center text-muted-foreground text-sm">
            <p>AlphaBot &copy; {new Date().getFullYear()}</p>
            <p className="mt-2">
              免责声明：本应用提供的数据和分析仅供参考，不构成投资建议。投资决策请结合个人风险承受能力和专业意见。
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
