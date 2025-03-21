'use client';

import { useState, useEffect, useCallback } from 'react';
import { createAsyncAITask, getAsyncTaskStatus, cancelAsyncTask } from '@/lib/api';

interface AsyncAIAnalysisProps {
  symbol: string;
  taskType: 'stock_analysis' | 'time_series' | 'intraday';
  analysisType?: 'rule' | 'ml' | 'llm';
  interval?: string;
  range?: string;
  dataSource?: string;
  onResult?: (result: any) => void;
  onError?: (error: string) => void;
  autoStart?: boolean;
}

interface TaskStatusResponse {
  task_id: string;
  status: string;
  status_display: string;
  message: string;
  result?: any;
  error?: string;
  progress?: number;
}

export default function AsyncAIAnalysis({
  symbol,
  taskType,
  analysisType = 'llm',
  interval,
  range,
  dataSource,
  onResult,
  onError,
  autoStart = true
}: AsyncAIAnalysisProps) {
  // 状态
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('idle');
  const [message, setMessage] = useState<string>('');
  const [progress, setProgress] = useState<number>(0);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);
  const [isCanceling, setIsCanceling] = useState<boolean>(false);

  // Move clearPollingInterval to be defined first
  const clearPollingInterval = useCallback(() => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
  }, [pollingInterval]);

  // 检查任务状态
  const checkTaskStatus = useCallback(async () => {
    if (!taskId) return;
    
    const response = await getAsyncTaskStatus(taskId);
    
    if (response.success && response.data) {
      const taskData = response.data as TaskStatusResponse;
      
      // 更新状态信息
      setMessage(taskData.message || '');
      
      // 如果有进度信息
      if (taskData.progress !== undefined) {
        setProgress(taskData.progress);
      }
      
      // 任务完成
      if (taskData.status === 'completed' || taskData.status === 'SUCCESS') {
        clearPollingInterval();
        setStatus('completed');
        setResult(taskData.result);
        if (onResult) onResult(taskData.result);
      }
      
      // 任务失败
      if (taskData.status === 'failed' || taskData.status === 'FAILURE') {
        clearPollingInterval();
        setStatus('error');
        setError(taskData.error || '分析任务失败');
        if (onError) onError(taskData.error || '分析任务失败');
      }
      
      // 任务被取消
      if (taskData.status === 'REVOKED' || taskData.status === 'revoked' || taskData.status === 'canceled') {
        clearPollingInterval();
        setStatus('canceled');
        setMessage('分析任务已取消');
        setIsCanceling(false);
      }
    } else {
      // 获取状态失败
      setError(response.error || '获取任务状态失败');
      if (response.error?.includes('任务不存在')) {
        clearPollingInterval();
        setStatus('error');
      }
    }
  }, [taskId, onResult, onError, clearPollingInterval]);

  // 取消任务
  const cancelTask = useCallback(async () => {
    if (!taskId) return;
    
    setIsCanceling(true);
    setMessage('正在取消分析...');
    
    try {
      const response = await cancelAsyncTask(taskId);
      
      if (response.success) {
        clearPollingInterval();
        setStatus('canceled');
        setMessage('分析任务已取消');
      } else {
        setError(response.error || '取消任务失败');
        setMessage('取消任务失败，任务可能已结束');
        // 继续轮询检查状态
        await checkTaskStatus();
      }
    } catch (error) {
      console.error('取消任务出错:', error);
      setError('取消任务时发生错误');
    } finally {
      setIsCanceling(false);
    }
  }, [taskId, checkTaskStatus, clearPollingInterval]);

  // 启动分析任务
  const startAnalysis = useCallback(async () => {
    setStatus('starting');
    setError(null);
    setResult(null);
    setIsCanceling(false);
    
    const response = await createAsyncAITask(symbol, taskType, {
      analysis_type: analysisType,
      data_source: dataSource,
      interval,
      range
    });
    
    if (response.success && response.data) {
      setTaskId(response.data.task_id);
      setStatus('polling');
      setMessage(response.data.message || '已启动分析任务');
    } else {
      setError(response.error || '启动分析失败');
      setStatus('error');
      if (onError) onError(response.error || '启动分析失败');
    }
  }, [symbol, taskType, analysisType, interval, range, dataSource, onError]);

  // 启动轮询
  useEffect(() => {
    if (status === 'polling' && !pollingInterval) {
      const interval = setInterval(() => {
        checkTaskStatus();
      }, 3000); // 每3秒轮询一次
      setPollingInterval(interval);
    }
    
    return () => {
      clearPollingInterval();
    };
  }, [status, pollingInterval, checkTaskStatus, clearPollingInterval]);

  // 组件挂载时自动启动
  useEffect(() => {
    if (autoStart) {
      startAnalysis();
    }
    
    return () => {
      // 组件卸载时清除轮询并尝试取消任务
      clearPollingInterval();
    };
  }, [autoStart, startAnalysis, clearPollingInterval]);

  return (
    <div className="async-ai-analysis">
      {/* 状态显示 */}
      {status === 'idle' && (
        <div className="flex items-center justify-center">
          <button 
            onClick={startAnalysis}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            开始分析
          </button>
        </div>
      )}
      
      {/* 加载中状态 */}
      {(status === 'starting' || status === 'polling' || status === 'PENDING' || status === 'STARTED' || status === 'PROGRESS') && (
        <div className="flex flex-col items-center justify-center">
          <div className="mb-2">
            <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          </div>
          <div className="text-center">
            <p className="text-lg font-semibold">{message || '正在进行AI分析...'}</p>
            {progress > 0 && (
              <div className="w-full bg-gray-200 rounded-full h-2.5 mt-2">
                <div 
                  className="bg-blue-500 h-2.5 rounded-full" 
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
            )}
            <button 
              onClick={cancelTask} 
              disabled={isCanceling}
              className={`mt-4 px-3 py-1 text-sm ${
                isCanceling 
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              } rounded`}
            >
              {isCanceling ? '取消中...' : '取消分析'}
            </button>
          </div>
        </div>
      )}
      
      {/* 错误状态 */}
      {(status === 'error' || status === 'FAILURE') && (
        <div className="text-center text-red-500">
          <p className="text-lg font-semibold">分析失败</p>
          <p>{error || '未知错误'}</p>
          <button 
            onClick={startAnalysis}
            className="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            重新分析
          </button>
        </div>
      )}
      
      {/* 取消状态 */}
      {status === 'canceled' && (
        <div className="text-center">
          <p className="text-lg font-semibold text-gray-700">{message || '分析已取消'}</p>
          <button 
            onClick={startAnalysis}
            className="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            重新分析
          </button>
        </div>
      )}
      
      {/* 完成状态 - 通常不显示，结果会通过onResult回调传递 */}
      {status === 'completed' && !onResult && result && (
        <div className="mt-4">
          <h3 className="text-lg font-semibold mb-2">分析结果</h3>
          <pre className="bg-gray-100 p-4 rounded overflow-auto max-h-96">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
} 