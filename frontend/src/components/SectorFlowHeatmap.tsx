'use client';

import { useMemo, useState } from 'react';
import { Info, Pin } from 'lucide-react';
import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import { cn } from '@/lib/utils';
import { flowHeatBand, summarizeFlow, validFlowPoint, type FlowObservation } from '@/lib/market/flowPersistence';
import { TooltipContent, TooltipProvider } from '@/components/ui/tooltip';

type FlowRow = { id: string; name: string; points: FlowObservation[] };
type Props = {
  rows: FlowRow[];
  dates: string[];
  loading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
};

const HEAT_COLORS: Record<number, string> = {
  '-3': 'bg-emerald-600 text-white',
  '-2': 'bg-emerald-200 text-emerald-950 dark:bg-emerald-800 dark:text-emerald-50',
  '-1': 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200',
  0: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300',
  1: 'bg-rose-50 text-rose-800 dark:bg-rose-950 dark:text-rose-200',
  2: 'bg-rose-200 text-rose-950 dark:bg-rose-800 dark:text-rose-50',
  3: 'bg-rose-600 text-white',
};

const TOOLTIP_SURFACE = 'rounded-xl border border-slate-200/70 bg-white/[0.88] px-3 py-2 text-slate-700 shadow-[0_12px_28px_rgba(15,23,42,0.12)] backdrop-blur-md dark:border-slate-700/60 dark:bg-slate-950/[0.84] dark:text-slate-200';

const signed = (value: number, digits = 1) => `${value > 0 ? '+' : ''}${value.toFixed(digits)}`;
const tone = (value: number | null) => value == null || value === 0 ? 'text-muted-foreground' : value > 0 ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-600 dark:text-emerald-400';

export default function SectorFlowHeatmap({ rows, dates, loading, selectedId, onSelect }: Props) {
  const [days, setDays] = useState<5 | 10>(10);
  const [pinned, setPinned] = useState<string[]>([]);
  const [showAll, setShowAll] = useState(false);
  const visibleDates = dates.slice(-days);
  const orderedRows = useMemo(() => [...rows].sort((a, b) => Number(pinned.includes(b.id)) - Number(pinned.includes(a.id))), [rows, pinned]);
  const visibleRows = showAll ? orderedRows : orderedRows.filter((row, index) => index < 10 || pinned.includes(row.id) || row.id === selectedId);
  const missingRows = rows.filter((row) => !row.points.some(validFlowPoint)).length;

  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-background shadow-sm" aria-busy={loading}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border/60 px-3 py-2.5">
        <div className="flex items-center gap-1.5">
          <h3 className="text-sm font-semibold text-foreground">板块资金热力图</h3>
          <TooltipProvider delayDuration={120}>
            <TooltipPrimitive.Root>
              <TooltipPrimitive.Trigger asChild>
                <button type="button" aria-label="资金口径说明" className="rounded p-1 text-muted-foreground hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-500"><Info size={13} /></button>
              </TooltipPrimitive.Trigger>
              <TooltipPrimitive.Portal>
                <TooltipContent side="bottom" align="start" className={cn(TOOLTIP_SURFACE, 'max-w-[min(320px,calc(100vw-24px))] text-[11px] leading-5')}>
                  <p>横向看持续性，纵向看资金关注方向。点击板块查看详情，置顶仅调整本页顺序。</p>
                  <p className="mt-1.5">净占比 = 主力净额 / 主力买卖总额。按当前候选板块的当前成分股聚合，板块之间可能重叠。</p>
                  <p className="mt-1.5">颜色深浅按占比绝对值：深色 ≥ 8%，中色 3%–8%，浅色 &lt; 3%，灰色为 0。虚线表示缺失；近 5 日数据不齐时不计算汇总。</p>
                </TooltipContent>
              </TooltipPrimitive.Portal>
            </TooltipPrimitive.Root>
          </TooltipProvider>
          <span className="text-[10px] text-muted-foreground">{loading ? '加载中' : `${visibleDates.length}日`}</span>
        </div>
        <div className="flex items-center gap-1 text-[10px] text-muted-foreground" aria-label="颜色图例：绿色净流出，红色净流入，颜色越深占比绝对值越大">
          <span className="mr-0.5">流出</span>
          {[-3, -2, -1, 0, 1, 2, 3].map((band) => <span key={band} aria-hidden="true" className={cn('h-2.5 w-3 rounded-sm', HEAT_COLORS[band])} />)}
          <span className="ml-0.5">流入</span>
        </div>
        <div className="ml-auto flex rounded-full border border-border/70 bg-muted/25 p-0.5" aria-label="历史显示范围">
          {([5, 10] as const).map((value) => (
            <button key={value} type="button" aria-pressed={days === value} onClick={() => setDays(value)} className={cn('rounded-full px-2.5 py-1 text-xs transition-colors', days === value ? 'bg-foreground text-background' : 'text-muted-foreground hover:text-foreground')}>近 {value} 日</button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="px-3 py-8 text-center text-sm text-muted-foreground" role="status">正在加载板块资金历史…</div>
      ) : dates.length === 0 || missingRows === rows.length ? (
        <div className="px-3 py-8 text-center text-sm text-muted-foreground" role="status">暂无可用资金历史，请稍后刷新。</div>
      ) : (
        <TooltipProvider delayDuration={120}>
          <div className="overflow-x-auto">
            <table className="w-full border-separate border-spacing-0 text-xs" style={{ minWidth: days === 10 ? 920 : 680 }}>
              <caption className="sr-only">板块每日主力净流入占比和最近五个交易日资金汇总</caption>
              <thead>
                <tr className="text-muted-foreground">
                  <th scope="col" className="sticky left-0 z-10 min-w-[128px] bg-background px-3 py-2 text-left font-normal">板块 / 置顶</th>
                  {visibleDates.map((date) => <th key={date} scope="col" className="min-w-[48px] px-0.5 py-2 text-center font-normal">{date.slice(5)}</th>)}
                  <th scope="col" className="min-w-[92px] px-2 py-2 text-right font-normal">5日流入天数</th>
                  <th scope="col" className="min-w-[90px] px-2 py-2 text-right font-normal">5日净额</th>
                  <th scope="col" className="min-w-[80px] px-3 py-2 text-right font-normal">最新占比</th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row) => {
                  const byDate = new Map(row.points.filter(validFlowPoint).map((point) => [point.date, point]));
                  const summary = summarizeFlow(row.points, dates);
                  const active = row.id === selectedId;
                  const isPinned = pinned.includes(row.id);
                  return (
                    <tr key={row.id} className={cn('group', active && 'bg-orange-50/50 dark:bg-orange-950/15')}>
                      <th scope="row" className={cn('sticky left-0 z-10 border-t border-border/40 bg-background px-2 py-1 text-left', active && 'shadow-[inset_3px_0_0_rgb(249_115_22)]')}>
                        <div className="flex items-center gap-1">
                          <button type="button" aria-label={`${isPinned ? '取消置顶' : '置顶'}${row.name}`} aria-pressed={isPinned} onClick={() => setPinned((current) => isPinned ? current.filter((id) => id !== row.id) : [...current, row.id])} className={cn('rounded-md p-1.5 transition-colors hover:bg-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-500', isPinned ? 'text-orange-600' : 'text-muted-foreground/50')}><Pin size={13} fill={isPinned ? 'currentColor' : 'none'} /></button>
                          <button type="button" onClick={() => onSelect(row.id)} aria-pressed={active} className="max-w-[130px] truncate py-1 text-left font-medium text-foreground hover:text-orange-600">{row.name}</button>
                        </div>
                      </th>
                      {visibleDates.map((date) => {
                        const point = byDate.get(date);
                        return (
                          <td key={date} className="border-t border-border/40 px-0.5 py-1">
                            <TooltipPrimitive.Root>
                              <TooltipPrimitive.Trigger asChild>
                                <button type="button" onClick={() => onSelect(row.id)} aria-label={`${row.name} ${date} ${point ? `净占比 ${signed(point.mainNetInflowRatio)}%，净流入 ${signed(point.mainNetInflow)} 亿` : '缺少数据'}`} className={cn('h-7 w-full rounded text-[11px] tabular-nums transition-shadow hover:ring-2 hover:ring-orange-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-500', point ? HEAT_COLORS[flowHeatBand(point.mainNetInflowRatio)] : 'border border-dashed border-border bg-muted/15 text-muted-foreground/50')}>
                                  {point ? `${signed(point.mainNetInflowRatio)}%` : '—'}
                                </button>
                              </TooltipPrimitive.Trigger>
                              <TooltipPrimitive.Portal>
                                <TooltipContent className={cn(TOOLTIP_SURFACE, 'max-w-[calc(100vw-24px)] text-xs leading-5')}>
                                  <div className="font-medium">{row.name} · {date}</div>
                                  <div className="mt-1">{point ? `主力净流入 ${signed(point.mainNetInflow, 2)} 亿 · 净占比 ${signed(point.mainNetInflowRatio, 2)}%` : '当日缺少资金数据，不计作零流入。'}</div>
                                </TooltipContent>
                              </TooltipPrimitive.Portal>
                            </TooltipPrimitive.Root>
                          </td>
                        );
                      })}
                      <td className="border-t border-border/40 px-2 py-1 text-right tabular-nums">
                        {summary.positiveDays == null ? <span className="text-[10px] text-muted-foreground">数据 {summary.availableDays}/5 日</span> : <span className={summary.positiveDays >= 4 ? 'font-semibold text-rose-600 dark:text-rose-400' : 'text-foreground'}>{summary.positiveDays}<span className="ml-1 font-normal text-muted-foreground">/ 5 日</span></span>}
                      </td>
                      <td className={cn('border-t border-border/40 px-2 py-1 text-right font-medium tabular-nums', tone(summary.netInflow))}>{summary.netInflow == null ? '—' : `${signed(summary.netInflow)} 亿`}</td>
                      <td className={cn('border-t border-border/40 px-3 py-1 text-right font-medium tabular-nums', tone(summary.latest?.mainNetInflowRatio ?? null))}>{summary.latest ? `${signed(summary.latest.mainNetInflowRatio)}%` : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </TooltipProvider>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/60 px-3 py-2 text-[10px] text-muted-foreground">
        <span>红入绿出 · 虚线为缺失{!loading && missingRows > 0 ? ` · ${missingRows} 个板块暂无历史` : ''}</span>
        {rows.length > 10 && <button type="button" onClick={() => setShowAll((value) => !value)} className="hover:text-foreground">{showAll ? '收起板块' : `展开全部 ${rows.length} 个板块`}</button>}
      </div>
    </div>
  );
}
