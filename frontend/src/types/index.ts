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

export interface WorldCupMarketPrice {
  label: string;
  odds: number;
  probability: number;
}

export interface WorldCupMarket {
  market_type: 'h2h' | 'asian_handicap' | 'totals' | 'polymarket';
  title: string;
  line?: string;
  options: WorldCupMarketPrice[];
}

export interface WorldCupPick {
  bet_type: 'h2h' | 'asian_handicap' | 'totals';
  strategy: string;
  side: string;
  signal_label?: string;
  book_probability?: number;
  fair_probability?: number;
  confidence: number;
  edge: number;
  stake_pct: number;
  stake_amount: number;
  rationale: string[];
}

export interface WorldCupMatchSummary {
  match_id: string;
  stage: string;
  group_name?: string;
  kickoff_at: string;
  home_team: string;
  away_team: string;
  venue: string;
  status: 'upcoming' | 'live' | 'settled';
  home_score?: number;
  away_score?: number;
  source?: string;
  external_url?: string;
  featured_pick: WorldCupPick;
  key_market: WorldCupMarket;
}

export interface WorldCupMatchDetail extends WorldCupMatchSummary {
  markets: WorldCupMarket[];
  line_movement: Array<{
    label: string;
    line: number;
    home_odds: number;
    away_odds: number;
  }>;
  polymarket_probabilities: Record<string, number>;
  bankroll_bet?: {
    bet_type?: string;
    side?: string;
    signal_label?: string;
    strategy?: string;
    odds?: number;
    stake_pct?: number;
    stake_amount?: number;
    status?: string;
    pnl?: number;
    placed_at?: string | null;
    settled_at?: string | null;
    result_label?: string | null;
  } | null;
}

export interface WorldCupBankrollPoint {
  label: string;
  bankroll: number;
  pnl: number;
}

export interface WorldCupOverview {
  tournament: string;
  bankroll: number;
  initial_bankroll: number;
  settled_matches: number;
  open_positions: number;
  roi: number;
  max_drawdown: number;
  next_match_at: string;
  last_updated_at?: string;
  phase_breakdown: Array<{
    phase: string;
    matches: number;
    roi: number;
    hit_rate: number;
  }>;
  featured_matches: WorldCupMatchSummary[];
  bankroll_curve: WorldCupBankrollPoint[];
  market_heat: Array<{
    label: string;
    value: number;
  }>;
}
