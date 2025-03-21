import { NextRequest, NextResponse } from 'next/server';
import { StockInfo } from '../../../../types';

// 模拟数据
const mockStocks: StockInfo[] = [
  {
    symbol: 'AAPL',
    name: '苹果公司',
    exchange: 'NASDAQ',
    currency: 'USD',
    price: 182.63,
    change: 1.25,
    changePercent: 0.69,
    marketCap: 2850000000000,
    volume: 58000000,
  },
  {
    symbol: 'MSFT',
    name: '微软公司',
    exchange: 'NASDAQ',
    currency: 'USD',
    price: 417.88,
    change: 2.35,
    changePercent: 0.57,
    marketCap: 3100000000000,
    volume: 25000000,
  },
  {
    symbol: 'GOOGL',
    name: '谷歌公司',
    exchange: 'NASDAQ',
    currency: 'USD',
    price: 175.98,
    change: -0.87,
    changePercent: -0.49,
    marketCap: 2200000000000,
    volume: 30000000,
  },
  {
    symbol: 'AMZN',
    name: '亚马逊公司',
    exchange: 'NASDAQ',
    currency: 'USD',
    price: 178.75,
    change: 1.05,
    changePercent: 0.59,
    marketCap: 1850000000000,
    volume: 40000000,
  },
  {
    symbol: 'TSLA',
    name: '特斯拉公司',
    exchange: 'NASDAQ',
    currency: 'USD',
    price: 248.42,
    change: -3.78,
    changePercent: -1.5,
    marketCap: 790000000000,
    volume: 120000000,
  },
  {
    symbol: 'BABA',
    name: '阿里巴巴集团',
    exchange: 'NYSE',
    currency: 'USD',
    price: 78.54,
    change: 0.32,
    changePercent: 0.41,
    marketCap: 198000000000,
    volume: 15000000,
  },
  {
    symbol: '600519',
    name: '贵州茅台',
    exchange: 'SSE',
    currency: 'CNY',
    price: 1789.99,
    change: 15.23,
    changePercent: 0.86,
    marketCap: 2250000000000,
    volume: 5000000,
  },
  {
    symbol: '000858',
    name: '五粮液',
    exchange: 'SZSE',
    currency: 'CNY',
    price: 168.75,
    change: 2.35,
    changePercent: 1.41,
    marketCap: 655000000000,
    volume: 12000000,
  },
];

export async function GET(request: NextRequest) {
  // 获取查询参数
  const searchParams = request.nextUrl.searchParams;
  const query = searchParams.get('q') || '';

  // 如果查询为空，返回所有股票
  if (!query) {
    return NextResponse.json({
      success: true,
      data: mockStocks,
    });
  }

  // 过滤匹配的股票
  const filteredStocks = mockStocks.filter(
    (stock) =>
      stock.symbol.toLowerCase().includes(query.toLowerCase()) ||
      stock.name.toLowerCase().includes(query.toLowerCase())
  );

  // 模拟网络延迟
  await new Promise((resolve) => setTimeout(resolve, 500));

  return NextResponse.json({
    success: true,
    data: filteredStocks,
  });
}