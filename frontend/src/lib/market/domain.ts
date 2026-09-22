/**
 * 市场领域数据客户端：只对接后端领域端点（/market/*，鉴权由 axios 拦截器附加）。
 * 统一三种返回契约：
 * - object: data 直接是对象
 * - list:   data.items 是数组
 * - map:    data.items 是对象字典
 */

import { api } from '../api';
import { decryptClientPayload, type EncryptedClientPayload } from '../appCipher';

const QUOTE_CHUNK_SIZE = 100;

export const FUNDFLOW_MAX_DAYS = 10;

type ApiEnvelope<T> = { success?: boolean; data?: T; error?: string };
type ListEnvelope<T> = { items?: T[] };
type MapEnvelope<T> = { items?: Record<string, T> };

async function domainObjectGet<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const result = await api.get<ApiEnvelope<T>>(path, { params });
  return (result.data.data ?? {}) as T;
}

async function domainListGet<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T[]> {
  const result = await api.get<ApiEnvelope<ListEnvelope<T>>>(path, { params });
  return result.data.data?.items ?? [];
}

async function domainMapGet<T>(path: string, params?: Record<string, string | number | undefined>): Promise<Record<string, T>> {
  const result = await api.get<ApiEnvelope<MapEnvelope<T>>>(path, { params });
  return result.data.data?.items ?? {};
}

export type FundflowRow = {
  prodCode: string;
  date: string;
  mainIn: number;
  mainOut: number;
  netInflow: number;
  superIn: number;
  superOut: number;
  netSuper: number;
  bigIn: number;
  bigOut: number;
  netBig: number;
  mediumIn: number;
  mediumOut: number;
  netMedium: number;
  smallIn: number;
  smallOut: number;
  netSmall: number;
};

export type TrendingPlate = {
  plateId?: string;
  name?: string;
  description?: string;
  stocks?: Array<{ name?: string; symbol?: string }>;
};

export type IndexBar = { date: string; open: number; close: number; high: number; low: number };

export async function fetchPoolDomain(
  kind: 'zt' | 'zb' | 'dt',
  dateHyphen?: string
): Promise<Array<{ name: string; code: string; reason: string; concepts?: string[]; lbc: number; time: number | null; type: 'zt' | 'zb' | 'dt'; fund: number | null; price: number | null; turnoverRate?: number; zbc: number; firstBreak?: number; lastSealTs?: number }>> {
  return domainListGet(`/market/pool/${kind}`, dateHyphen ? { date: dateHyphen } : undefined);
}

export type TopicPoolDomainItem = Awaited<ReturnType<typeof fetchPoolDomain>>[number];

export async function fetchPoolsBatch(
  dates: string[],
  kinds?: Array<'zt' | 'zb' | 'dt'>
): Promise<{
  ztByDate: Record<string, TopicPoolDomainItem[]>;
  zbByDate: Record<string, TopicPoolDomainItem[]>;
  dtByDate: Record<string, TopicPoolDomainItem[]>;
}> {
  const result = await api.post<
    ApiEnvelope<{
      ztByDate?: Record<string, TopicPoolDomainItem[]>;
      zbByDate?: Record<string, TopicPoolDomainItem[]>;
      dtByDate?: Record<string, TopicPoolDomainItem[]>;
    }>
  >('/market/pools/batch', { dates, kinds });
  return {
    ztByDate: result.data.data?.ztByDate ?? {},
    zbByDate: result.data.data?.zbByDate ?? {},
    dtByDate: result.data.data?.dtByDate ?? {},
  };
}

export async function fetchUniverseDomain(): Promise<
  Array<{ code: string; name: string; change: number | null; netFlow: number | null; ztCount: number | null; upCount: number | null; downCount: number | null; flatCount: number | null }>
> {
  return domainListGet('/market/universe');
}

export async function fetchSurgeDomain(): Promise<Array<{ code: string; name: string; plates: string[]; analysis?: string }>> {
  return domainListGet('/market/surge');
}

export async function fetchQuoteSnapshots(codes: string[]): Promise<Record<string, { name: string; price: number | null; change: number }>> {
  const cleanCodes = codes.filter(Boolean);
  if (cleanCodes.length === 0) return {};
  const parts: string[][] = [];
  for (let index = 0; index < cleanCodes.length; index += QUOTE_CHUNK_SIZE) {
    parts.push(cleanCodes.slice(index, index + QUOTE_CHUNK_SIZE));
  }
  const merged: Record<string, { name: string; price: number | null; change: number }> = {};
  await Promise.all(
    parts.map(async (part) => {
      Object.assign(
        merged,
        await domainMapGet<{ name: string; price: number | null; change: number }>('/market/quotes', {
          symbols: part.join(','),
        })
      );
    })
  );
  return merged;
}

export async function fetchFundflowBatch(codes: string[], days: number): Promise<Map<string, FundflowRow[]>> {
  const result = new Map<string, FundflowRow[]>();
  if (codes.length === 0) return result;
  const data = await domainMapGet<FundflowRow[]>('/market/fundflow', {
    codes: codes.join(','),
    days: Math.min(days, FUNDFLOW_MAX_DAYS),
  });
  Object.entries(data).forEach(([key, rows]) => {
    if (Array.isArray(rows)) result.set(key, rows);
  });
  return result;
}

export async function fetchTrendingPlates(): Promise<TrendingPlate[]> {
  return domainListGet('/market/trending');
}

export type PlateMemberDomain = {
  code: string;
  name: string;
  price: number | null;
  change: number | null;
  amount: number | null;
  netFlow: number | null;
  turnoverRate: number | null;
};

export async function fetchPlateMembers(plateId: string): Promise<PlateMemberDomain[]> {
  return domainListGet('/market/plate-members', { plateId });
}

export async function fetchPlateIndexHistory(plateId: string, count: number): Promise<IndexBar[]> {
  return domainListGet('/market/plate-index', { plateId, count });
}

export async function fetchTurnoverDomain(): Promise<{
  current: number | null;
  predict: number | null;
  previous: number | null;
  change: number | null;
  points: Array<{ time: string; today: number | null; yesterday: number | null }>;
}> {
  return domainObjectGet('/market/turnover');
}

export async function fetchStrategyPrivateOverrides(): Promise<{ version?: string; private?: unknown }> {
  const encrypted = await domainObjectGet<EncryptedClientPayload>('/market/strategy');
  return decryptClientPayload(encrypted, 'alphabot:market-strategy:v1');
}

export async function updateStrategyPrivateOverrides(payload: { version?: string; private: Record<string, unknown> }): Promise<{ version?: string; private?: unknown }> {
  const result = await api.put<ApiEnvelope<{ version?: string; private?: unknown }>>('/market/strategy', payload);
  return result.data.data ?? {};
}

export async function fetchLatestMarketContext(): Promise<{
  latestDay: string;
  pools: {
    ztByDate: Record<string, TopicPoolDomainItem[]>;
    zbByDate: Record<string, TopicPoolDomainItem[]>;
    dtByDate: Record<string, TopicPoolDomainItem[]>;
  };
  latestZt: TopicPoolDomainItem[];
  latestZb: TopicPoolDomainItem[];
  latestDt: TopicPoolDomainItem[];
  surge: Array<{ code: string; name: string; plates: string[]; analysis?: string }>;
  conceptIndex: Record<string, string[]>;
  baseUniverse: Array<{ code: string; name: string; change: number | null; netFlow: number | null; ztCount: number | null; upCount: number | null; downCount: number | null; flatCount: number | null }>;
  trendUniverse: Array<{ code: string; name: string; change: number | null; netFlow: number | null; ztCount: number | null; upCount: number | null; downCount: number | null; flatCount: number | null }>;
}> {
  return domainObjectGet('/market/context/latest');
}

export async function fetchPayoffList<T>(kind: 'strong' | 'hot' | 'drawdown', params?: Record<string, string | number | undefined>): Promise<T[]> {
  return domainListGet(`/market/payoff/${kind}`, params);
}
