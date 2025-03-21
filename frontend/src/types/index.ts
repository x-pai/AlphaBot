// 股票基本信息
export interface StockInfo {
  symbol: string;
  name: string;
  exchange: string;
  currency: string;
  price?: number;
  change?: number;
  changePercent?: number;
  marketCap?: number;
  volume?: number;
  marketStatus?: 'open' | 'closed' | 'pre' | 'after';
  pe?: number;
  dividend?: number;
}

// 股票历史价格数据点
export interface StockPricePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// 股票历史价格数据
export interface StockPriceHistory {
  symbol: string;
  data: StockPricePoint[];
}

// AI分析结果
export interface AIAnalysis {
  summary: string;
  sentiment: 'positive' | 'neutral' | 'negative';
  keyPoints: string[];
  recommendation: string;
  riskLevel: 'low' | 'medium' | 'high';
  analysisType?: 'rule' | 'ml' | 'llm';
}

// 从 user.ts 导入 SavedStock
export type { SavedStock } from './user';

// API响应
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

// 缓存统计信息
export interface CacheStats {
  total_items: number;
  active_items: number;
  expired_items: number;
  cache_keys: string[];
}

// 任务基本信息
export interface TaskInfo {
  task_id: string;
  description: string;
  interval: number;
  next_run: string;
  last_run?: string;
  run_count: number;
  is_enabled: boolean;
}

// 创建任务请求
export interface TaskCreate {
  task_type: string;
  symbol?: string;
  interval: number;
  is_enabled: boolean;
}

// 更新任务请求
export interface TaskUpdate {
  interval?: number;
  is_enabled?: boolean;
} 