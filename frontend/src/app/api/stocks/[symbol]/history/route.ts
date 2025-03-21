import { NextRequest, NextResponse } from 'next/server';
import { StockPriceHistory, StockPricePoint } from '../../../../../types';

// 生成模拟历史数据
function generateMockHistoryData(
  _symbol: string,
  days: number,
  startPrice: number
): StockPricePoint[] {
  const data: StockPricePoint[] = [];
  let currentPrice = startPrice;
  
  const today = new Date();
  
  for (let i = days; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    
    // 随机波动，但保持一定趋势
    const volatility = Math.random() * 0.03; // 3%的波动
    const trend = Math.random() > 0.5 ? 1 : -1; // 随机趋势
    const change = currentPrice * volatility * trend;
    
    const open = currentPrice;
    const close = currentPrice + change;
    const high = Math.max(open, close) + Math.random() * Math.abs(change);
    const low = Math.min(open, close) - Math.random() * Math.abs(change);
    const volume = Math.floor(Math.random() * 10000000) + 1000000;
    
    data.push({
      date: date.toISOString().split('T')[0],
      open: parseFloat(open.toFixed(2)),
      high: parseFloat(high.toFixed(2)),
      low: parseFloat(low.toFixed(2)),
      close: parseFloat(close.toFixed(2)),
      volume,
    });
    
    currentPrice = close;
  }
  
  return data;
}

// 模拟数据
const mockPriceHistories: Record<string, { startPrice: number }> = {
  'AAPL': { startPrice: 170 },
  'MSFT': { startPrice: 400 },
  'GOOGL': { startPrice: 160 },
  'AMZN': { startPrice: 170 },
  'TSLA': { startPrice: 260 },
  'BABA': { startPrice: 75 },
  '600519': { startPrice: 1700 },
  '000858': { startPrice: 160 },
};

export async function GET(
  request: NextRequest
): Promise<Response> {
  const { pathname } = new URL(request.url);
  const symbol = pathname.split('/').pop()?.toUpperCase() || '';
  const searchParams = new URL(request.url).searchParams;
  const interval = searchParams.get('interval') || 'daily';
  const range = searchParams.get('range') || '1m';
  
  // 模拟网络延迟
  await new Promise((resolve) => setTimeout(resolve, 800));
  
  // 检查股票是否存在
  if (!mockPriceHistories[symbol]) {
    return NextResponse.json(
      {
        success: false,
        error: '未找到该股票的历史数据',
      },
      { status: 404 }
    );
  }
  
  // 根据范围确定天数
  let days = 30; // 默认1个月
  switch (range) {
    case '3m':
      days = 90;
      break;
    case '6m':
      days = 180;
      break;
    case '1y':
      days = 365;
      break;
    case '5y':
      days = 365 * 5;
      break;
    default:
      days = 30;
  }
  
  // 生成历史数据
  const data = generateMockHistoryData(
    symbol,
    days,
    mockPriceHistories[symbol].startPrice
  );
  
  // 如果不是daily，则需要聚合数据
  let aggregatedData = data;
  if (interval === 'weekly') {
    // 简单实现：每7天取一个点
    aggregatedData = data.filter((_, index) => index % 7 === 0);
  } else if (interval === 'monthly') {
    // 简单实现：每30天取一个点
    aggregatedData = data.filter((_, index) => index % 30 === 0);
  }
  
  const response: StockPriceHistory = {
    symbol,
    data: aggregatedData,
  };
  
  return NextResponse.json({
    success: true,
    data: response,
  });
} 