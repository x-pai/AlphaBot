import { NextRequest, NextResponse } from 'next/server';
import { SavedStock } from '../../../../../types';

// 模拟数据存储
// 在实际应用中，这应该是一个数据库或其他持久化存储
// 这里我们创建一个本地的模拟数据，与 ../route.ts 中的数据结构相同
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

// 删除保存的股票
export async function DELETE(
  request: Request
): Promise<Response> {
  const { pathname } = new URL(request.url);
  const symbol = pathname.split('/').pop() || '';
  
  // 模拟网络延迟
  await new Promise((resolve) => setTimeout(resolve, 500));
  
  try {
    // 在实际应用中，这应该是对数据库的操作
    // 这里我们模拟删除操作，但由于每个API路由是独立的，
    // 这个删除操作不会影响到 ../route.ts 中的数据
    // 在实际项目中，应该使用共享的数据存储（如数据库）
    const stockIndex = savedStocks.findIndex(stock => stock.symbol === symbol);
    
    if (stockIndex === -1) {
      return NextResponse.json(
        {
          success: false,
          error: '未找到该股票',
        },
        { status: 404 }
      );
    }
    
    // 从数组中移除
    savedStocks.splice(stockIndex, 1);
    
    // 返回成功响应
    return NextResponse.json({
      success: true,
    });
  } catch (error) {
    console.error('Error deleting saved stock:', error);
    return NextResponse.json(
      {
        success: false,
        error: '删除股票时出错',
      },
      { status: 500 }
    );
  }
} 