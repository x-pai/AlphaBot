import { NextRequest, NextResponse } from 'next/server';
import { TaskInfo, TaskCreate } from '../../../types';

// 模拟数据存储
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

// 获取所有任务
export async function GET() {
  // 模拟网络延迟
  await new Promise((resolve) => setTimeout(resolve, 500));
  
  return NextResponse.json({
    success: true,
    data: mockTasks,
  });
}

// 创建新任务
export async function POST(request: NextRequest) {
  const body = await request.json() as TaskCreate;
  
  // 验证必要字段
  if (!body.task_type) {
    return NextResponse.json(
      {
        success: false,
        error: '任务类型不能为空',
      },
      { status: 400 }
    );
  }
  
  // 模拟网络延迟
  await new Promise((resolve) => setTimeout(resolve, 800));
  
  // 创建新任务
  const newTask: TaskInfo = {
    task_id: `${mockTasks.length + 1}`,
    description: `更新股票数据: ${body.symbol || '所有'}`,
    interval: body.interval,
    next_run: new Date(Date.now() + body.interval * 1000).toISOString(),
    run_count: 0,
    is_enabled: body.is_enabled,
  };
  
  // 添加到模拟数据中
  mockTasks.push(newTask);
  
  return NextResponse.json({
    success: true,
    data: newTask,
  });
} 