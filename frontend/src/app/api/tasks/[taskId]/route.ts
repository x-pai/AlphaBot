import { NextRequest, NextResponse } from 'next/server';
import { TaskInfo, TaskUpdate } from '../../../../types';

// 模拟数据存储
// 在实际应用中，这应该是一个数据库或其他持久化存储
// 这里我们创建一个本地的模拟数据，与 ../route.ts 中的数据结构相同
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

// 获取特定任务
export async function GET(
  request: Request
): Promise<Response> {
  const { pathname } = new URL(request.url);
  const taskId = pathname.split('/').pop() || '';
  
  // 模拟网络延迟
  await new Promise((resolve) => setTimeout(resolve, 300));
  
  // 查找任务
  const task = mockTasks.find((t) => t.task_id === taskId);
  
  if (!task) {
    return NextResponse.json(
      {
        success: false,
        error: '任务不存在',
      },
      { status: 404 }
    );
  }
  
  return NextResponse.json({
    success: true,
    data: task,
  });
}

// 更新任务
export async function PUT(
  request: Request
): Promise<Response> {
  const { pathname } = new URL(request.url);
  const taskId = pathname.split('/').pop() || '';
  const body = await request.json() as TaskUpdate;
  
  // 模拟网络延迟
  await new Promise((resolve) => setTimeout(resolve, 500));
  
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
  
  // 更新任务
  const updatedTask = {
    ...mockTasks[taskIndex],
  };
  
  if (body.interval !== undefined) {
    updatedTask.interval = body.interval;
    // 更新下次运行时间
    updatedTask.next_run = new Date(Date.now() + body.interval * 1000).toISOString();
  }
  
  if (body.is_enabled !== undefined) {
    updatedTask.is_enabled = body.is_enabled;
  }
  
  // 保存更新
  mockTasks[taskIndex] = updatedTask;
  
  return NextResponse.json({
    success: true,
    data: updatedTask,
  });
}

// 删除任务
export async function DELETE(
  request: Request
): Promise<Response> {
  const { pathname } = new URL(request.url);
  const taskId = pathname.split('/').pop() || '';
  
  // 模拟网络延迟
  await new Promise((resolve) => setTimeout(resolve, 400));
  
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
  
  // 删除任务
  mockTasks.splice(taskIndex, 1);
  
  return NextResponse.json({
    success: true,
    data: { message: '任务已删除' },
  });
} 