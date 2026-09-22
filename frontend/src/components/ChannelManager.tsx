"use client";
import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@/lib/contexts/AuthContext';
import { channelNames, channelRequest, ChannelOverview, loadChannels, ChannelSendResult, channelSendError } from '@/lib/channels';
import { Button } from './ui/button';
import { Input } from './ui/input';

export default function ChannelManager({ systemOnly = false }: { systemOnly?: boolean }) {
  const { user } = useAuth();
  const [data, setData] = useState<ChannelOverview | null>(null);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState<{ code: string; expires_at: string; channel: string; kind: string } | null>(null);
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [editing, setEditing] = useState<number | null>(null);
  const refresh = useCallback(async () => {
    try { setData(await loadChannels()); setError(''); }
    catch { setError('加载失败，请确认已登录后重试。'); }
  }, []);
  useEffect(() => { if (user) void refresh(); }, [user, refresh]);
  useEffect(() => {
    if (!code) return;
    const timer = setInterval(() => {
      if (Date.now() >= new Date(code.expires_at).getTime()) { setCode(null); return; }
      void refresh();
    }, 5000);
    return () => clearInterval(timer);
  }, [code, refresh]);
  async function action(fn: () => Promise<void>) {
    setBusy(true); setError(''); setFeedback('');
    try { await fn(); await refresh(); }
    catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(detail || (e instanceof Error ? e.message : '操作失败'));
    } finally { setBusy(false); }
  }
  if (!user) return <p>请先登录，再管理个人渠道。</p>;
  if (systemOnly && !user.is_admin) return <p>仅管理员可查看系统渠道配置。</p>;
  return <div className="space-y-6">
    <div className="flex items-center justify-between"><h2 className="text-xl font-semibold">{systemOnly ? '系统消息渠道' : '个人渠道管理'}</h2><Button variant="outline" onClick={() => void refresh()}>刷新状态</Button></div>
    <p className="text-sm text-muted-foreground">{systemOnly ? '机器人凭证和总开关由服务端环境变量管理，修改后需重启服务。QQ 使用 WebSocket。' : '系统提供机器人，绑定你的账号后，可在每日任务和预警中选择接收目标。'}</p>
    {error && <p role="alert" className="text-red-600">{error}</p>}
    {feedback && <p role="status" className="text-green-600">{feedback}</p>}
    <div className="grid gap-4 md:grid-cols-2">{data?.channels.map(c => <section key={c.channel} className="rounded-xl border p-4 space-y-3">
      <h3 className="font-semibold">{channelNames[c.channel]}</h3>
      <p className="text-sm">{systemOnly ? (!c.enabled ? '已关闭' : !c.configured ? '凭证未配置' : c.channel === 'qq' ? c.connection : '已启用 · 配置完整') : (c.available ? '可绑定和推送' : '当前不可用，请联系管理员')}</p>
      {!systemOnly && c.channel !== 'webhook' && <>
        {data.bindings.filter(b => b.channel === c.channel).map(b => <div key={b.id} className="text-sm flex items-center justify-between gap-2"><span>{b.current_bot ? '已绑定' : '机器人已更换'} · {b.external_user_id.slice(0, 8)}…</span><Button disabled={busy} variant="outline" onClick={() => {
          if (window.confirm('解绑会移除该渠道的接收目标，相关任务将停止推送。继续？')) void action(async () => { await channelRequest('DELETE', `/bindings/${b.id}`); setCode(null); });
        }}>解绑</Button></div>)}
        <div className="flex flex-wrap gap-2">{(['private', 'group'] as const).map(kind => <Button key={kind} disabled={busy || !c.available} variant="outline" onClick={() => void action(async () => {
          const result = await channelRequest<{ code: string; expires_at: string }>('POST', '/binding-codes', { channel: c.channel, kind });
          setCode({ ...result, channel: c.channel, kind });
        })}>{kind === 'private' ? '绑定账号' : '添加群目标'}</Button>)}</div>
      </>}
    </section>)}</div>
    {!systemOnly && <>
      {code && <section className="rounded-xl border border-blue-300 bg-blue-50 p-4 text-slate-900 space-y-2">
        <p>在 {channelNames[code.channel]} {code.kind === 'group' ? '目标群中 @机器人' : '私聊机器人'}发送：</p>
        <code className="block font-mono text-lg">绑定 {code.code}</code>
        <p className="text-sm">有效至 {new Date(code.expires_at).toLocaleTimeString()}，仅可使用一次。{code.kind === 'group' && '请先完成个人绑定，再用同一账号操作。'}完成后下方会显示接收目标。</p>
        <Button variant="outline" onClick={() => void navigator.clipboard.writeText(`绑定 ${code.code}`).catch(() => setError('复制失败，请手动复制。'))}>复制指令</Button>
      </section>}
      <section className="space-y-3"><h3 className="font-semibold">接收目标</h3>
        {!data?.targets.length && <p className="text-sm text-muted-foreground">尚无接收目标，请绑定账号或添加 Webhook。</p>}
        {data?.targets.map(t => <div key={t.id} className="rounded-xl border p-4 space-y-2">
          <p className="font-medium">{t.name} <span className="text-sm text-muted-foreground">· {channelNames[t.channel]} / {t.kind === 'private' ? '私聊' : t.kind === 'group' ? '群' : t.kind === 'legacy' ? '原有目标' : 'Webhook'}{!t.available && ' · 当前不可用'}</span></p>
          {t.last_result && <p className="text-sm">最近发送：{t.last_result.success ? '成功' : channelSendError(t.last_result)} {t.last_result.at && new Date(t.last_result.at).toLocaleString()}</p>}
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={busy || !t.available} onClick={() => void action(async () => {
              const r = await channelRequest<ChannelSendResult>('POST', `/targets/${t.id}/test`);
              if (!r.success) { await refresh(); throw new Error(channelSendError(r)); } setFeedback('测试消息已发送');
            })}>测试推送</Button>
            <Button variant="outline" disabled={busy} onClick={() => { setEditing(t.id); setName(t.name); setUrl(''); }}>编辑</Button>
            <Button variant="outline" disabled={busy} onClick={() => { if (window.confirm('删除目标后，引用它的任务将无法推送。继续？')) void action(async () => { await channelRequest('DELETE', `/targets/${t.id}`); }); }}>删除</Button>
          </div>
        </div>)}
      </section>
      <form className="rounded-xl border p-4 space-y-3" onSubmit={e => { e.preventDefault(); void action(async () => {
        await channelRequest(editing ? 'PATCH' : 'POST', editing ? `/targets/${editing}` : '/webhooks', { name, url });
        setEditing(null); setName(''); setUrl(''); setFeedback('已保存');
      }); }}>
        <h3 className="font-semibold">{editing ? '编辑接收目标' : '添加 Webhook'}</h3>
        <label className="block text-sm">备注<Input required maxLength={100} value={name} onChange={e => setName(e.target.value)} /></label>
        {(!editing || data?.targets.find(t => t.id === editing)?.channel === 'webhook') && <label className="block text-sm">Webhook 地址<Input type="url" required={!editing} value={url} onChange={e => setUrl(e.target.value)} placeholder={editing ? '留空保留现有地址' : 'https://…'} /></label>}
        <Button disabled={busy || (!editing && !data?.channels.find(c => c.channel === 'webhook')?.available)} type="submit">保存</Button>
        {editing && <Button type="button" variant="outline" onClick={() => { setEditing(null); setName(''); setUrl(''); }}>取消编辑</Button>}
      </form>
    </>}
  </div>;
}
