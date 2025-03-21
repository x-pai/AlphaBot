import { NextRequest, NextResponse } from 'next/server';
import { SavedStock } from '../../../../types';

// 模拟数据存储
const savedStocks: SavedStock[] = [
  {
    symbol: 'AAPL',
    name: '苹果公司',
    addedAt: new Date().toISOString(),
    notes: '长期持有的核心资产',
  },
  {
    symbol: 'MSFT',
    name: '微软公司',
    addedAt: new Date().toISOString(),
    notes: '云业务和AI前景看好',
  },
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
      symbol,
      name: name || symbol,
      addedAt: new Date().toISOString(),
      notes: notes || '',
    });
  }
  
  return NextResponse.json({
    success: true,
  });
} 