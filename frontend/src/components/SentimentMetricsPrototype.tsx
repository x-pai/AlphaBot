'use client';

import React, { useMemo, useState } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  AlertTriangle,
  BarChart3,
  CalendarRange,
  CircleDollarSign,
  Gauge,
  Flame,
  Target,
  TrendingUp,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { cn } from '@/lib/utils';

type MetricKey = 'ratio' | 'returnRate' | 'count' | 'amount';
type PresetRange = 20 | 40 | 60 | 120;

type MetricPoint = {
  date: string;
  advanceRate: number;
  breakoutRate: number;
  marketHeat: number;
  avgReturn: number;
  maxReturn: number;
  medianReturn: number;
  firstBoardCount: number;
  secondBoardCount: number;
  breakoutCount: number;
  turnoverAmount: number;
  northboundAmount: number;
  mainForceAmount: number;
};

type SeriesMeta = {
  key: keyof MetricPoint;
  name: string;
  color: string;
  isPrimary?: boolean;
};

type MetricConfig = {
  key: MetricKey;
  name: string;
  unit: '%' | '家' | '亿';
  icon: React.ComponentType<{ className?: string }>;
  threshold: number;
  description: string;
  series: SeriesMeta[];
};

type SummaryStats = {
  totalTradingDays: number;
  breakoutCount: number;
  breakoutRatio: number;
  latestBreakoutDate: string | null;
  maxValue: number;
  avgValue: number;
  currentValue: number;
};

const METRIC_CONFIGS: MetricConfig[] = [
  {
    key: 'ratio',
    name: '比率指标(%)',
    unit: '%',
    icon: Gauge,
    threshold: 6.5,
    description: '观察市场核心情绪比率，重点标注超阈值日。',
    series: [
      { key: 'advanceRate', name: '涨停晋级率', color: '#3b82f6', isPrimary: true },
      { key: 'breakoutRate', name: '炸板率', color: '#f97316' },
      { key: 'marketHeat', name: '承接热度', color: '#10b981' },
    ],
  },
  {
    key: 'returnRate',
    name: '收益率(%)',
    unit: '%',
    icon: TrendingUp,
    threshold: 4.2,
    description: '用于观察强势股次日反馈与中位收益波动。',
    series: [
      { key: 'avgReturn', name: '平均收益', color: '#3b82f6', isPrimary: true },
      { key: 'maxReturn', name: '最大收益', color: '#ef4444' },
      { key: 'medianReturn', name: '中位收益', color: '#14b8a6' },
    ],
  },
  {
    key: 'count',
    name: '数量指标',
    unit: '家',
    icon: BarChart3,
    threshold: 42,
    description: '观察不同梯队个股数量变化与突破密集区。',
    series: [
      { key: 'firstBoardCount', name: '首板数量', color: '#3b82f6', isPrimary: true },
      { key: 'secondBoardCount', name: '二板数量', color: '#8b5cf6' },
      { key: 'breakoutCount', name: '突破个股', color: '#f59e0b' },
    ],
  },
  {
    key: 'amount',
    name: '金额(亿)',
    unit: '亿',
    icon: CircleDollarSign,
    threshold: 180,
    description: '观察成交额与资金强弱，适合后续接入真实成交数据。',
    series: [
      { key: 'turnoverAmount', name: '总成交额', color: '#3b82f6', isPrimary: true },
      { key: 'northboundAmount', name: '北向资金', color: '#22c55e' },
      { key: 'mainForceAmount', name: '主力净流入', color: '#f97316' },
    ],
  },
];

const PRESET_RANGES: PresetRange[] = [20, 40, 60, 120];

function formatDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

function formatXAxisLabel(value: string) {
  const [year, month, day] = value.split('-');
  return `${month}.${day}`;
}

function parseDate(value: string) {
  return new Date(`${value}T00:00:00`);
}

function shiftDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function getDefaultDateRange() {
  const endDate = new Date('2026-06-09T00:00:00');
  return {
    endDate: formatDate(endDate),
    startDate: formatDate(shiftDays(endDate, -119)),
  };
}

function createTradingDates(startDate: string, endDate: string) {
  const dates: string[] = [];
  let cursor = parseDate(startDate);
  const end = parseDate(endDate);

  while (cursor <= end) {
    const day = cursor.getDay();
    if (day !== 0 && day !== 6) {
      dates.push(formatDate(cursor));
    }
    cursor = shiftDays(cursor, 1);
  }

  return dates;
}

function createMockSeries(dates: string[]) {
  return dates.map((date, index) => {
    const wave = Math.sin(index * 0.37);
    const subWave = Math.cos(index * 0.19);
    const spike = index % 29 === 12 ? 4.8 : index % 41 === 6 ? 3.3 : 0;
    const lateSpike = index === dates.length - 1 ? 4.2 : 0;

    const advanceRate = Number((3.1 + wave * 1.4 + subWave * 0.9 + spike + lateSpike).toFixed(2));
    const breakoutRate = Number((2.7 + Math.cos(index * 0.24) * 1.2 + (index % 23 === 4 ? 1.1 : 0)).toFixed(2));
    const marketHeat = Number((4.4 + Math.sin(index * 0.14) * 0.8 + (index % 35 === 8 ? 0.9 : 0)).toFixed(2));
    const avgReturn = Number((1.2 + wave * 1.1 + spike * 0.5 + lateSpike * 0.4).toFixed(2));
    const maxReturn = Number((4.8 + Math.abs(wave) * 3.2 + spike * 0.7 + lateSpike * 0.5).toFixed(2));
    const medianReturn = Number((0.8 + subWave * 0.7 + spike * 0.15).toFixed(2));
    const firstBoardCount = Number((26 + wave * 9 + spike * 3 + lateSpike * 2).toFixed(0));
    const secondBoardCount = Number((11 + subWave * 5 + spike * 1.4).toFixed(0));
    const breakoutCount = Number((9 + Math.abs(wave) * 6 + spike * 1.8).toFixed(0));
    const turnoverAmount = Number((128 + wave * 24 + spike * 20 + lateSpike * 14).toFixed(2));
    const northboundAmount = Number((46 + subWave * 11 + spike * 5).toFixed(2));
    const mainForceAmount = Number((38 + Math.sin(index * 0.22) * 14 + spike * 6).toFixed(2));

    return {
      date,
      advanceRate: Math.max(0.8, advanceRate),
      breakoutRate: Math.max(0.5, breakoutRate),
      marketHeat: Math.max(1.2, marketHeat),
      avgReturn: Math.max(-1.5, avgReturn),
      maxReturn: Math.max(0.5, maxReturn),
      medianReturn: Math.max(-0.8, medianReturn),
      firstBoardCount: Math.max(6, firstBoardCount),
      secondBoardCount: Math.max(1, secondBoardCount),
      breakoutCount: Math.max(0, breakoutCount),
      turnoverAmount: Math.max(60, turnoverAmount),
      northboundAmount: Math.max(10, northboundAmount),
      mainForceAmount: Math.max(5, mainForceAmount),
    };
  });
}

function getSummaryStats(points: MetricPoint[], metricConfig: MetricConfig): SummaryStats {
  const primarySeries = metricConfig.series.find((series) => series.isPrimary) ?? metricConfig.series[0];
  const values = points.map((point) => Number(point[primarySeries.key]));
  const breakoutPoints = points.filter((point) => Number(point[primarySeries.key]) >= metricConfig.threshold);
  const latestBreakout = breakoutPoints.length > 0 ? breakoutPoints[breakoutPoints.length - 1].date : null;
  const total = values.reduce((sum, value) => sum + value, 0);

  return {
    totalTradingDays: points.length,
    breakoutCount: breakoutPoints.length,
    breakoutRatio: points.length > 0 ? (breakoutPoints.length / points.length) * 100 : 0,
    latestBreakoutDate: latestBreakout,
    maxValue: values.length > 0 ? Math.max(...values) : 0,
    avgValue: values.length > 0 ? total / values.length : 0,
    currentValue: values.length > 0 ? values[values.length - 1] : 0,
  };
}

function formatValue(value: number, unit: MetricConfig['unit']) {
  if (unit === '%') {
    return `${value.toFixed(2)}%`;
  }
  if (unit === '亿') {
    return `${value.toFixed(2)}亿`;
  }
  return `${Math.round(value)}家`;
}

function getRangeStart(endDate: string, days: PresetRange) {
  return formatDate(shiftDays(parseDate(endDate), -(days - 1)));
}

export default function SentimentMetricsPrototype() {
  const defaults = useMemo(() => getDefaultDateRange(), []);
  const [metricKey, setMetricKey] = useState<MetricKey>('ratio');
  const [activeRange, setActiveRange] = useState<PresetRange>(120);
  const endDate = defaults.endDate;
  const startDate = useMemo(() => getRangeStart(endDate, activeRange), [activeRange, endDate]);

  const metricConfig = useMemo(
    () => METRIC_CONFIGS.find((config) => config.key === metricKey) ?? METRIC_CONFIGS[0],
    [metricKey]
  );

  const chartData = useMemo(() => {
    const tradingDates = createTradingDates(startDate, endDate);
    return createMockSeries(tradingDates);
  }, [startDate, endDate]);

  const summary = useMemo(() => getSummaryStats(chartData, metricConfig), [chartData, metricConfig]);

  const primarySeries = useMemo(
    () => metricConfig.series.find((series) => series.isPrimary) ?? metricConfig.series[0],
    [metricConfig]
  );

  const highlightedDates = useMemo(() => {
    return new Set(
      chartData
        .filter((point) => Number(point[primarySeries.key]) >= metricConfig.threshold)
        .map((point) => point.date)
    );
  }, [chartData, metricConfig.threshold, primarySeries]);

  const isAboveThreshold = summary.currentValue >= metricConfig.threshold;
  const thresholdGap = summary.currentValue - metricConfig.threshold;
  const latestBreakoutLabel = summary.latestBreakoutDate
    ? formatXAxisLabel(summary.latestBreakoutDate)
    : '--';

  const chartDomain = useMemo(() => {
    const values = chartData.flatMap((point) =>
      metricConfig.series.map((series) => Number(point[series.key]))
    );
    values.push(metricConfig.threshold);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min || 1) * 0.12;
    return [Math.max(0, min - padding), max + padding];
  }, [chartData, metricConfig]);

  const metricCards = METRIC_CONFIGS.map((config) => {
    const Icon = config.icon;
    const selected = config.key === metricKey;
    return (
      <button
        key={config.key}
        type="button"
        onClick={() => setMetricKey(config.key)}
        className={cn(
          'rounded-lg border p-4 text-left transition-colors',
          selected ? 'border-primary bg-primary/10' : 'border-border bg-card hover:bg-muted/60'
        )}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className={cn('h-4 w-4', selected ? 'text-primary' : 'text-muted-foreground')} />
            <span className="text-sm font-medium">{config.name}</span>
          </div>
          {selected && <Badge variant="default">当前</Badge>}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">{config.description}</p>
      </button>
    );
  });

  return (
    <div className="space-y-6">
      <Card className="bg-card">
        <CardHeader className="border-b border-border pb-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Target className="h-5 w-5 text-primary" />
                <CardTitle>情绪指标统计</CardTitle>
              </div>
              <CardDescription className="mt-1">
                保持首屏先见图，筛选和状态信息只保留最关键部分。
              </CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span>{startDate} - {endDate}</span>
              <span>共 {summary.totalTradingDays} 个交易日</span>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="grid gap-3 xl:grid-cols-[0.9fr_1.35fr]">
            <div>
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
                <CalendarRange className="h-4 w-4 text-muted-foreground" />
                快捷区间
              </div>
              <div className="flex flex-wrap gap-2">
                {PRESET_RANGES.map((range) => (
                  <Button
                    key={range}
                    variant={activeRange === range ? 'primary' : 'outline'}
                    size="sm"
                    onClick={() => setActiveRange(range)}
                  >
                    近{range}日
                  </Button>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
                <Gauge className="h-4 w-4 text-muted-foreground" />
                指标切换
              </div>
              <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
                {METRIC_CONFIGS.map((config) => {
                  const Icon = config.icon;
                  const selected = config.key === metricKey;
                  return (
                    <button
                      key={config.key}
                      type="button"
                      onClick={() => setMetricKey(config.key)}
                      className={cn(
                        'rounded-md border px-3 py-2 text-left transition-colors',
                        selected ? 'border-primary bg-primary/10' : 'border-border bg-card hover:bg-muted/60'
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <Icon className={cn('h-4 w-4', selected ? 'text-primary' : 'text-muted-foreground')} />
                        <span className="text-xs font-medium">{config.name}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="border-b border-border pb-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle className="text-base">{metricConfig.name}走势</CardTitle>
              <CardDescription className="mt-1">红线代表参考阈值，首屏只保留最关键的读图信息。</CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">当前 {formatValue(summary.currentValue, metricConfig.unit)}</Badge>
              <Badge variant="warning">阈值 {formatValue(metricConfig.threshold, metricConfig.unit)}</Badge>
              <Badge variant={isAboveThreshold ? 'destructive' : 'success'}>
                {isAboveThreshold ? '高于阈值' : '低于阈值'}
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="mb-4 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
              <div className="flex items-center gap-2">
                <Flame className="h-4 w-4 text-primary" />
                <span className="text-muted-foreground">当前值</span>
                <span className="font-semibold text-foreground">{formatValue(summary.currentValue, metricConfig.unit)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">阈值状态</span>
                <span className={cn('font-semibold', isAboveThreshold ? 'text-red-500' : 'text-emerald-600')}>
                  {isAboveThreshold ? '高于阈值' : '低于阈值'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">差值</span>
                <span className="font-semibold text-foreground">
                  {thresholdGap >= 0 ? '+' : '-'}{formatValue(Math.abs(thresholdGap), metricConfig.unit)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">最近突破</span>
                <span className="font-semibold text-foreground">{latestBreakoutLabel}</span>
              </div>
            </div>
          </div>

          <div className="h-[56vh] min-h-[420px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatXAxisLabel}
                  tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
                  minTickGap={28}
                />
                <YAxis
                  domain={chartDomain}
                  tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
                  tickFormatter={(value: number) => {
                    if (metricConfig.unit === '%') return `${value.toFixed(0)}%`;
                    if (metricConfig.unit === '亿') return `${value.toFixed(0)}`;
                    return `${Math.round(value)}`;
                  }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--card)',
                    borderColor: 'var(--border)',
                    borderRadius: '0.5rem',
                  }}
                  formatter={(value: number, name: string) => [formatValue(Number(value), metricConfig.unit), name]}
                  labelFormatter={(label: string) => `日期: ${label}`}
                />
                <Legend />
                <ReferenceLine
                  y={metricConfig.threshold}
                  stroke="#ef4444"
                  strokeWidth={2}
                  strokeDasharray="6 4"
                  label={{
                    value: `阈值 ${formatValue(metricConfig.threshold, metricConfig.unit)}`,
                    fill: '#ef4444',
                    position: 'insideTopRight',
                    fontSize: 12,
                  }}
                />
                {metricConfig.series.map((series) => (
                  <Line
                    key={series.key}
                    type="monotone"
                    dataKey={series.key}
                    name={series.name}
                    stroke={series.color}
                    strokeWidth={series.isPrimary ? 2.5 : 1.8}
                    dot={(props: any) => {
                      const { cx, cy, payload } = props;
                      if (!series.isPrimary || !highlightedDates.has(payload.date)) {
                        return <circle cx={cx} cy={cy} r={2.5} fill={series.color} stroke="none" />;
                      }

                      return (
                        <g>
                          <circle cx={cx} cy={cy} r={11} fill="rgba(239, 68, 68, 0.08)" />
                          <circle cx={cx} cy={cy} r={7} fill="#ffffff" stroke="#ef4444" strokeWidth={2} />
                          <circle cx={cx} cy={cy} r={3} fill="#ef4444" />
                        </g>
                      );
                    }}
                    activeDot={{ r: 6 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card className="border-primary/20">
              <CardContent className="p-5">
                <div className="text-sm text-muted-foreground">当前观察值</div>
                <div className="mt-2 text-2xl font-semibold text-foreground">
                  {formatValue(summary.currentValue, metricConfig.unit)}
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  主观察指标：{primarySeries.name}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5">
                <div className="text-sm text-muted-foreground">超阈值次数</div>
                <div className="mt-2 text-2xl font-semibold text-red-500">
                  {summary.breakoutCount}
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  阈值线：{formatValue(metricConfig.threshold, metricConfig.unit)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5">
                <div className="text-sm text-muted-foreground">超阈值占比</div>
                <div className="mt-2 text-2xl font-semibold">
                  {summary.breakoutRatio.toFixed(1)}%
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  用于判断情绪高位密度
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5">
                <div className="text-sm text-muted-foreground">最近一次突破</div>
                <div className="mt-2 text-2xl font-semibold">
                  {latestBreakoutLabel}
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  均值 {formatValue(summary.avgValue, metricConfig.unit)} / 峰值 {formatValue(summary.maxValue, metricConfig.unit)}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-lg border border-border bg-background p-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <AlertTriangle className="h-4 w-4 text-red-500" />
                读图重点
              </div>
              <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                <li>先看当前值是否站上红线，这是页面最重要的判断。</li>
                <li>再看红圈点是否集中出现，判断情绪高位是偶发还是持续。</li>
                <li>最后结合最近突破日期，辅助判断市场是否刚进入活跃阶段。</li>
              </ul>
            </div>
            <div className="rounded-lg border border-border bg-background p-4">
              <div className="text-sm font-medium text-foreground">后续接真实数据建议字段</div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge variant="outline">startDate</Badge>
                <Badge variant="outline">endDate</Badge>
                <Badge variant="outline">seriesMeta</Badge>
                <Badge variant="outline">points</Badge>
                <Badge variant="outline">threshold</Badge>
                <Badge variant="outline">breakoutPoints</Badge>
                <Badge variant="outline">summary</Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
