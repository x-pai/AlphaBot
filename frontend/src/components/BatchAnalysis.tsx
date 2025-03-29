import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Button, Input, Select, Progress, message } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import { api } from '../lib/api';
import { TicketsPlane } from 'lucide-react';

const { TextArea } = Input;
const { Option } = Select;

interface TaskResponse {
  data: {
    status: string;
    meta?: {
      progress?: number;
    };
  };
  success: boolean;
  error?: string;
}

const BatchAnalysis: React.FC = () => {
  const [symbols, setSymbols] = useState<string>('');
  const [interval, setInterval] = useState<string>('daily');
  const [range, setRange] = useState<string>('1m');
  const [taskId, setTaskId] = useState<string>('');
  const [status, setStatus] = useState<string>('');
  const [progress, setProgress] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const intervalRef = useRef<number | null>(null);
  
  useEffect(() => {
    return () => {
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current);
      }
    };
  }, []);
  
  const startAnalysis = async () => {
    try {
      setLoading(true);
      // 将输入的股票代码转换为数组
      const symbolList = symbols.split(/[,，\s]+/).filter(s => s.trim());
      
      if (symbolList.length === 0) {
        message.error('请输入至少一个股票代码');
        return;
      }
      
      const response = await api.post('/async/ai/batch-analyze', {
        task_type: 'time_series',
        symbol: symbolList,
        interval,
        range
      });
      
      if (response.data.success) {
        setTaskId(response.data.data.task_id);
        message.success('批量分析任务已启动');
        pollTaskStatus(response.data.data.task_id);
      } else {
        message.error(response.data.error || '启动分析任务失败');
      }
    } catch (error) {
      message.error('启动分析任务失败');
    } finally {
      setLoading(false);
    }
  };
  
  const pollTaskStatus = useCallback((taskId: string) => {
    // 清除之前的轮询
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
    }
    
    const newInterval = window.setInterval(async () => {
      try {
        const response = await api.get<TaskResponse>(`/async/ai/task/${taskId}`);
        const { status, meta } = response.data.data;
        
        setStatus(status);
        if (meta?.progress) {
          setProgress(meta.progress);
        }
        
        if (status === 'SUCCESS' || status === 'FAILURE') {
          if (intervalRef.current !== null) {
            window.clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          if (status === 'SUCCESS') {
            message.success('分析完成');
          } else {
            message.error('分析失败');
          }
        }
      } catch (error) {
        if (intervalRef.current !== null) {
          window.clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        message.error('获取任务状态失败');
      }
    }, 2000);
    
    intervalRef.current = newInterval;
  }, []);
  
  const downloadReport = async () => {
    if (!taskId) {
      message.error('请先启动分析任务');
      return;
    } 
    // 下载pdf文件，并保存到本地
    const response = await api.get(`/reports/${taskId}/download`);
    if (response.status === 200) {  
      const file = new Blob([response.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(file);
      const a = document.createElement('a');
      a.href = url;
      a.download = `time_series_analysis_${taskId}.pdf`;
      a.click();
    } else {
      message.error(response.data.error || '下载报告失败');
    }
  };
  
  return (
    <div className="space-y-4 p-4">
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          股票代码（用逗号或空格分隔）
        </label>
        <TextArea
          value={symbols}
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setSymbols(e.target.value)}
          placeholder="例如: AAPL, GOOGL, MSFT"
          className="w-full"
          rows={4}
        />
      </div>
      
      <div className="flex space-x-4 mb-4">
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            时间间隔
          </label>
          <Select 
            value={interval} 
            onChange={setInterval}
            className="w-full"
          >
            <Option value="daily">每日</Option>
            <Option value="weekly">每周</Option>
            <Option value="monthly">每月</Option>
          </Select>
        </div>
        
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            时间范围
          </label>
          <Select 
            value={range} 
            onChange={setRange}
            className="w-full"
          >
            <Option value="1m">1个月</Option>
            <Option value="3m">3个月</Option>
            <Option value="6m">6个月</Option>
            <Option value="1y">1年</Option>
          </Select>
        </div>
      </div>
      
      <div className="flex justify-between items-center">
        <Button
          type="primary"
          onClick={startAnalysis}
          loading={loading}
          className="w-32"
        >
          开始分析
        </Button>
        
        {status === 'SUCCESS' && (
          <Button
            type="default"
            icon={<DownloadOutlined />}
            onClick={downloadReport}
          >
            下载报告
          </Button>
        )}
      </div>
      
      {(status || progress > 0) && (
        <div className="mt-4">
          <div className="mb-2">状态: {status}</div>
          {progress > 0 && (
            <Progress 
              percent={Math.round(progress)} 
              status={status === 'FAILURE' ? 'exception' : undefined}
            />
          )}
        </div>
      )}
    </div>
  );
};

export default BatchAnalysis; 