import { NextRequest, NextResponse } from 'next/server';
import { SavedStock } from '../../../../types';

// 模拟数据存储
const savedStocks: SavedStock[] = [
  {
    id: 1,
    stock_id: 1,
    user_id: 1,
    symbol: 'AAPL',
    added_at: new Date().toISOString(),
    notes: '长期持有的核心资产',
    stock: {
      symbol: 'AAPL',
      name: '苹果公司',
      exchange: 'NASDAQ',
      currency: 'USD'
    }
  },
  {
    id: 2,
    stock_id: 2,
    user_id: 1,
    symbol: 'MSFT',
    added_at: new Date().toISOString(),
    notes: '云业务和AI前景看好',
    stock: {
      symbol: 'MSFT',
      name: '微软公司',
      exchange: 'NASDAQ',
      currency: 'USD'
    }
  }
];

// 获取所有保存的股票
export async function GET() {
  // 模拟网络延迟
  await new Promise((resolve) => setTimeout(resolve, 300));
  
  return NextResponse.json({
    success: true,
    data: savedStocks,
  });
}

// 保存新的股票
export async function POST(request: NextRequest) {
  const body = await request.json();
  const { symbol, name, notes } = body;
  
  // 验证必要字段
  if (!symbol) {
    return NextResponse.json(
      {
        success: false,
        error: '股票代码不能为空',
      },
      { status: 400 }
    );
  }
  
  // 检查是否已存在
  const existingIndex = savedStocks.findIndex(
    (stock) => stock.symbol === symbol
  );
  
  // 模拟网络延迟
  await new Promise((resolve) => setTimeout(resolve, 500));
  
  if (existingIndex >= 0) {
    // 更新现有记录
    savedStocks[existingIndex] = {
      ...savedStocks[existingIndex],
      notes: notes || savedStocks[existingIndex].notes,
    };
  } else {
    // 添加新记录
    savedStocks.push({
      id: savedStocks.length + 1,
      stock_id: savedStocks.length + 1,
      user_id: 1,
      symbol,
      added_at: new Date().toISOString(),
      notes: notes || '',
      stock: {
        symbol,
        name: name || symbol,
        exchange: 'UNKNOWN',
        currency: 'USD'
      }
    });
  }
  
  return NextResponse.json({
    success: true,
  });
} 