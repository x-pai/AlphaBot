import React, { useState, useEffect, useCallback } from 'react';
import { getAllTasks, createTask, updateTask, deleteTask, runTaskNow } from '../lib/api';
import { TaskInfo, TaskCreate } from '../types';

const TaskManager: React.FC = () => {
  const [tasks, setTasks] = useState<TaskInfo[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState<boolean>(false);
  
  // 新任务表单状态
  const [newTask, setNewTask] = useState<TaskCreate>({
    task_type: 'update_stock_data',
    symbol: '',
    interval: 3600,
    is_enabled: true
  });

  // 加载所有任务 - 使用 useCallback 优化
  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await getAllTasks();
      if (response.success && response.data) {
        setTasks(response.data);
      } else {
        setError(response.error || '获取任务列表失败');
      }
    } catch (err) {
      setError('获取任务列表时发生错误');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  // 创建新任务
  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);
    
    try {
      const response = await createTask(newTask);
      if (response.success && response.data) {
        setMessage('任务创建成功');
        setShowCreateForm(false);
        // 重置表单
        setNewTask({
          task_type: 'update_stock_data',
          symbol: '',
          interval: 3600,
          is_enabled: true
        });
        // 重新加载任务列表
        loadTasks();
      } else {
        setError(response.error || '创建任务失败');
      }
    } catch (err) {
      setError('创建任务时发生错误');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // 更新任务状态
  const handleToggleTaskStatus = async (taskId: string, isEnabled: boolean) => {
    setLoading(true);
    setError(null);
    setMessage(null);
    
    try {
      const response = await updateTask(taskId, { is_enabled: !isEnabled });
      if (response.success) {
        setMessage(`任务已${!isEnabled ? '启用' : '禁用'}`);
        // 更新本地任务列表
        setTasks(tasks.map(task => 
          task.task_id === taskId ? { ...task, is_enabled: !isEnabled } : task
        ));
      } else {
        setError(response.error || '更新任务状态失败');
      }
    } catch (err) {
      setError('更新任务状态时发生错误');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // 删除任务
  const handleDeleteTask = async (taskId: string) => {
    if (!window.confirm('确定要删除此任务吗？此操作不可撤销。')) {
      return;
    }
    
    setLoading(true);
    setError(null);
    setMessage(null);
    
    try {
      const response = await deleteTask(taskId);
      if (response.success) {
        setMessage(response.data?.message || '任务已删除');
        // 从本地任务列表中移除
        setTasks(tasks.filter(task => task.task_id !== taskId));
      } else {
        setError(response.error || '删除任务失败');
      }
    } catch (err) {
      setError('删除任务时发生错误');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // 立即运行任务
  const handleRunTaskNow = async (taskId: string) => {
    setLoading(true);
    setError(null);
    setMessage(null);
    
    try {
      const response = await runTaskNow(taskId);
      if (response.success) {
        setMessage(response.data?.message || '任务已开始运行');
      } else {
        setError(response.error || '运行任务失败');
      }
    } catch (err) {
      setError('运行任务时发生错误');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // 格式化时间间隔
  const formatInterval = (seconds: number): string => {
    if (seconds < 60) {
      return `${seconds}秒`;
    } else if (seconds < 3600) {
      return `${Math.floor(seconds / 60)}分钟`;
    } else if (seconds < 86400) {
      return `${Math.floor(seconds / 3600)}小时`;
    } else {
      return `${Math.floor(seconds / 86400)}天`;
    }
  };

  // 自动隐藏消息
  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => {
        setMessage(null);
      }, 3000);

      return () => {
        clearTimeout(timer);
      };
    }
  }, [message]);

  // 组件加载时获取任务列表
  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  return (
    <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6 transition-colors duration-200">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold dark:text-white">定时任务管理</h2>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 focus:ring-2 focus:ring-blue-300 focus:ring-offset-2 dark:focus:ring-offset-gray-800 transition-colors duration-200 flex items-center"
          aria-label={showCreateForm ? '取消创建任务' : '创建新任务'}
        >
          {showCreateForm ? (
            <>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
              取消
            </>
          ) : (
            <>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
              </svg>
              创建任务
            </>
          )}
        </button>
      </div>
      
      {/* 错误提示 */}
      {error && (
        <div className="bg-red-100 dark:bg-red-900/30 border border-red-400 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded mb-4 flex justify-between items-center">
          <span>{error}</span>
          <button 
            onClick={() => setError(null)} 
            className="text-red-700 dark:text-red-400 hover:text-red-900 dark:hover:text-red-300"
            aria-label="关闭错误提示"
          >
            ✕
          </button>
        </div>
      )}
      
      {/* 成功消息 */}
      {message && (
        <div className="bg-green-100 dark:bg-green-900/30 border border-green-400 dark:border-green-800 text-green-700 dark:text-green-400 px-4 py-3 rounded mb-4 flex justify-between items-center">
          <span>{message}</span>
          <button 
            onClick={() => setMessage(null)} 
            className="text-green-700 dark:text-green-400 hover:text-green-900 dark:hover:text-green-300"
            aria-label="关闭成功提示"
          >
            ✕
          </button>
        </div>
      )}
      
      {/* 创建任务表单 */}
      {showCreateForm && (
        <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded mb-6 transition-colors duration-200 border border-gray-200 dark:border-gray-600">
          <h3 className="text-lg font-medium mb-3 dark:text-white">创建新任务</h3>
          <form onSubmit={handleCreateTask}>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" htmlFor="task-type">
                  任务类型
                </label>
                <select
                  value={newTask.task_type}
                  onChange={(e) => setNewTask({ ...newTask, task_type: e.target.value })}
                  className="w-full border dark:border-gray-600 rounded px-3 py-2 dark:bg-gray-800 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all duration-200"
                  disabled
                  id="task-type"
                  name="task-type"
                >
                  <option value="update_stock_data">更新股票数据</option>
                </select>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">目前仅支持更新股票数据的任务</p>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" htmlFor="task-symbol">
                  股票代码 (可选)
                </label>
                <input
                  type="text"
                  value={newTask.symbol || ''}
                  onChange={(e) => setNewTask({ ...newTask, symbol: e.target.value })}
                  placeholder="留空则更新所有股票"
                  className="w-full border dark:border-gray-600 rounded px-3 py-2 dark:bg-gray-800 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all duration-200"
                  id="task-symbol"
                  name="task-symbol"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">如果留空，将更新所有股票数据</p>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" htmlFor="task-interval">
                  执行间隔 (秒)
                </label>
                <div className="flex items-center space-x-2">
                  <input
                    type="number"
                    value={newTask.interval}
                    onChange={(e) => setNewTask({ ...newTask, interval: parseInt(e.target.value) })}
                    min="60"
                    className="w-full border dark:border-gray-600 rounded px-3 py-2 dark:bg-gray-800 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all duration-200"
                    id="task-interval"
                    name="task-interval"
                  />
                  <span className="text-gray-500 dark:text-gray-400 whitespace-nowrap">{formatInterval(newTask.interval)}</span>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">建议至少设置为60秒</p>
              </div>
              
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="is_enabled"
                  checked={newTask.is_enabled}
                  onChange={(e) => setNewTask({ ...newTask, is_enabled: e.target.checked })}
                  className="h-4 w-4 text-blue-600 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700 focus:ring-blue-500"
                />
                <label htmlFor="is_enabled" className="ml-2 block text-sm text-gray-700 dark:text-gray-300">
                  立即启用
                </label>
              </div>
              
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={loading}
                  className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:bg-green-300 dark:disabled:bg-green-800 transition-colors duration-200 focus:ring-2 focus:ring-green-300 focus:ring-offset-2 dark:focus:ring-offset-gray-800 flex items-center"
                  aria-label="创建新任务"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                  {loading ? '创建中...' : '创建任务'}
                </button>
              </div>
            </div>
          </form>
        </div>
      )}
      
      {/* 任务列表 */}
      {loading && tasks.length === 0 ? (
        <div className="flex justify-center my-8">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 dark:border-blue-400"></div>
        </div>
      ) : tasks.length > 0 ? (
        <div className="overflow-x-auto rounded border border-gray-200 dark:border-gray-700">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  描述
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  间隔
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  下次运行
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  状态
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {tasks.map((task) => (
                <tr key={task.task_id} className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors duration-150">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900 dark:text-white">{task.description}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">ID: {task.task_id}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900 dark:text-white">{formatInterval(task.interval)}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900 dark:text-white">
                      {new Date(task.next_run).toLocaleString()}
                    </div>
                    {task.last_run && (
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        上次: {new Date(task.last_run).toLocaleString()}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      task.is_enabled 
                        ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' 
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                    }`}>
                      {task.is_enabled ? '已启用' : '已禁用'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <div className="flex space-x-3">
                      <button
                        onClick={() => handleToggleTaskStatus(task.task_id, task.is_enabled)}
                        className={`${
                          task.is_enabled 
                            ? 'text-yellow-600 hover:text-yellow-900 dark:text-yellow-500 dark:hover:text-yellow-400' 
                            : 'text-green-600 hover:text-green-900 dark:text-green-500 dark:hover:text-green-400'
                        } transition-colors duration-150 focus:outline-none focus:underline`}
                        aria-label={task.is_enabled ? '禁用任务' : '启用任务'}
                      >
                        {task.is_enabled ? '禁用' : '启用'}
                      </button>
                      <button
                        onClick={() => handleRunTaskNow(task.task_id)}
                        className="text-blue-600 hover:text-blue-900 dark:text-blue-500 dark:hover:text-blue-400 transition-colors duration-150 focus:outline-none focus:underline"
                        aria-label="立即运行任务"
                      >
                        立即运行
                      </button>
                      <button
                        onClick={() => handleDeleteTask(task.task_id)}
                        className="text-red-600 hover:text-red-900 dark:text-red-500 dark:hover:text-red-400 transition-colors duration-150 focus:outline-none focus:underline"
                        aria-label="删除任务"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-8 bg-gray-50 dark:bg-gray-700 rounded border border-gray-200 dark:border-gray-600">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mx-auto text-gray-400 dark:text-gray-500 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-gray-500 dark:text-gray-400">暂无定时任务</p>
          <button
            onClick={() => setShowCreateForm(true)}
            className="mt-3 text-blue-500 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors duration-150"
          >
            创建第一个任务
          </button>
        </div>
      )}
      
      {/* 刷新按钮 */}
      {tasks.length > 0 && (
        <div className="mt-4 flex justify-center">
          <button
            onClick={loadTasks}
            disabled={loading}
            className="text-blue-500 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center transition-colors duration-150 focus:outline-none focus:underline"
            aria-label="刷新任务列表"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" />
            </svg>
            {loading ? '加载中...' : '刷新任务列表'}
          </button>
        </div>
      )}
    </div>
  );
};

export default TaskManager; 