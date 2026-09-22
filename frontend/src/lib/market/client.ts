import { api } from '../api';
import { indexedDBCache } from '../indexedDBCache';

const inflight = new Map<string, Promise<unknown>>();
const memory = new Map<string, { at: number; ttl: number; data: unknown }>();

export type MarketSourceInfo = { source: string; cacheNamespace: string; notice?: string | null; unavailable: string[] };
let sourceInfo: { at: number; value: MarketSourceInfo } | undefined;
let sourceRequest: Promise<MarketSourceInfo> | undefined;
export async function getMarketSourceInfo(): Promise<MarketSourceInfo> {
  if (sourceInfo && Date.now() - sourceInfo.at < 15000) return sourceInfo.value;
  if (!sourceRequest) {
    sourceRequest = api.get<{ data: MarketSourceInfo }>('/market/source-info').then(({ data }) => {
      sourceInfo = { at: Date.now(), value: data.data };
      return data.data;
    }).finally(() => { sourceRequest = undefined; });
  }
  return sourceRequest;
}

export const TTL = {
  seconds: (value: number) => value * 1000,
  minutes: (value: number) => value * 60_000,
  hours: (value: number) => value * 3_600_000,
  days: (value: number) => value * 86_400_000,
};

export function buildMarketCacheKey(
  resource: string,
  params?: Record<string, string | number | boolean | null | undefined>
): string {
  const pairs = Object.entries(params || {})
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${key}=${String(value)}`);
  return pairs.length > 0 ? `${resource}:${pairs.join(':')}` : resource;
}

function persistKey(key: string) {
  return `market:${key}`;
}

async function readPersisted<T>(key: string): Promise<T | null> {
  if (typeof window === 'undefined') return null;
  try {
    return await indexedDBCache.get<T>(persistKey(key));
  } catch {
    return null;
  }
}

async function writePersisted(key: string, ttl: number, data: unknown) {
  if (typeof window === 'undefined') return;
  try {
    await indexedDBCache.set(persistKey(key), data, ttl);
  } catch {
    // ignore persistence failures
  }
}

export async function cached<T>(
  key: string,
  ttl: number,
  persist: boolean,
  loader: () => Promise<T>
): Promise<T> {
  const source = await getMarketSourceInfo();
  key = `${source.cacheNamespace}:${key}`;
  const hit = memory.get(key);
  if (hit && Date.now() - hit.at < hit.ttl) {
    return hit.data as T;
  }
  if (persist) {
    const stored = await readPersisted<T>(key);
    if (stored != null) {
      memory.set(key, { at: Date.now(), ttl, data: stored });
      return stored;
    }
  }
  const pending = inflight.get(key);
  if (pending) {
    return pending as Promise<T>;
  }

  const request = loader()
    .then(async (data) => {
      memory.set(key, { at: Date.now(), ttl, data });
      const empty = Array.isArray(data) && data.length === 0;
      if (persist && !empty) await writePersisted(key, ttl, data);
      return data;
    })
    .finally(() => {
      inflight.delete(key);
    });
  inflight.set(key, request);
  return request;
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    cache: 'no-cache',
    headers: { Accept: 'application/json,text/javascript,*/*' },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

export function marketGet<T>(url: string, ttl = TTL.seconds(30), persist = false, key: string): Promise<T> {
  return cached(key, ttl, persist, () => fetchJson<T>(url));
}

export async function mapBatches<T, R>(items: T[], size: number, mapper: (item: T) => Promise<R>): Promise<R[]> {
  const output: R[] = [];
  for (let index = 0; index < items.length; index += size) {
    const chunk = await Promise.all(items.slice(index, index + size).map(mapper));
    output.push(...chunk);
  }
  return output;
}
