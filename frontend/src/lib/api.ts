import axios from 'axios';
import { StockInfo, StockPriceHistory, AIAnalysis, ApiResponse, CacheStats, TaskInfo, TaskCreate, TaskUpdate } from '../types';
import { SavedStock, LoginForm, RegisterForm, AuthResponse, User } from '../types/user';
import { indexedDBCache } from './indexedDBCache';

// API基础URL，优先使用环境变量，否则使用相对路径
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

// 开发环境下输出API基础URL，帮助调试
if (process.env.NODE_ENV !== 'production') {
  console.log('API Base URL:', API_BASE_URL);
}

// 创建axios实例
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 添加认证令牌
api.interceptors.request.use(
  (config) => {
    // 从localStorage获取令牌
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    
    // 如果有令牌，添加到请求头
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // 如果数据是 FormData 类型，修改 Content-Type
    if (config.data instanceof FormData || config.data instanceof URLSearchParams) {
      config.headers['Content-Type'] = 'application/x-www-form-urlencoded';
    }
    
    // 开发环境下输出请求信息，帮助调试
    if (process.env.NODE_ENV !== 'production') {
      console.log(`API Request: ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
      if (token) {
        console.log('Using token:', token);
      }
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器 - 处理认证错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // 输出错误信息，帮助调试
    console.error('API Error:', error.message);
    if (error.response) {
      console.error('Status:', error.response.status);
      console.error('Data:', error.response.data);
    }
    
    // 如果是401错误（未授权），可以重定向到登录页面
    if (error.response && error.response.status === 401) {
      // 清除本地存储的令牌
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
        // 可以在这里添加重定向到登录页面的逻辑
        // window.location.href = '/login';
      }
    }
    
    // 对于404错误，我们应该返回一个特定的错误对象，而不是直接拒绝Promise
    if (error.response && error.response.status === 404) {
      return Promise.resolve({
        data: {
          success: false,
          error: '请求的资源不存在',
          isNotFound: true
        }
      });
    }
    
    return Promise.reject(error);
  }
);

// 初始化IndexedDB缓存
if (typeof window !== 'undefined') {
  indexedDBCache.init().catch(err => {
    console.error('Failed to initialize IndexedDB cache:', err);
  });
}

// 搜索股票
export async function searchStocks(query: string, forceRefresh: boolean = false): Promise<ApiResponse<StockInfo[]>> {
  const cacheKey = `searchStocks:${query}`;
  
  // 如果不是强制刷新，尝试从缓存获取
  if (!forceRefresh) {
    const cachedResult = await indexedDBCache.get<ApiResponse<StockInfo[]>>(cacheKey);
    if (cachedResult) {
      return cachedResult;
    }
  }
  
  try {
    const response = await api.get<{success: boolean, data?: StockInfo[], error?: string}>(`/stocks/search?q=${encodeURIComponent(query)}`);
    
    // 直接返回后端的响应格式
    if (response.data) {
      // 缓存结果（1小时）
      await indexedDBCache.set(cacheKey, response.data, 3600 * 1000);
      return response.data;
    }
    
    // 如果响应不符合预期格式，进行转换
    const result = {
      success: true,
      data: response.data as any
    };
    
    // 缓存结果（1小时）
    await indexedDBCache.set(cacheKey, result, 3600 * 1000);
    
    return result;
  } catch (error) {
    console.error('Error searching stocks:', error);
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      return {
        success: false,
        error: '请先登录后再进行搜索',
      };
    }
    return {
      success: false,
      error: '搜索股票时出错',
    };
  }
}

// 获取股票详细信息
export async function getStockInfo(symbol: string, forceRefresh: boolean = false): Promise<ApiResponse<StockInfo>> {
  const cacheKey = `getStockInfo:${symbol}`;
  
  // 如果不是强制刷新，尝试从缓存获取
  if (!forceRefresh) {
    const cachedResult = await indexedDBCache.get<ApiResponse<StockInfo>>(cacheKey);
    if (cachedResult) {
      return cachedResult;
    }
  }
  
  try {
    const response = await api.get<{success: boolean, data?: StockInfo, error?: string}>(`/stocks/${encodeURIComponent(symbol)}`);
    
    // 直接返回后端的响应格式
    if (response.data && 'success' in response.data) {
      // 缓存结果（1小时）
      await indexedDBCache.set(cacheKey, response.data, 3600 * 1000);
      return response.data;
    }
    
    // 如果响应不符合预期格式，进行转换
    const result = {
      success: true,
      data: response.data as any
    };
    
    // 缓存结果（1小时）
    await indexedDBCache.set(cacheKey, result, 3600 * 1000);
    
    return result;
  } catch (error) {
    console.error('Error getting stock info:', error);
    return {
      success: false,
      error: '获取股票信息时出错',
    };
  }
}

// 获取股票历史价格数据
export async function getStockPriceHistory(
  symbol: string,
  interval: 'daily' | 'weekly' | 'monthly' = 'daily',
  range: '1m' | '3m' | '6m' | '1y' | '5y' = '1m',
  forceRefresh: boolean = false
): Promise<ApiResponse<StockPriceHistory>> {
  const cacheKey = `getStockPriceHistory:${symbol}:${interval}:${range}`;
  
  // 如果不是强制刷新，尝试从缓存获取
  if (!forceRefresh) {
    const cachedResult = await indexedDBCache.get<ApiResponse<StockPriceHistory>>(cacheKey);
    if (cachedResult) {
      return cachedResult;
    }
  }
  
  try {
    const response = await api.get<{success: boolean, data?: StockPriceHistory, error?: string}>(
      `/stocks/${encodeURIComponent(symbol)}/history?interval=${interval}&range=${range}`
    );
    
    // 直接返回后端的响应格式
    if (response.data && 'success' in response.data) {
      // 缓存结果（1小时）
      await indexedDBCache.set(cacheKey, response.data, 3600 * 1000);
      return response.data;
    }
    
    // 如果响应不符合预期格式，进行转换
    const result = {
      success: true,
      data: response.data as any
    };
    
    // 缓存结果（1小时）
    await indexedDBCache.set(cacheKey, result, 3600 * 1000);
    
    return result;
  } catch (error) {
    console.error('Error getting stock price history:', error);
    return {
      success: false,
      error: '获取股票价格历史数据时出错',
    };
  }
}

// 获取AI分析
export async function getAIAnalysis(
  symbol: string, 
  forceRefresh: boolean = false,
  analysisType: 'rule' | 'ml' | 'llm' = 'llm'
): Promise<ApiResponse<AIAnalysis>> {
  const cacheKey = `getAIAnalysis:${symbol}:${analysisType}`;
  
  // 如果不是强制刷新，尝试从缓存获取
  if (!forceRefresh) {
    const cachedResult = await indexedDBCache.get<ApiResponse<AIAnalysis>>(cacheKey);
    if (cachedResult) {
      return cachedResult;
    }
  }
  
  try {
    const response = await api.get<{success: boolean, data?: AIAnalysis, error?: string}>(
      `/ai/analyze?symbol=${encodeURIComponent(symbol)}&analysis_type=${analysisType}`
    );
    
    // 直接返回后端的响应格式
    if (response.data && 'success' in response.data) {
      // 缓存结果（1小时）
      await indexedDBCache.set(cacheKey, response.data, 3600 * 1000);
      return response.data;
    }
    
    // 如果响应不符合预期格式，进行转换
    const result = {
      success: true,
      data: response.data as any
    };
    
    // 缓存结果（1小时）
    await indexedDBCache.set(cacheKey, result, 3600 * 1000);
    
    return result;
  } catch (error) {
    console.error('Error getting AI analysis:', error);
    // 如果是429错误，返回错误信息
    if (axios.isAxiosError(error) && error.response?.status === 429) {
      return {
        success: false,
        error: '请求频率过高，请稍后再试'
      };
    } 
    return {
      success: false,
      error: '获取AI分析时出错',
    };
  }
}

// 获取AI时间序列分析
export async function getAITimeSeriesAnalysis(
  symbol: string,
  interval: 'daily' | 'weekly' | 'monthly' = 'daily',
  range: '1m' | '3m' | '6m' | '1y' | '5y' = '1m',
  forceRefresh: boolean = false,
  analysisType: 'rule' | 'ml' | 'llm' = 'llm'
): Promise<ApiResponse<any>> {
  try {
    // 缓存键
    const cacheKey = `ai_time_series_${symbol}_${interval}_${range}_${analysisType}`;
    
    // 如果不强制刷新，尝试从缓存获取
    if (!forceRefresh) {
      const cachedData = await indexedDBCache.get<ApiResponse<any>>(cacheKey);
      if (cachedData) {
        return {
          success: true,
          data: cachedData,
          message: "从缓存获取AI分时分析"
        };
      }
    }
    
    // 构建请求参数
    const params = new URLSearchParams();
    params.append('symbol', symbol);
    params.append('interval', interval);
    params.append('range', range);
    if (analysisType) params.append('analysis_type', analysisType);
    
    // 发送请求
    const response = await api.get(`/ai/time-series?${params.toString()}`);
    
    // 如果请求成功，缓存结果
    if (response.data.success && response.data.data) {
      await indexedDBCache.set(cacheKey, response.data.data, 1800 * 1000); // 缓存30分钟
    }
    
    return response.data;
  } catch (error) {
    console.error('获取AI分时分析失败:', error);
    // 如果是429错误，返回错误信息
    if (axios.isAxiosError(error) && error.response?.status === 429) {
      return {
        success: false,
        error: '请求频率过高，请稍后再试'
      };
    }

    return {
      success: false,
      error: '获取AI分时分析失败'
    };
  }
}

// 用户认证相关 API
export async function login(data: LoginForm): Promise<ApiResponse<AuthResponse>> {
  try {
    const formData = new URLSearchParams();
    formData.append('username', data.username);
    formData.append('password', data.password);
    
    const response = await api.post<AuthResponse>('/user/token', formData.toString(), {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    });

    return {
      success: true,
      data: response.data
    };
  } catch (error: any) {
    console.error('Error logging in:', error);
    return {
      success: false,
      error: error.response?.data?.error || '登录失败'
    };
  }
}

export async function changePassword(oldPassword: string, newPassword: string): Promise<ApiResponse<any>> {
  try {
    const response = await api.post('/user/change-password', {
      old_password: oldPassword,
      new_password: newPassword
    });

    return {
      success: true,
      data: response.data
    };
  } catch (error: any) {
    console.error('Error changing password:', error);
    return {
      success: false,
      error: error.response?.data?.error || '修改密码失败'
    };
  }
}

export async function logout(): Promise<ApiResponse<any>> {
  try {
    const response = await api.post<ApiResponse<any>>('/user/logout');
    
    // 清除本地存储的认证信息
    localStorage.removeItem('auth_token');
    
    // 清除缓存的用户相关数据
    await clearCachePattern('user:');
    await clearCachePattern('saved-stocks:');
    
    return response.data;
  } catch (error: any) {
    console.error('Error logging out:', error);
    // 即使请求失败，也要清除本地存储
    localStorage.removeItem('auth_token');
    return {
      success: false,
      error: error.response?.data?.error || '退出登录失败'
    };
  }
}

export async function register(data: RegisterForm): Promise<ApiResponse<AuthResponse>> {
  try {
    const response = await api.post<ApiResponse<AuthResponse>>('/user/register', data);
    return response.data;
  } catch (error: any) {
    console.error('Error registering:', error);
    return {
      success: false,
      error: error.response?.data?.error || '注册失败'
    };
  }
}

export async function getUserInfo(): Promise<ApiResponse<User>> {
  try {
    const response = await api.get<ApiResponse<User>>('/user/me');
    return response.data;
  } catch (error: any) {
    console.error('Error fetching user info:', error);
    return {
      success: false,
      error: error.response?.data?.error || '获取用户信息失败'
    };
  }
}

export async function checkUsage(): Promise<ApiResponse<any>> {
  try {
    const response = await api.get<ApiResponse<any>>('/user/check-usage');
    return response.data;
  } catch (error: any) {
    console.error('Error checking usage:', error);
    return {
      success: false,
      error: error.response?.data?.error || '检查使用情况失败'
    };
  }
}

// 股票收藏相关 API
export async function getSavedStocks(): Promise<ApiResponse<SavedStock[]>> {
  try {
    const response = await api.get<ApiResponse<SavedStock[]>>('/user/saved-stocks');
    return response.data;
  } catch (error: any) {
    console.error('Error getting saved stocks:', error);
    return {
      success: false,
      error: error.response?.data?.error || '获取收藏股票失败'
    };
  }
}

export async function saveStock(symbol: string, notes?: string): Promise<ApiResponse<SavedStock>> {
  try {
    const response = await api.post<ApiResponse<SavedStock>>('/user/saved-stocks', { symbol, notes });
    return response.data;
  } catch (error: any) {
    console.error('Error saving stock:', error);
    return {
      success: false,
      error: error.response?.data?.error || '收藏股票失败'
    };
  }
}

export async function deleteSavedStock(symbol: string): Promise<ApiResponse<void>> {
  try {
    const response = await api.delete<ApiResponse<void>>(`/user/saved-stocks/${symbol}`);
    return response.data;
  } catch (error: any) {
    console.error('Error deleting saved stock:', error);
    return {
      success: false,
      error: error.response?.data?.error || '取消收藏失败'
    };
  }
}

// 更新特定股票数据
export async function updateStockData(symbol: string): Promise<ApiResponse<any>> {
  try {
    const response = await api.post<{success: boolean, data?: {message: string}, error?: string}>(`/stocks/${symbol}/update`);
    return response.data;
  } catch (error) {
    console.error('Error updating stock data:', error);
    return {
      success: false,
      error: '更新股票数据时出错',
    };
  }
}

// 更新所有股票数据
export async function updateAllStocks(): Promise<ApiResponse<any>> {
  try {
    const response = await api.post<{success: boolean, data?: {message: string}, error?: string}>('/stocks/update-all');
    return response.data;
  } catch (error) {
    console.error('Error updating all stocks:', error);
    return {
      success: false,
      error: '更新所有股票数据时出错',
    };
  }
}

// 获取缓存统计信息
export async function getCacheStats(): Promise<ApiResponse<CacheStats>> {
  try {
    const stats = await indexedDBCache.getStats();
    return {
      success: true,
      data: {
        total_items: stats.totalItems,
        active_items: stats.activeItems,
        expired_items: stats.expiredItems,
        cache_keys: stats.cacheKeys
      }
    };
  } catch (error) {
    console.error('Error getting cache stats:', error);
    return {
      success: false,
      error: '获取缓存统计信息时出错',
    };
  }
}

// 清空缓存
export async function clearCache(): Promise<ApiResponse<any>> {
  try {
    await indexedDBCache.clear();
    return {
      success: true,
      data: { message: '缓存已清空' }
    };
  } catch (error) {
    console.error('Error clearing cache:', error);
    return {
      success: false,
      error: '清空缓存时出错',
    };
  }
}

// 清除匹配模式的缓存
export async function clearCachePattern(pattern: string): Promise<ApiResponse<any>> {
  try {
    const count = await indexedDBCache.clearPattern(pattern);
    return {
      success: true,
      data: { message: `已清除 ${count} 个缓存项` }
    };
  } catch (error) {
    console.error('Error clearing cache pattern:', error);
    return {
      success: false,
      error: '清除缓存模式时出错',
    };
  }
}

// 清理过期缓存
export async function cleanupCache(): Promise<ApiResponse<any>> {
  try {
    const count = await indexedDBCache.cleanup();
    return {
      success: true,
      data: { message: `已清理 ${count} 个过期缓存项` }
    };
  } catch (error) {
    console.error('Error cleaning up cache:', error);
    return {
      success: false,
      error: '清理过期缓存时出错',
    };
  }
}

// 获取所有定时任务
export async function getAllTasks(): Promise<ApiResponse<TaskInfo[]>> {
  try {
    const response = await api.get<{success: boolean, data?: TaskInfo[], error?: string}>('/tasks');
    return response.data;
  } catch (error) {
    console.error('Error getting all tasks:', error);
    return {
      success: false,
      error: '获取所有定时任务时出错',
    };
  }
}

// 获取特定定时任务
export async function getTask(taskId: string): Promise<ApiResponse<TaskInfo>> {
  try {
    const response = await api.get<{success: boolean, data?: TaskInfo, error?: string}>(`/tasks/${taskId}`);
    return response.data;
  } catch (error) {
    console.error('Error getting task:', error);
    return {
      success: false,
      error: '获取定时任务时出错',
    };
  }
}

// 创建定时任务
export async function createTask(task: TaskCreate): Promise<ApiResponse<TaskInfo>> {
  try {
    const response = await api.post<{success: boolean, data?: TaskInfo, error?: string}>('/tasks', task);
    return response.data;
  } catch (error) {
    console.error('Error creating task:', error);
    return {
      success: false,
      error: '创建定时任务时出错',
    };
  }
}

// 更新定时任务
export async function updateTask(taskId: string, task: TaskUpdate): Promise<ApiResponse<TaskInfo>> {
  try {
    const response = await api.put<{success: boolean, data?: TaskInfo, error?: string}>(`/tasks/${taskId}`, task);
    return response.data;
  } catch (error) {
    console.error('Error updating task:', error);
    return {
      success: false,
      error: '更新定时任务时出错',
    };
  }
}

// 删除定时任务
export async function deleteTask(taskId: string): Promise<ApiResponse<any>> {
  try {
    const response = await api.delete<{success: boolean, data?: {message: string}, error?: string}>(`/tasks/${taskId}`);
    return response.data;
  } catch (error) {
    console.error('Error deleting task:', error);
    return {
      success: false,
      error: '删除定时任务时出错',
    };
  }
}

// 立即运行定时任务
export async function runTaskNow(taskId: string): Promise<ApiResponse<any>> {
  try {
    const response = await api.post<{success: boolean, data?: {message: string}, error?: string}>(`/tasks/${taskId}/run`);
    return response.data;
  } catch (error) {
    console.error('Error running task:', error);
    return {
      success: false,
      error: '运行定时任务时出错',
    };
  }
}

/**
 * 获取股票分时数据
 * @param symbol 股票代码
 * @param forceRefresh 是否强制刷新缓存
 * @returns 分时数据响应
 */
export async function getStockIntraday(
  symbol: string,
  forceRefresh: boolean = false
): Promise<ApiResponse<any>> {
  const cacheKey = `getStockIntraday:${symbol}`;
  
  // 如果不是强制刷新，尝试从缓存获取
  if (!forceRefresh) {
    const cachedResult = await indexedDBCache.get<ApiResponse<any>>(cacheKey);
    if (cachedResult) {
      return cachedResult;
    }
  }
  
  try {
    const response = await api.get<{success: boolean, data?: any, error?: string}>(
      `/stocks/${encodeURIComponent(symbol)}/intraday`
    );
    
    // 直接返回后端的响应格式
    if (response.data && 'success' in response.data) {
      // 缓存结果（5分钟）
      await indexedDBCache.set(cacheKey, response.data, 300 * 1000);
      return response.data;
    }
    
    // 如果响应不符合预期格式，进行转换
    const result = {
      success: true,
      data: response.data as any
    };
    
    // 缓存结果（5分钟）
    await indexedDBCache.set(cacheKey, result, 300 * 1000);
    
    return result;
  } catch (error) {
    console.error('获取分时数据出错:', error);
    return {
      success: false,
      error: '获取分时数据时出错',
    };
  }
}

/**
 * 获取AI分时分析
 * @param symbol 股票代码
 * @param forceRefresh 是否强制刷新缓存
 * @param analysisType 分析类型：规则、机器学习或LLM
 * @returns AI分时分析响应
 */
export async function getAIIntradayAnalysis(
  symbol: string,
  forceRefresh: boolean = false,
  analysisType: 'rule' | 'ml' | 'llm' = 'llm'
): Promise<ApiResponse<any>> {
  const cacheKey = `getAIIntradayAnalysis:${symbol}:${analysisType}`;
  
  // 如果不是强制刷新，尝试从缓存获取
  if (!forceRefresh) {
    const cachedResult = await indexedDBCache.get<ApiResponse<any>>(cacheKey);
    if (cachedResult) {
      return cachedResult;
    }
  }
  
  try {
    const params = new URLSearchParams();
    params.append('analysis_type', analysisType);
    
    const response = await api.get<{success: boolean, data?: any, error?: string}>(
      `/ai/intraday-analysis/${encodeURIComponent(symbol)}?${params.toString()}`
    );
    
    // 直接返回后端的响应格式
    if (response.data && 'success' in response.data) {
      // 缓存结果（5分钟）
      await indexedDBCache.set(cacheKey, response.data, 300 * 1000);
      return response.data;
    }
    
    // 如果响应不符合预期格式，进行转换
    const result = {
      success: true,
      data: response.data as any
    };
    
    // 缓存结果（5分钟）
    await indexedDBCache.set(cacheKey, result, 300 * 1000);
    
    return result;
  } catch (error) {
    console.error('获取AI分时分析出错:', error);
    // 如果是429错误，返回错误信息
    if (axios.isAxiosError(error) && error.response?.status === 429) {
      return {
        success: false,
        error: '请求频率过高，请稍后再试'
      };  
    } 
    return {
      success: false,
      error: '获取AI分时分析时出错',
    };
  }
}

/**
 * 创建异步AI分析任务
 * @param symbol 股票代码
 * @param taskType 任务类型
 * @param options 分析选项
 * @returns 任务信息
 */
export async function createAsyncAITask(
  symbol: string,
  taskType: 'stock_analysis' | 'time_series' | 'intraday',
  options: {
    analysis_type?: 'rule' | 'ml' | 'llm';
    data_source?: string;
    interval?: string;
    range?: string;
  } = {}
): Promise<ApiResponse<{task_id: string, status: string, message: string}>> {
  try {
    const payload = {
      task_type: taskType,
      symbol,
      analysis_type: options.analysis_type || 'llm',
      data_source: options.data_source,
      interval: options.interval,
      range: options.range
    };
    
    const response = await api.post<{success: boolean, data?: any, error?: string}>(
      `/async/ai/analyze`,
      payload
    );
    
    return response.data;
  } catch (error) {
    console.error('Error creating async AI task:', error);

    if (axios.isAxiosError(error) && error.response?.status === 429) {
      return {
        success: false,
        error: '请求频率过高，请稍后再试'
      };
    } 

    return {
      success: false,
      error: '创建异步分析任务时出错',
    };
  }
}

/**
 * 获取异步任务状态
 * @param taskId 任务ID
 * @returns 任务状态和结果
 */
export async function getAsyncTaskStatus(
  taskId: string
): Promise<ApiResponse<{
  task_id: string,
  status: string,
  status_display: string,
  message: string,
  result?: any,
  error?: string
}>> {
  try {
    const response = await api.get<{success: boolean, data?: any, error?: string}>(
      `/async/ai/task/${taskId}`
    );
    
    return response.data;
  } catch (error) {
    console.error('Error checking task status:', error);
    return {
      success: false,
      error: '获取任务状态时出错',
    };
  }
}

/**
 * 取消异步任务
 * @param taskId 任务ID
 * @returns 操作结果
 */
export async function cancelAsyncTask(
  taskId: string
): Promise<ApiResponse<{message: string}>> {
  try {
    const response = await api.delete<{success: boolean, data?: any, error?: string}>(
      `/async/ai/task/${taskId}`
    );
    
    return response.data;
  } catch (error) {
    console.error('Error canceling task:', error);
    return {
      success: false,
      error: '取消任务时出错',
    };
  }
}

// 通用 HTTP 请求方法
export async function get<T>(url: string): Promise<T> {
  try {
    const response = await api.get<T>(url);
    if (process.env.NODE_ENV !== 'production') {
      console.log(`API Response (GET ${url}):`, response.data);
    }
    return response.data;
  } catch (error: any) {
    console.error(`API Error (GET ${url}):`, error);
    throw error;
  }
}

export async function post<T>(url: string, data?: any): Promise<T> {
  try {
    const response = await api.post<T>(url, data);
    if (process.env.NODE_ENV !== 'production') {
      console.log(`API Response (POST ${url}):`, response.data);
    }
    return response.data;
  } catch (error: any) {
    console.error(`API Error (POST ${url}):`, error);
    throw error;
  }
}

export async function put<T>(url: string, data: any): Promise<T> {
  try {
    const response = await api.put<T>(url, data);
    if (process.env.NODE_ENV !== 'production') {
      console.log(`API Response (PUT ${url}):`, response.data);
    }
    return response.data;
  } catch (error: any) {
    console.error(`API Error (PUT ${url}):`, error);
    throw error;
  }
}

export async function del<T>(url: string): Promise<T> {
  try {
    const response = await api.delete<T>(url);
    if (process.env.NODE_ENV !== 'production') {
      console.log(`API Response (DELETE ${url}):`, response.data);
    }
    return response.data;
  } catch (error: any) {
    console.error(`API Error (DELETE ${url}):`, error);
    throw error;
  }
}

/**
 * 与智能体对话
 * @param data 请求数据
 * @returns 智能体回复
 */
export async function chatWithAgent(data: {
  content: string;
  session_id?: string;
  enable_web_search?: boolean;
  stream?: boolean;
  model?: string;
}): Promise<ApiResponse<any>> {
  try {
    const response = await api.post<{success: boolean, data?: any, error?: string}>(
      '/agent/chat',
      data
    );
    
    return response.data;
  } catch (error) {
    console.error('与智能体对话出错:', error);
    if (axios.isAxiosError(error)) {
      const backendError = (error.response?.data as any)?.error;
      const statusInfo = error.response ? `${error.response.status} ${error.response.statusText}` : '';
      const message = backendError || error.message || '未知错误';
      return {
        success: false,
        error: `与智能体通信时出错: ${message}${statusInfo ? ` (${statusInfo})` : ''}`,
      };
    }
    return {
      success: false,
      error: `与智能体通信时出错: ${(error as any)?.message || String(error)}`,
    };
  }
}

/**
 * 与智能体流式对话
 * @param data 请求数据
 * @param onMessage 消息回调函数
 * @returns Promise<void>
 */
export async function chatWithAgentStream(
  data: {
    content: string;
    session_id?: string;
    enable_web_search?: boolean;
    model?: string;
  },
  onMessage: (message: any) => void
): Promise<void> {
  try {
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    
    // 保持“浏览器直连后端 + 代理超时放宽 + 周期性 chunk”，Next 不会成为瓶颈
    const response = await fetch(`${API_BASE_URL}/agent/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      },
      body: JSON.stringify({
        ...data,
        stream: true
      })
    });

    if (!response.ok) {
      let detail = '';
      try {
        const text = await response.text();
        // 尝试解析后端标准响应
        const json = JSON.parse(text);
        detail = json?.error || text;
      } catch (_) {
        detail = response.statusText || '';
      }
      throw new Error(`HTTP ${response.status} ${response.statusText}${detail ? ` - ${detail}` : ''}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('无法获取响应流');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      
      // 处理完整的JSON行
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // 保留最后一个不完整的行
      
      for (const line of lines) {
        if (line.trim()) {
          try {
            const message = JSON.parse(line);
            onMessage(message);
          } catch (e) {
            console.error('解析流式消息失败:', e, line);
          }
        }
      }
    }
  } catch (error) {
    console.error('流式对话出错:', error);
    onMessage({
      type: 'error',
      error: `与智能体通信时出错: ${(error as any)?.message || String(error)}`
    });
  }
}

/**
 * 获取后端配置的可用模型列表
 */
export async function getAvailableModels(): Promise<ApiResponse<{models: string[], default: string}>> {
  try {
    const response = await api.get<{success: boolean, data?: any, error?: string}>('/agent/models');
    return response.data as any;
  } catch (error) {
    return {
      success: false,
      error: '获取模型列表失败'
    } as any;
  }
}

/**
 * 获取智能体会话列表
 * @returns 会话列表
 */
export async function getAgentSessions(): Promise<ApiResponse<any>> {
  try {
    const response = await api.get<{success: boolean, data?: any, error?: string}>(
      '/agent/sessions'
    );
    
    return response.data;
  } catch (error) {
    console.error('获取智能体会话列表出错:', error);
    return {
      success: false,
      error: '获取会话列表时出错',
    };
  }
}

/**
 * 获取特定会话历史
 * @param sessionId 会话ID
 * @returns 会话历史
 */
export async function getAgentSessionHistory(sessionId: string): Promise<ApiResponse<any>> {
  try {
    const response = await api.get<{success: boolean, data?: any, error?: string}>(
      `/agent/sessions/${sessionId}`
    );
    
    return response.data;
  } catch (error) {
    console.error('获取会话历史出错:', error);
    return {
      success: false,
      error: '获取会话历史时出错',
    };
  }
}

/**
 * 删除特定会话
 * @param sessionId 会话ID
 * @returns 删除结果
 */
export async function deleteAgentSession(sessionId: string): Promise<ApiResponse<any>> {
  try {
    const response = await api.delete<{success: boolean, data?: any, error?: string}>(
      `/agent/sessions/${sessionId}`
    );
    
    return response.data;
  } catch (error) {
    console.error('删除会话出错:', error);
    return {
      success: false,
      error: '删除会话时出错',
    };
  }
}

/**
 * 获取智能体工具列表
 * @returns 工具列表
 */
export async function getAgentTools(): Promise<ApiResponse<any>> {
  try {
    const response = await api.get<{success: boolean, data?: any, error?: string}>(
      '/agent/tools'
    );
    
    return response.data;
  } catch (error) {
    console.error('获取智能体工具列表出错:', error);
    return {
      success: false,
      error: '获取工具列表时出错',
    };
  }
}

/**
 * 执行Web搜索
 * @param query 搜索查询
 * @param limit 结果数量限制
 * @returns 搜索结果
 */
export const searchWeb = async (query: string, limit: number = 5) => {
  try {
    const params = new URLSearchParams({
      query,
      limit: limit.toString()
    });
    
    const response = await api.get(`/search/web?${params.toString()}`);
    return response.data;
  } catch (error) {
    console.error("Web搜索出错:", error);
    throw error;
  }
};

/**
 * 执行智能体工具调用
 * @param toolCalls 工具调用列表
 * @returns 工具执行结果
 */
export async function executeAgentTool(toolCalls: any[]): Promise<ApiResponse<any>> {
  try {
    // 设置更长的超时时间，特别是对于搜索请求
    const response = await api.post<{success: boolean, data?: any, error?: string}>(
      '/agent/agent-tool',
      { tool_calls: toolCalls }
    );
    
    return response.data;
  } catch (error) {
    console.error('执行智能体工具调用出错:', error);
    return {
      success: false,
      error: '执行工具调用时出错',
    };
  }
} 