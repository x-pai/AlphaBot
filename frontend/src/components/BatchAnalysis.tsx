import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Input, Progress, Select, message } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import { api } from '../lib/api';
import { MAX_BATCH_SYMBOLS, validateBatchSymbols } from '../lib/stockSymbols';

const { TextArea } = Input;
const { Option } = Select;

type AnalysisResultSummary = {
  summary?: string;
  sentiment?: string;
  recommendation?: string;
  riskLevel?: string;
};

type TaskResponse = {
  data: {
    status: string;
    message?: string;
    progress?: number;
    current_symbol?: string | null;
    completed?: number;
    total?: number;
    report_url?: string | null;
    errors?: Record<string, string>;
    results?: Record<string, AnalysisResultSummary>;
  };
  success: boolean;
  error?: string;
};

const RUNNING_STATUSES = new Set(['PENDING', 'STARTED', 'PROGRESS']);

const defaultTaskState = {
  taskId: '',
  status: '',
  statusMessage: '',
  progress: 0,
  currentSymbol: '',
  completedCount: 0,
  totalCount: 0,
  reportUrl: '',
  errors: {} as Record<string, string>,
  results: {} as Record<string, AnalysisResultSummary>,
};

const formatStatusLabel = (status: string) => {
  switch (status) {
    case 'PENDING':
      return '等待执行';
    case 'STARTED':
      return '执行中';
    case 'PROGRESS':
      return '分析中';
    case 'SUCCESS':
      return '已完成';
    case 'FAILURE':
      return '执行失败';
    case 'CANCELLED':
    case 'REVOKED':
      return '已取消';
    default:
      return status || '未开始';
  }
};

const BatchAnalysis: React.FC = () => {
  const [symbols, setSymbols] = useState('');
  const [interval, setInterval] = useState('daily');
  const [range, setRange] = useState('1m');
  const [taskState, setTaskState] = useState(defaultTaskState);
  const [loading, setLoading] = useState(false);
  const intervalRef = useRef<number | null>(null);

  const validation = useMemo(() => validateBatchSymbols(symbols), [symbols]);
  const isTaskRunning = !!taskState.taskId && RUNNING_STATUSES.has(taskState.status);
  const exceedsLimit = validation.validCodes.length > MAX_BATCH_SYMBOLS;
  const canSubmit = validation.validCodes.length > 0 && validation.invalidSymbols.length === 0 && !exceedsLimit;

  const stopPolling = useCallback(() => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const pollTaskStatus = useCallback((taskId: string) => {
    stopPolling();

    const newInterval = window.setInterval(async () => {
      try {
        const response = await api.get<TaskResponse>(`/async/ai/task/${taskId}`);
        if (!response.data.success) {
          return;
        }

        const {
          status,
          message: taskMessage,
          progress,
          current_symbol,
          completed,
          total,
          report_url,
          errors,
          results,
        } = response.data.data;

        setTaskState({
          taskId,
          status,
          statusMessage: taskMessage || '',
          progress: progress || 0,
          currentSymbol: current_symbol || '',
          completedCount: completed || 0,
          totalCount: total || 0,
          reportUrl: report_url || '',
          errors: errors || {},
          results: results || {},
        });

        if (status === 'SUCCESS' || status === 'FAILURE') {
          stopPolling();
          if (status === 'SUCCESS') {
            message.success('分析完成');
          } else {
            message.error('分析失败');
          }
        }
      } catch {
        stopPolling();
        message.error('获取任务状态失败');
      }
    }, 2000);

    intervalRef.current = newInterval;
  }, [stopPolling]);

  const startAnalysis = async () => {
    try {
      setLoading(true);

      if (validation.validCodes.length === 0) {
        message.error('请输入至少一个有效股票代码');
        return;
      }

      if (validation.invalidSymbols.length > 0) {
        message.error('请先修正无效的股票代码');
        return;
      }

      if (validation.validCodes.length > MAX_BATCH_SYMBOLS) {
        message.error(`批量分析一次最多支持 ${MAX_BATCH_SYMBOLS} 个股票`);
        return;
      }

      stopPolling();
      setTaskState({
        ...defaultTaskState,
        totalCount: validation.validCodes.length,
      });

      const response = await api.post('/async/ai/batch-analyze', {
        task_type: 'time_series',
        symbol: validation.validCodes,
        interval,
        range,
      });

      if (!response.data.success) {
        message.error(response.data.error || '启动分析任务失败');
        return;
      }

      const taskId = response.data.data.task_id;
      setTaskState({
        taskId,
        status: 'PENDING',
        statusMessage: response.data.data.message || '任务已创建',
        progress: 0,
        currentSymbol: '',
        completedCount: 0,
        totalCount: validation.validCodes.length,
        reportUrl: '',
        errors: {},
        results: {},
      });

      pollTaskStatus(taskId);
      message.success('批量分析任务已启动');
    } catch {
      message.error('启动分析任务失败');
    } finally {
      setLoading(false);
    }
  };

  const cancelAnalysis = async () => {
    if (!taskState.taskId) {
      return;
    }

    try {
      const response = await api.delete(`/async/ai/task/${taskState.taskId}`);
      if (!response.data.success) {
        message.error(response.data.error || '取消任务失败');
        return;
      }

      stopPolling();
      setTaskState((prev) => ({
        ...prev,
        status: 'CANCELLED',
        statusMessage: '任务已取消',
      }));
      message.success('任务已取消');
    } catch {
      message.error('取消任务失败');
    }
  };

  const downloadReport = async () => {
    const reportTaskId = taskState.reportUrl?.split('/').slice(-2, -1)[0] || taskState.taskId;
    if (!reportTaskId) {
      message.error('请先完成一次分析');
      return;
    }

    try {
      const response = await api.get(`/reports/${reportTaskId}/download`, {
        responseType: 'blob',
      });

      if (response.status !== 200) {
        message.error('下载报告失败');
        return;
      }

      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `time_series_analysis_${reportTaskId}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      message.error('下载报告失败');
    }
  };

  return (
    <div className="space-y-6 p-4">
      <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900/40">
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">分析配置</h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            仅支持输入 6 位纯数字股票代码，例如 `000001`、`600519`。提交后会在后端自动推断交易所。
          </p>
        </div>

        <div className="mb-4">
          <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300">
            股票代码
          </label>
          <TextArea
            value={symbols}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setSymbols(e.target.value)}
            placeholder="例如：000001 600519 601318"
            className="w-full"
            rows={4}
            disabled={isTaskRunning}
          />
          <div className="mt-3 space-y-2 text-xs">
            <div className="flex flex-wrap items-center gap-3 text-gray-500 dark:text-gray-400">
              <span>有效代码 {validation.validCodes.length}</span>
              <span>无效代码 {validation.invalidSymbols.length}</span>
              <span>重复代码 {validation.duplicateSymbols.length}</span>
            </div>

            {validation.normalizedPreview.length > 0 && (
              <div className="rounded bg-gray-50 px-3 py-2 text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                后端将自动按以下格式分析：{validation.normalizedPreview.join(', ')}
              </div>
            )}

            {validation.invalidSymbols.length > 0 && (
              <div className="rounded bg-red-50 px-3 py-2 text-red-600 dark:bg-red-900/20 dark:text-red-300">
                无效输入：{validation.invalidSymbols.join(', ')}。仅支持 6 位纯数字代码。
              </div>
            )}

            {validation.duplicateSymbols.length > 0 && (
              <div className="rounded bg-amber-50 px-3 py-2 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300">
                重复输入会自动去重：{validation.duplicateSymbols.join(', ')}
              </div>
            )}

            {exceedsLimit && (
              <div className="rounded bg-red-50 px-3 py-2 text-red-600 dark:bg-red-900/20 dark:text-red-300">
                批量分析一次最多支持 {MAX_BATCH_SYMBOLS} 个股票
              </div>
            )}
          </div>
        </div>

        <div className="mb-4 flex flex-col gap-4 md:flex-row">
          <div className="flex-1">
            <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300">
              时间间隔
            </label>
            <Select value={interval} onChange={setInterval} className="w-full" disabled={isTaskRunning}>
              <Option value="daily">每日</Option>
              <Option value="weekly">每周</Option>
              <Option value="monthly">每月</Option>
            </Select>
          </div>
          <div className="flex-1">
            <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300">
              时间范围
            </label>
            <Select value={range} onChange={setRange} className="w-full" disabled={isTaskRunning}>
              <Option value="1m">1个月</Option>
              <Option value="3m">3个月</Option>
              <Option value="6m">6个月</Option>
              <Option value="1y">1年</Option>
            </Select>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="primary" onClick={startAnalysis} loading={loading} disabled={!canSubmit || isTaskRunning}>
            {taskState.status ? '重新分析' : '开始分析'}
          </Button>
          {isTaskRunning && (
            <Button danger onClick={cancelAnalysis}>
              取消任务
            </Button>
          )}
          {taskState.status === 'SUCCESS' && (
            <Button icon={<DownloadOutlined />} onClick={downloadReport}>
              下载报告
            </Button>
          )}
        </div>
      </div>

      {(taskState.status || taskState.progress > 0) && (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-5 dark:border-gray-700 dark:bg-gray-800/50">
          <div className="mb-3">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">执行结果</h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              状态：{formatStatusLabel(taskState.status)}
            </p>
          </div>

          {taskState.statusMessage && (
            <div className="mb-2 text-sm text-gray-600 dark:text-gray-300">{taskState.statusMessage}</div>
          )}

          {taskState.totalCount > 0 && (
            <div className="mb-3 text-sm text-gray-600 dark:text-gray-300">
              进度：{taskState.completedCount} / {taskState.totalCount}
              {taskState.currentSymbol ? `，当前股票：${taskState.currentSymbol}` : ''}
            </div>
          )}

          {taskState.status !== 'CANCELLED' && (
            <Progress
              percent={Math.round(taskState.progress)}
              status={taskState.status === 'FAILURE' ? 'exception' : undefined}
            />
          )}

          {Object.keys(taskState.errors).length > 0 && (
            <div className="mt-4">
              <div className="mb-2 text-sm font-medium text-red-600 dark:text-red-400">失败股票</div>
              <div className="space-y-2 text-sm text-red-600 dark:text-red-300">
                {Object.entries(taskState.errors).map(([symbol, error]) => (
                  <div key={symbol}>
                    <span className="font-medium">{symbol}</span>：{error}
                  </div>
                ))}
              </div>
            </div>
          )}

          {taskState.status === 'SUCCESS' && Object.keys(taskState.results).length > 0 && (
            <div className="mt-4">
              <div className="mb-2 text-sm font-medium text-gray-900 dark:text-white">分析摘要</div>
              <div className="space-y-3">
                {Object.entries(taskState.results).map(([symbol, result]) => (
                  <div
                    key={symbol}
                    className="rounded border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900/40"
                  >
                    <div className="mb-1 text-sm font-medium text-gray-900 dark:text-white">{symbol}</div>
                    {result.summary && (
                      <div className="mb-2 text-sm text-gray-600 dark:text-gray-300">{result.summary}</div>
                    )}
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {result.sentiment ? `情绪: ${result.sentiment}` : ''}
                      {result.riskLevel ? `  风险: ${result.riskLevel}` : ''}
                    </div>
                    {result.recommendation && (
                      <div className="mt-2 text-sm text-gray-700 dark:text-gray-200">
                        建议：{result.recommendation}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default BatchAnalysis;
