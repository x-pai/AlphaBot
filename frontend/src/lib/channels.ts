import { api } from './api';
export interface ChannelStatus { channel: string; enabled: boolean; configured: boolean; available: boolean; connection: string }
export interface ChannelTarget { id: number; channel: string; kind: string; name: string; available: boolean; last_result: ChannelSendResult | null }
export interface ChannelOverview { channels: ChannelStatus[]; bindings: { id: number; channel: string; external_user_id: string; current_bot: boolean }[]; targets: ChannelTarget[] }
export const channelNames: Record<string, string> = { qq: 'QQ', telegram: 'Telegram', feishu: '飞书', webhook: 'Webhook' };
export async function channelRequest<T>(method: string, path = '', data?: unknown): Promise<T> {
  const response = await api.request({ method, url: `/user/channels${path}`, data });
  if (!response.data.success) throw new Error(response.data.error || '操作失败');
  return response.data.data as T;
}
export const loadChannels = () => channelRequest<ChannelOverview>('GET');

export interface ChannelSendResult {
  success: boolean; error?: string; code?: string | number | null;
  http_status?: number; provider_message?: string; trace_id?: string; stage?: string; at?: string;
}
export function channelSendError(result: ChannelSendResult): string {
  const text = result.error || '发送失败';
  const details = [text];
  if (result.http_status && !text.includes('HTTP ')) details.push(`HTTP ${result.http_status}`);
  if (result.code != null && !text.includes('错误码 ')) details.push(`错误码 ${result.code}`);
  if (result.provider_message && !text.includes(result.provider_message)) details.push(result.provider_message);
  if (result.trace_id && !text.includes('Trace ID:')) details.push(`Trace ID: ${result.trace_id}`);
  return details.join('；');
}
