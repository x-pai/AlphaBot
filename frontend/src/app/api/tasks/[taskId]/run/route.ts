import { NextRequest, NextResponse } from 'next/server';
import { TaskInfo } from '../../../../../types';

// 模拟数据存储
// 在实际应用中，这应该是一个数据库或其他持久化存储
// 这里我们创建一个本地的模拟数据，与 ../../route.ts 中的数据结构相同
const mockTasks: TaskInfo[] = [
  {
    task_id: '1',
    description: '更新股票数据: AAPL',
    interval: 3600,
    next_run: new Date(Date.now() + 3600 * 1000).toISOString(),
    last_run: new Date(Date.now() - 1800 * 1000).toISOString(),
    run_count: 5,
    is_enabled: true,
  },
  {
    task_id: '2',
    description: '更新股票数据: 所有',
    interval: 86400,
    next_run: new Date(Date.now() + 43200 * 1000).toISOString(),
    last_run: new Date(Date.now() - 43200 * 1000).toISOString(),
    run_count: 2,
    is_enabled: true,
  },
];

// 立即运行任务
export async function POST(
  request: NextRequest
): Promise<Response> {
  const { pathname } = new URL(request.url);
  const taskId = pathname.split('/').pop() || '';
  
  // 需要先等待params
  await new Promise((resolve) => setTimeout(resolve, 1500));
  
  // 查找任务
  const taskIndex = mockTasks.findIndex((t) => t.task_id === taskId);
  
  if (taskIndex === -1) {
    return NextResponse.json(
      {
        success: false,
        error: '任务不存在',
      },
      { status: 404 }
    );
  }
  
  // 更新任务状态
  const now = new Date();
  mockTasks[taskIndex] = {
    ...mockTasks[taskIndex],
    last_run: now.toISOString(),
    next_run: new Date(now.getTime() + mockTasks[taskIndex].interval * 1000).toISOString(),
    run_count: mockTasks[taskIndex].run_count + 1,
  };
  
  return NextResponse.json({
    success: true,
    data: { 
      message: '任务已执行',
      task: mockTasks[taskIndex]
    },
  });
} 