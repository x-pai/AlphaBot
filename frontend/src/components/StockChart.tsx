import React, { useState, useEffect, useCallback } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Legend,
  Area,
  AreaChart,
  Bar,
  BarChart,
  ComposedChart,
  ReferenceLine,
} from 'recharts';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { getStockPriceHistory, getAITimeSeriesAnalysis, getStockIntraday, getAIIntradayAnalysis } from '../lib/api';
import { StockPriceHistory } from '../types';
import { RefreshCw, TrendingUp, BarChart2, Activity, AlertCircle, Brain, Clock } from 'lucide-react';
import { Skeleton } from './ui/skeleton';
import { Badge } from './ui/badge';

interface StockChartProps {
  symbol: string;
}

type TimeRange = '1m' | '3m' | '6m' | '1y' | '5y';
type Interval = 'daily' | 'weekly' | 'monthly' | 'intraday';
type ChartType = 'price-volume' | 'intraday';
type AnalysisType = 'rule' | 'ml' | 'llm';

// 图表数据类型
interface ChartDataPoint {
  date: string;
  time?: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
  predicted?: number;
}

export default function StockChart({ symbol }: StockChartProps) {
  const [priceHistory, setPriceHistory] = useState<StockPriceHistory | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>('1m');
  const [interval, setInterval] = useState<Interval>('daily');
  const [chartType, setChartType] = useState<ChartType>('price-volume');
  const [showAIPrediction, setShowAIPrediction] = useState(true);
  const [aiPredictions, setAIPredictions] = useState<Record<AnalysisType, any>>({
    rule: null,
    ml: null,
    llm: null
  });
  const [aiLoading, setAILoading] = useState(false);
  const [aiError, setAIError] = useState<string | null>(null);
  const [analysisType, setAnalysisType] = useState<AnalysisType>('llm');
  const [intradayData, setIntradayData] = useState<ChartDataPoint[]>([]);
  const [intradayLoading, setIntradayLoading] = useState(false);
  const [intradayError, setIntradayError] = useState<string | null>(null);
  const [intradayAIPredictions, setIntradayAIPredictions] = useState<Record<AnalysisType, any>>({
    rule: null,
    ml: null,
    llm: null
  });
  const [intradayAILoading, setIntradayAILoading] = useState(false);
  const [intradayAIError, setIntradayAIError] = useState<string | null>(null);

  // 加载股票历史价格数据
  const loadPriceHistory = useCallback(async (forceRefresh: boolean = false) => {
    if (!symbol) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await getStockPriceHistory(symbol, interval === 'intraday' ? 'daily' : interval, timeRange, forceRefresh);
      if (response.success && response.data) {
        setPriceHistory(response.data);
      } else {
        setError(response.error || '加载价格历史数据失败');
      }
    } catch (err) {
      console.error('加载价格历史数据出错:', err);
      setError('加载价格历史数据时出错');
    } finally {
      setLoading(false);
    }
  }, [symbol, interval, timeRange]);

  // 加载分时数据
  const loadIntradayData = useCallback(async (forceRefresh: boolean = false) => {
    if (!symbol) return;
    
    setIntradayLoading(true);
    setIntradayError(null);
    
    try {
      // 调用API获取分时数据
      const response = await getStockIntraday(symbol, forceRefresh);
      if (response.success && response.data && Array.isArray(response.data.data)) {
        // 确保response.data.data是数组
        const chartData: ChartDataPoint[] = response.data.data.map((point: any) => ({
          date: new Date().toLocaleDateString(),
          time: point.time,
          close: point.price,
          volume: point.volume
        }));
        setIntradayData(chartData);
      } else {
        // 如果API调用失败或数据结构不符合预期，使用模拟数据
        console.warn('无法获取真实分时数据或数据结构不正确，使用模拟数据');
        const mockIntradayData = generateMockIntradayData();
        setIntradayData(mockIntradayData);
      }
    } catch (err) {
      console.error('加载分时数据出错:', err);
      setIntradayError('加载分时数据时出错');
    } finally {
      setIntradayLoading(false);
    }
  }, [symbol]);

  // 生成模拟分时数据
  const generateMockIntradayData = () => {
    const data: ChartDataPoint[] = [];
    const today = new Date();
    const basePrice = 100 + Math.random() * 50;
    let currentPrice = basePrice;
    
    // 生成9:30到15:00的分时数据
    for (let hour = 9; hour <= 15; hour++) {
      const startMinute = hour === 9 ? 30 : 0;
      const endMinute = hour === 15 ? 0 : 59;
      
      for (let minute = startMinute; minute <= endMinute; minute++) {
        // 11:30-13:00是午休时间，跳过
        if ((hour === 11 && minute >= 30) || (hour === 12)) {
          continue;
        }
        
        // 随机价格波动
        const change = (Math.random() - 0.5) * 0.5;
        currentPrice = currentPrice + change;
        
        // 随机成交量
        const volume = Math.floor(Math.random() * 10000) + 1000;
        
        // 格式化时间
        const timeStr = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
        
        data.push({
          date: today.toLocaleDateString(),
          time: timeStr,
          close: parseFloat(currentPrice.toFixed(2)),
          volume: volume
        });
      }
    }
    
    return data;
  };

  // 加载 AI 预测数据
  const loadAIPrediction = useCallback(async (forceRefresh: boolean = false) => {
    if (!symbol) return;
    
    setAILoading(true);
    setAIError(null);
    
    try {
      const response = await getAITimeSeriesAnalysis(
        symbol, 
        interval === 'intraday' ? 'daily' : interval, 
        timeRange, 
        forceRefresh,
        analysisType
      );
      
      if (response.success && response.data) {
        // Update only the current analysis type in the predictions object
        setAIPredictions(prev => ({
          ...prev,
          [analysisType]: response.data
        }));
        setShowAIPrediction(true);
      } else {
        setAIError(response.error || '加载 AI 预测数据失败');
      }
    } catch (err) {
      console.error('加载 AI 预测数据出错:', err);
      setAIError('加载 AI 预测数据时出错');
    } finally {
      setAILoading(false);
    }
  }, [symbol, interval, timeRange, analysisType]);

  // 加载分时AI分析
  const loadIntradayAIAnalysis = useCallback(async (forceRefresh: boolean = false) => {
    if (!symbol) return;
    
    setIntradayAILoading(true);
    setIntradayAIError(null);
    
    try {
      const response = await getAIIntradayAnalysis(symbol, forceRefresh, analysisType);
      if (response.success && response.data) {
        // Update only the current analysis type in the predictions object
        setIntradayAIPredictions(prev => ({
          ...prev,
          [analysisType]: response.data
        }));
        setShowAIPrediction(true);
      } else {
        setIntradayAIError(response.error || '加载分时AI分析失败');
      }
    } catch (err) {
      console.error('加载分时AI分析出错:', err);
      setIntradayAIError('加载分时AI分析时出错');
    } finally {
      setIntradayAILoading(false);
    }
  }, [symbol, analysisType]);

  // 初始加载和参数变化时重新加载
  useEffect(() => {
    if (interval === 'intraday') {
      loadIntradayData();
      setChartType('intraday');
    } else {
      loadPriceHistory();
      setChartType('price-volume');
    }
  }, [loadPriceHistory, loadIntradayData, interval]);

  // 处理刷新
  const handleRefresh = () => {
    if (interval === 'intraday') {
      loadIntradayData(true);
      // 只有当已经有分析数据时才刷新AI分析
      if (intradayAIPredictions[analysisType]) {
        loadIntradayAIAnalysis(true);
      }
    } else {
      loadPriceHistory(true);
      // 只有当已经有分析数据时才刷新AI分析
      if (aiPredictions[analysisType]) {
        loadAIPrediction(true);
      }
    }
  };

  // 处理获取AI分析
  const handleGetAIAnalysis = () => {
    if (interval === 'intraday') {
      loadIntradayAIAnalysis(false);
    } else {
      loadAIPrediction(false);
    }
  };

  // 准备图表数据
  const prepareChartData = () => {
    if (!priceHistory || !priceHistory.data || priceHistory.data.length === 0) {
      return [] as ChartDataPoint[];
    }

    // 基础数据
    const chartData: ChartDataPoint[] = priceHistory.data.map(point => ({
      date: new Date(point.date).toLocaleDateString(),
      open: point.open,
      high: point.high,
      low: point.low,
      close: point.close,
      volume: point.volume,
    }));

    // 如果显示 AI 预测，添加预测数据
    const currentPrediction = aiPredictions[analysisType];
    if (showAIPrediction && currentPrediction && currentPrediction.prediction && currentPrediction.prediction.price_trend) {
      // 获取最后一个日期的索引
      const lastIndex = chartData.length - 1;
      const lastDate = new Date(priceHistory.data[lastIndex].date);
      
      // 添加预测数据
      currentPrediction.prediction.price_trend.forEach((point: any, index: number) => {
        // 计算预测日期（假设是工作日）
        const predictionDate = new Date(lastDate);
        predictionDate.setDate(predictionDate.getDate() + (index + 1));
        
        // 添加到图表数据
        chartData.push({
          date: predictionDate.toLocaleDateString(),
          predicted: point.predicted_price,
        });
      });
    }

    return chartData;
  };

  // 获取支撑位和阻力位
  const getSupportAndResistanceLevels = () => {
    if (!showAIPrediction) {
      return { supportLevels: [], resistanceLevels: [] };
    }
    
    const currentPrediction = interval === 'intraday' 
      ? intradayAIPredictions[analysisType]
      : aiPredictions[analysisType];
    
    if (!currentPrediction || !currentPrediction.prediction) {
      return { supportLevels: [], resistanceLevels: [] };
    }
    
    return {
      supportLevels: currentPrediction.prediction.support_levels || [],
      resistanceLevels: currentPrediction.prediction.resistance_levels || [],
    };
  };

  // 获取图表颜色
  const getChartColors = () => {
    const isDarkMode = document.documentElement.classList.contains('dark');
    
    return {
      price: isDarkMode ? '#4ade80' : '#22c55e',
      volume: isDarkMode ? '#94a3b8' : '#cbd5e1',
      grid: isDarkMode ? '#334155' : '#e2e8f0',
      prediction: '#3b82f6',
      support: '#4ade80',
      resistance: '#f87171',
      intraday: '#3b82f6',
    };
  };

  // 渲染价格-成交量图表
  const renderPriceVolumeChart = () => {
    if (!priceHistory || !priceHistory.data || priceHistory.data.length === 0) {
      return null;
    }

    const chartData = prepareChartData();
    const colors = getChartColors();
    const { supportLevels, resistanceLevels } = getSupportAndResistanceLevels();

    return (
      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
            <XAxis dataKey="date" />
            <YAxis yAxisId="left" domain={['auto', 'auto']} />
            <YAxis yAxisId="right" orientation="right" domain={['auto', 'auto']} />
            <YAxis yAxisId="volume" orientation="right" domain={['auto', 'auto']} hide />
            <RechartsTooltip />
            <Legend />
            
            {/* 价格线 */}
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="close"
              stroke={colors.price}
              name="收盘价"
              dot={false}
              strokeWidth={2}
            />
            
            {/* 成交量柱状图 */}
            <Bar
              yAxisId="volume"
              dataKey="volume"
              fill={colors.volume}
              name="成交量"
              opacity={0.5}
            />
            
            {/* AI 预测线 */}
            {showAIPrediction && (
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="predicted"
                stroke={colors.prediction}
                name="AI预测"
                strokeDasharray="5 5"
                strokeWidth={2}
                dot={{ r: 4 }}
              />
            )}
            
            {/* 支撑位 */}
            {showAIPrediction && supportLevels.map((level: number, index: number) => (
              <ReferenceLine
                key={`support-${index}`}
                y={level}
                yAxisId="left"
                stroke={colors.support}
                strokeDasharray="3 3"
                label={{
                  value: `支撑: ${level.toFixed(2)}`,
                  position: 'insideBottomRight',
                  fill: colors.support,
                }}
              />
            ))}
            
            {/* 阻力位 */}
            {showAIPrediction && resistanceLevels.map((level: number, index: number) => (
              <ReferenceLine
                key={`resistance-${index}`}
                y={level}
                yAxisId="left"
                stroke={colors.resistance}
                strokeDasharray="3 3"
                label={{
                  value: `阻力: ${level.toFixed(2)}`,
                  position: 'insideTopRight',
                  fill: colors.resistance,
                }}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    );
  };

  // 渲染分时图表
  const renderIntradayChart = () => {
    if (intradayData.length === 0) {
      return null;
    }

    const colors = getChartColors();
    
    // 获取支撑位和阻力位
    const supportLevels = showAIPrediction && intradayAIPredictions[analysisType] && intradayAIPredictions[analysisType].support_levels 
      ? intradayAIPredictions[analysisType].support_levels : [];
    const resistanceLevels = showAIPrediction && intradayAIPredictions[analysisType] && intradayAIPredictions[analysisType].resistance_levels 
      ? intradayAIPredictions[analysisType].resistance_levels : [];

    return (
      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={intradayData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
            <XAxis 
              dataKey="time" 
              scale="band"
              tickFormatter={(value) => {
                // 只显示整点和半点
                if (value.endsWith(':00') || value.endsWith(':30')) {
                  return value;
                }
                return '';
              }}
            />
            <YAxis yAxisId="left" domain={['auto', 'auto']} />
            <YAxis yAxisId="right" orientation="right" domain={['auto', 'auto']} />
            <YAxis yAxisId="volume" orientation="right" domain={['auto', 'auto']} hide />
            <RechartsTooltip />
            <Legend />
            
            {/* 分时价格线 */}
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="close"
              stroke={colors.intraday}
              name="价格"
              dot={false}
              strokeWidth={2}
            />
            
            {/* 成交量柱状图 */}
            <Bar
              yAxisId="volume"
              dataKey="volume"
              fill={colors.volume}
              name="成交量"
              opacity={0.5}
            />
            
            {/* 支撑位 */}
            {showAIPrediction && supportLevels.map((level: number, index: number) => (
              <ReferenceLine
                key={`support-${index}`}
                y={level}
                yAxisId="left"
                stroke={colors.support}
                strokeDasharray="3 3"
                label={{
                  value: `支撑: ${level.toFixed(2)}`,
                  position: 'insideBottomRight',
                  fill: colors.support,
                }}
              />
            ))}
            
            {/* 阻力位 */}
            {showAIPrediction && resistanceLevels.map((level: number, index: number) => (
              <ReferenceLine
                key={`resistance-${index}`}
                y={level}
                yAxisId="left"
                stroke={colors.resistance}
                strokeDasharray="3 3"
                label={{
                  value: `阻力: ${level.toFixed(2)}`,
                  position: 'insideTopRight',
                  fill: colors.resistance,
                }}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    );
  };

  // 渲染图表控制按钮
  const renderChartControls = () => {
    return (
      <div className="flex flex-wrap gap-2 mb-4">
        <div className="flex rounded-md overflow-hidden border border-border">
          <Button
            variant={interval === 'intraday' ? 'primary' : 'ghost'}
            size="sm"
            className="rounded-none border-0"
            onClick={() => setInterval('intraday')}
          >
            <Clock className="h-4 w-4 mr-1" />
            分时
          </Button>
          <Button
            variant={interval === 'daily' ? 'primary' : 'ghost'}
            size="sm"
            className="rounded-none border-0"
            onClick={() => setInterval('daily')}
          >
            日K
          </Button>
          <Button
            variant={interval === 'weekly' ? 'primary' : 'ghost'}
            size="sm"
            className="rounded-none border-0"
            onClick={() => setInterval('weekly')}
          >
            周K
          </Button>
          <Button
            variant={interval === 'monthly' ? 'primary' : 'ghost'}
            size="sm"
            className="rounded-none border-0"
            onClick={() => setInterval('monthly')}
          >
            月K
          </Button>
        </div>
        
        {interval !== 'intraday' && (
          <div className="flex rounded-md overflow-hidden border border-border">
            <Button
              variant={timeRange === '1m' ? 'primary' : 'ghost'}
              size="sm"
              className="rounded-none border-0"
              onClick={() => setTimeRange('1m')}
            >
              1月
            </Button>
            <Button
              variant={timeRange === '3m' ? 'primary' : 'ghost'}
              size="sm"
              className="rounded-none border-0"
              onClick={() => setTimeRange('3m')}
            >
              3月
            </Button>
            <Button
              variant={timeRange === '6m' ? 'primary' : 'ghost'}
              size="sm"
              className="rounded-none border-0"
              onClick={() => setTimeRange('6m')}
            >
              6月
            </Button>
            <Button
              variant={timeRange === '1y' ? 'primary' : 'ghost'}
              size="sm"
              className="rounded-none border-0"
              onClick={() => setTimeRange('1y')}
            >
              1年
            </Button>
            <Button
              variant={timeRange === '5y' ? 'primary' : 'ghost'}
              size="sm"
              className="rounded-none border-0"
              onClick={() => setTimeRange('5y')}
            >
              5年
            </Button>
          </div>
        )}
        
        <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={interval === 'intraday' ? intradayAILoading : aiLoading}
              >
                <RefreshCw className="h-4 w-4 mr-1" />
                刷新数据
              </Button>
        </div>

      </div>
    );
  };

  return (
    <Card>
      <CardContent className="p-4">
        {renderChartControls()}
        
        {interval === 'intraday' ? (
          intradayLoading ? (
            <Skeleton className="h-80 w-full" />
          ) : intradayError ? (
            <div className="h-80 w-full flex items-center justify-center">
              <div className="text-center">
                <AlertCircle className="h-10 w-10 text-red-500 mx-auto mb-2" />
                <p className="text-red-500">{intradayError}</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => loadIntradayData(true)}
                  className="mt-2"
                >
                  <RefreshCw className="h-4 w-4 mr-1" />
                  重试
                </Button>
              </div>
            </div>
          ) : (
            renderIntradayChart()
          )
        ) : (
          loading ? (
            <Skeleton className="h-80 w-full" />
          ) : error ? (
            <div className="h-80 w-full flex items-center justify-center">
              <div className="text-center">
                <AlertCircle className="h-10 w-10 text-red-500 mx-auto mb-2" />
                <p className="text-red-500">{error}</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRefresh}
                  className="mt-2"
                >
                  <RefreshCw className="h-4 w-4 mr-1" />
                  重试
                </Button>
              </div>
            </div>
          ) : (
            renderPriceVolumeChart()
          )
        )}
        
        {/* AI分析区域 */}
        <div className="mt-4">
          
          {/* AI分析类型选择 */}
          <div className="flex gap-2 mb-3">
            <Button
              variant={analysisType === 'rule' ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setAnalysisType('rule')}
              disabled={interval === 'intraday' ? intradayAILoading : aiLoading}
            >
              规则分析
            </Button>
            <Button
              variant={analysisType === 'ml' ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setAnalysisType('ml')}
              disabled={interval === 'intraday' ? intradayAILoading : aiLoading}
            >
              ML分析
            </Button>
            <Button
              variant={analysisType === 'llm' ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setAnalysisType('llm')}
              disabled={interval === 'intraday' ? intradayAILoading : aiLoading}
            >
              LLM分析
            </Button>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={interval === 'intraday' ? intradayAILoading : aiLoading}
              >
                <RefreshCw className="h-4 w-4 mr-1" />
                刷新数据
              </Button>
            </div>
          </div>
          
          {/* AI分析内容 */}
          {(() => {
            if (!showAIPrediction) return null;
            
            // 根据图表类型选择不同的分析数据
            const currentPrediction = interval === 'intraday' 
              ? intradayAIPredictions[analysisType]
              : aiPredictions[analysisType];
            
            const isLoading = interval === 'intraday' ? intradayAILoading : aiLoading;
            const error = interval === 'intraday' ? intradayAIError : aiError;
            
            if (!currentPrediction || !currentPrediction.analysis) {
              return (
                <div className="p-4 bg-muted rounded-md">
                  <div className="text-center">
                    {error && (
                      <div className="mb-4 p-2 bg-red-100 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-md">
                        <p className="text-sm flex items-center">
                          <AlertCircle className="h-4 w-4 mr-1" />
                          {error}
                        </p>
                      </div>
                    )}
                    
                    <Button
                      onClick={handleGetAIAnalysis}
                      className="bg-primary hover:bg-primary/90"
                      disabled={isLoading}
                    >
                      {isLoading ? (
                        <div className="flex items-center">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                          分析中...
                        </div>
                      ) : (
                        <>
                          <Brain className="h-4 w-4 mr-2" />
                          获取{analysisType === 'rule' ? '规则' : analysisType === 'ml' ? '机器学习' : 'LLM'}分析
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              );
            }
            
            const analysis = currentPrediction.analysis;
            const trend = analysis.trend;
            const strength = analysis.strength;
            
            return (
              <div className="p-4 bg-muted rounded-md">
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant={trend === 'bullish' ? 'success' : trend === 'bearish' ? 'destructive' : 'secondary'}>
                    {trend === 'bullish' ? '看涨' : trend === 'bearish' ? '看跌' : '中性'}
                  </Badge>
                  
                  <Badge variant="outline">
                    强度: {strength === 'strong' ? '强' : strength === 'weak' ? '弱' : '中等'}
                  </Badge>
                  
                  <Badge variant="outline">
                    分析模式: {analysisType === 'rule' ? '规则' : analysisType === 'ml' ? '机器学习' : 'LLM'}
                  </Badge>
                </div>
                
                <p className="text-sm">{analysis.summary}</p>
              </div>
            );
          })()}
        </div>
      </CardContent>
    </Card>
  );
} 