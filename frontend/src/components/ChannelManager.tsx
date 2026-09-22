'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertCircle, ArrowRight, Check, CheckCircle2, ChevronRight, Clock3, Copy,
  Link2, Loader2, MessageCircle, Pencil, Plus, RefreshCw, Send, ShieldCheck,
  Trash2, Unplug, Users, Webhook, X,
} from 'lucide-react';
import { useAuth } from '@/lib/contexts/AuthContext';
import {
  channelNames, channelRequest, ChannelOverview, ChannelStatus, ChannelTarget,
  loadChannels, ChannelSendResult, channelSendError,
} from '@/lib/channels';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';

const channelOrder = ['qq', 'telegram', 'feishu', 'webhook'];
const channelLooks: Record<string, string> = {
  qq: 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-300',
  telegram: 'bg-sky-50 text-sky-600 dark:bg-sky-500/10 dark:text-sky-300',
  feishu: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300',
  webhook: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300',
};
const subtleButton = 'rounded-lg hover:bg-muted hover:text-foreground dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800';
const panel = 'rounded-2xl border border-border/80 bg-card text-slate-900 shadow-sm dark:border-slate-700 dark:text-slate-100';
const modalStyle = 'max-h-[90dvh] w-[calc(100%-2rem)] overflow-y-auto rounded-2xl dark:border-slate-700 dark:text-slate-100 sm:rounded-2xl';

type BindingCode = { code: string; code_id: number; expires_at: string };
type Modal =
  | { type: 'bind'; channel: string; kind: 'private' | 'group' }
  | { type: 'edit'; target?: ChannelTarget }
  | { type: 'delete'; target: ChannelTarget }
  | { type: 'unbind'; binding: ChannelOverview['bindings'][number] };
type Notice = { kind: 'success' | 'error'; text: string };

function ChannelIcon({ channel, small = false }: { channel: string; small?: boolean }) {
  const Icon = channel === 'webhook' ? Webhook : channel === 'telegram' ? Send : channel === 'feishu' ? Link2 : MessageCircle;
  return <span className={`inline-flex shrink-0 items-center justify-center rounded-xl ${small ? 'h-9 w-9' : 'h-11 w-11'} ${channelLooks[channel]}`}><Icon className={small ? 'h-4 w-4' : 'h-5 w-5'} aria-hidden="true" /></span>;
}

function Badge({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: 'good' | 'warn' | 'neutral' }) {
  const style = tone === 'good'
    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
    : tone === 'warn' ? 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300' : 'bg-muted text-muted-foreground';
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ${style}`}><span className="h-1.5 w-1.5 rounded-full bg-current" />{children}</span>;
}

function systemStatus(status: ChannelStatus): { text: string; tone: 'good' | 'warn' | 'neutral' } {
  if (!status.enabled) return { text: '未启用', tone: 'neutral' };
  if (!status.configured) return { text: '待配置', tone: 'warn' };
  if (status.channel === 'qq') return { text: status.connection, tone: status.connection === '已连接' ? 'good' : 'warn' };
  return { text: '已配置', tone: 'good' };
}

function errorText(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : error instanceof Error ? error.message : '操作失败，请稍后重试。';
}

function formatDate(value?: string) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export default function ChannelManager() {
  const { user, isReady } = useAuth();
  const userId = user?.id;
  const [data, setData] = useState<ChannelOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selected, setSelected] = useState('qq');
  const [notice, setNotice] = useState<Notice | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const mutationLock = useRef(false);
  const modalTrigger = useRef<HTMLElement | null>(null);
  const [modal, setModal] = useState<Modal | null>(null);
  const [modalError, setModalError] = useState('');
  const [code, setCode] = useState<BindingCode | null>(null);
  const [bound, setBound] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [copied, setCopied] = useState('');
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');

  const refresh = useCallback(async () => {
    const result = await loadChannels();
    setData(result);
    return result;
  }, []);

  useEffect(() => {
    let active = true;
    setData(null);
    if (!userId) { setLoading(false); return; }
    setLoading(true);
    loadChannels().then(result => { if (active) setData(result); })
      .catch(e => { if (active) setNotice({ kind: 'error', text: errorText(e) }); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [userId]); // Account changes must not reuse another user's destinations.

  useEffect(() => {
    if (!notice || notice.kind !== 'success') return;
    const timer = setTimeout(() => setNotice(null), 6000);
    return () => clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(''), 2000);
    return () => clearTimeout(timer);
  }, [copied]);

  useEffect(() => {
    if (!code || modal?.type !== 'bind' || bound) return;
    let stopped = false;
    let checking = false;
    const clock = setInterval(() => setNow(Date.now()), 1000);
    const poll = setInterval(async () => {
      if (checking || Date.now() >= new Date(code.expires_at).getTime()) return;
      checking = true;
      try {
        const result = await channelRequest<{ status: 'pending' | 'consumed' | 'expired' }>('GET', `/binding-codes/${code.code_id}`);
        if (stopped) return;
        setModalError('');
        if (result.status === 'consumed') {
          setBound(true);
          await refresh();
        }
      } catch {
        if (!stopped) setModalError('暂时无法获取绑定状态，请检查网络；恢复后会自动继续确认。');
      } finally { checking = false; }
    }, 3000);
    return () => { stopped = true; clearInterval(clock); clearInterval(poll); };
  }, [code, modal?.type, bound, refresh]);

  async function run(key: string, operation: () => Promise<void>, inModal = false) {
    if (mutationLock.current) return;
    mutationLock.current = true;
    setPending(key);
    if (inModal) setModalError(''); else setNotice(null);
    try { await operation(); }
    catch (e) {
      if (inModal) setModalError(errorText(e));
      else setNotice({ kind: 'error', text: errorText(e) });
    } finally { mutationLock.current = false; setPending(null); }
  }

  function openModal(next: Modal) {
    modalTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setModal(next); setModalError(''); setCode(null); setBound(false); setCopied('');
    setName(next.type === 'edit' ? next.target?.name || '' : ''); setUrl('');
  }

  async function generateCode() {
    if (modal?.type !== 'bind') return;
    await run('code', async () => {
      const result = await channelRequest<BindingCode>('POST', '/binding-codes', { channel: modal.channel, kind: modal.kind });
      setCode(result); setNow(Date.now()); setBound(false);
    }, true);
  }

  async function copy(text: string, key: string) {
    try { await navigator.clipboard.writeText(text); setCopied(key); }
    catch {
      if (modal) setModalError('复制失败，请选中文字手动复制。');
      else setNotice({ kind: 'error', text: '复制失败，请选中文字手动复制。' });
    }
  }

  const current = data?.channels.find(c => c.channel === selected);
  const bindings = data?.bindings.filter(b => b.channel === selected) || [];
  const hasBinding = bindings.some(b => b.current_bot);
  const targets = data?.targets.filter(t => t.channel === selected) || [];
  const remaining = code ? Math.max(0, Math.ceil((new Date(code.expires_at).getTime() - now) / 1000)) : 0;
  const expired = !!code && remaining === 0;
  const busy = pending !== null;

  if (!isReady || loading) return <div aria-busy="true" aria-label="正在加载消息渠道" className="space-y-6"><div className="h-32 animate-pulse rounded-2xl bg-muted" /><div className="h-80 animate-pulse rounded-2xl bg-muted" /><span className="sr-only">正在加载消息渠道</span></div>;
  if (!user) return <div className={`${panel} p-10 text-center`}><ShieldCheck className="mx-auto mb-3 h-8 w-8 text-muted-foreground" /><h2 className="font-semibold">登录后管理你的消息渠道</h2><p className="mt-2 text-sm text-muted-foreground">绑定个人账号，接收任务结果与预警通知。</p><a href="/login" className="mt-5 inline-block text-sm font-medium text-primary">前往登录 →</a></div>;

  return <div className="space-y-6">
    <div className="flex items-center justify-between gap-4">
      <p className="text-sm text-muted-foreground">让任务结果和预警，送到你常用的地方。</p>
      <Button variant="outline" size="sm" className={`shrink-0 gap-2 ${subtleButton}`} disabled={refreshing || busy} onClick={async () => {
        setRefreshing(true);
        try { await refresh(); setNotice({ kind: 'success', text: '渠道状态已更新' }); }
        catch (e) { setNotice({ kind: 'error', text: errorText(e) }); }
        finally { setRefreshing(false); }
      }}><RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />刷新</Button>
    </div>

    {notice && <div role={notice.kind === 'error' ? 'alert' : 'status'} className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${notice.kind === 'error' ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-900/60 dark:bg-red-950/20 dark:text-red-300' : 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/20 dark:text-emerald-300'}`}>
      {notice.kind === 'error' ? <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />}
      <p className="min-w-0 flex-1 break-words">{notice.text}</p><button aria-label="关闭提示" className="rounded p-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => setNotice(null)}><X className="h-4 w-4" /></button>
    </div>}

    {user.is_admin && data && <section className={`${panel} overflow-hidden`} aria-labelledby="system-channels-title">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 px-5 py-4">
        <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-muted-foreground" /><h2 id="system-channels-title" className="text-sm font-semibold">系统消息渠道</h2><span className="rounded-md bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">管理员</span></div>
        <span className="text-xs text-muted-foreground">机器人凭证与开关由部署配置管理</span>
      </div>
      <div className="grid grid-cols-2 gap-px bg-border/60 xl:grid-cols-4">
        {data.channels.map(c => { const status = systemStatus(c); return <div key={c.channel} className="flex items-center gap-3 bg-card px-3 py-4 sm:px-5"><ChannelIcon channel={c.channel} small /><div className="min-w-0 flex-1"><p className="mb-1.5 text-sm font-medium">{channelNames[c.channel]}</p><Badge tone={status.tone}>{status.text}</Badge></div></div>; })}
      </div>
    </section>}

    {data && <section className={`${panel} overflow-hidden`} aria-labelledby="personal-channels-title">
      <header className="px-5 pt-6 sm:px-6"><div className="flex flex-wrap items-center gap-3"><h2 id="personal-channels-title" className="text-lg font-semibold tracking-tight">个人渠道管理</h2><span className="text-xs text-muted-foreground">{data.targets.length} 个接收目标</span></div><p className="mt-1.5 text-sm text-muted-foreground">绑定账号或添加接收地址，供每日任务和预警使用。</p></header>
      <div className="mt-5 flex gap-1 overflow-x-auto border-b border-border/70 px-3 sm:px-5" role="tablist" aria-label="选择消息渠道">
        {channelOrder.map(c => <button key={c} id={`channel-tab-${c}`} role="tab" type="button" aria-selected={selected === c} aria-controls="channel-panel" tabIndex={selected === c ? 0 : -1} onKeyDown={e => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
          e.preventDefault(); const index = channelOrder.indexOf(c);
          const next = e.key === 'Home' ? channelOrder[0] : e.key === 'End' ? channelOrder[3] : channelOrder[(index + (e.key === 'ArrowRight' ? 1 : 3)) % 4];
          setSelected(next); document.getElementById(`channel-tab-${next}`)?.focus();
        }} onClick={() => setSelected(c)} className={`relative flex shrink-0 items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring ${selected === c ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:bg-muted/50 hover:text-foreground'}`}>{channelNames[c]}<span className={`rounded-md px-1.5 py-0.5 text-[10px] ${selected === c ? 'bg-primary/10' : 'bg-muted'}`}>{data.targets.filter(t => t.channel === c).length}</span></button>)}
      </div>

      <div id="channel-panel" role="tabpanel" aria-labelledby={`channel-tab-${selected}`} className="space-y-6 p-5 sm:p-6">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3"><ChannelIcon channel={selected} /><div><div className="flex items-center gap-2"><h3 className="font-semibold">{channelNames[selected]}</h3><Badge tone={!current?.available ? 'neutral' : selected === 'webhook' || hasBinding ? 'good' : 'warn'}>{!current?.available ? '暂不可用' : selected === 'webhook' ? '可添加' : hasBinding ? '账号已绑定' : '待绑定'}</Badge></div><p className="mt-1 text-xs leading-5 text-muted-foreground">{!current?.available ? '此渠道暂不可用，请联系管理员。' : selected === 'webhook' ? '将通知发送到你的服务或群机器人。' : hasBinding ? '个人私聊和群聊目标，都可以用于接收通知。' : '先绑定个人账号，再添加需要接收通知的群。'}</p></div></div>
          <div className="flex shrink-0 flex-wrap gap-2">
            {selected === 'webhook' ? <Button size="sm" className="gap-1.5 rounded-lg" disabled={!current?.available || busy} onClick={() => openModal({ type: 'edit' })}><Plus className="h-4 w-4" />添加 Webhook</Button> : <>
              <Button size="sm" variant={hasBinding ? 'outline' : 'primary'} className={`gap-1.5 ${subtleButton}`} disabled={!current?.available || busy} onClick={() => openModal({ type: 'bind', channel: selected, kind: 'private' })}><Link2 className="h-3.5 w-3.5" />{hasBinding ? '绑定其他账号' : '绑定账号'}</Button>
              <Button size="sm" variant="outline" className={`gap-1.5 ${subtleButton}`} title={!hasBinding ? '请先绑定个人账号' : undefined} disabled={!current?.available || !hasBinding || busy} onClick={() => openModal({ type: 'bind', channel: selected, kind: 'group' })}><Users className="h-3.5 w-3.5" />添加群目标</Button>
            </>}
          </div>
        </div>

        {bindings.length > 0 && <div className="divide-y divide-border/60 rounded-xl bg-muted/40 px-4">{bindings.map(b => <div key={b.id} className="flex items-center justify-between gap-3 py-3"><div className="flex min-w-0 items-center gap-2"><CheckCircle2 className={`h-4 w-4 shrink-0 ${b.current_bot ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-500'}`} /><span className="text-xs text-muted-foreground">{b.current_bot ? '已绑定账号' : '机器人已更换，需重新绑定'}</span><span className="truncate font-mono text-xs" title={b.external_user_id}>{b.external_user_id.length > 14 ? `${b.external_user_id.slice(0, 6)}…${b.external_user_id.slice(-4)}` : b.external_user_id}</span></div><Button variant="ghost" size="sm" className={`h-7 px-2 text-muted-foreground ${subtleButton}`} disabled={busy} onClick={() => openModal({ type: 'unbind', binding: b })}>解绑</Button></div>)}</div>}

        <div><div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-semibold">接收目标 <span className="ml-1 text-xs font-normal text-muted-foreground">{targets.length}</span></h3><span className="text-xs text-muted-foreground">仅你可管理和使用</span></div>
          {targets.length === 0 ? <div className="rounded-xl border border-dashed border-border bg-muted/20 px-5 py-10 text-center"><div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-muted"><Send className="h-5 w-5 text-muted-foreground" /></div><p className="text-sm font-medium">还没有{channelNames[selected]}接收目标</p><p className="mx-auto mt-2 max-w-sm text-xs leading-6 text-muted-foreground">{selected === 'webhook' ? '添加一个 Webhook 地址，即可接收任务结果。' : '绑定个人账号后会自动创建私聊目标，也可以添加群目标。'}</p></div> : <div className="space-y-3">{targets.map(t => <article key={t.id} className="overflow-hidden rounded-xl border border-border/80 transition-colors hover:border-primary/25 dark:border-slate-700">
            <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"><div className="flex min-w-0 items-center gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">{t.kind === 'group' ? <Users className="h-4 w-4" /> : t.kind === 'webhook' ? <Webhook className="h-4 w-4" /> : <MessageCircle className="h-4 w-4" />}</span><div className="min-w-0"><p className="truncate text-sm font-medium" title={t.name}>{t.name}</p><p className="mt-1 text-xs text-muted-foreground">{t.kind === 'private' ? '个人私聊' : t.kind === 'group' ? '群聊' : t.kind === 'legacy' ? '原有推送目标' : 'Webhook'}{!t.available && ' · 当前不可用'}</p></div></div>
              <div className="flex shrink-0 items-center gap-1.5 self-end sm:self-auto"><Button size="sm" variant="outline" className={`h-8 gap-1.5 ${subtleButton}`} disabled={busy || !t.available} onClick={() => void run(`test:${t.id}`, async () => {
                const result = await channelRequest<ChannelSendResult>('POST', `/targets/${t.id}/test`);
                await refresh();
                if (!result.success) throw new Error(channelSendError(result));
                setNotice({ kind: 'success', text: `测试消息已发送到「${t.name}」` });
              })}>{pending === `test:${t.id}` ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}{pending === `test:${t.id}` ? '发送中' : '测试推送'}</Button><Button variant="ghost" size="sm" className={`h-8 w-8 px-0 ${subtleButton}`} aria-label={`编辑 ${t.name}`} title="编辑目标" disabled={busy} onClick={() => openModal({ type: 'edit', target: t })}><Pencil className="h-3.5 w-3.5" /></Button><Button variant="ghost" size="sm" className="h-8 w-8 rounded-lg px-0 text-muted-foreground hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/30" aria-label={`删除 ${t.name}`} title="删除目标" disabled={busy} onClick={() => openModal({ type: 'delete', target: t })}><Trash2 className="h-3.5 w-3.5" /></Button></div>
            </div>
            {t.last_result && <div className={`border-t px-4 py-2.5 text-xs ${t.last_result.success ? 'border-border/60 bg-muted/20 text-muted-foreground' : 'border-red-100 bg-red-50/60 text-red-700 dark:border-red-900/40 dark:bg-red-950/10 dark:text-red-300'}`}>
              {t.last_result.success ? <p className="flex items-center gap-2"><CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />最近发送成功<span className="ml-auto tabular-nums">{formatDate(t.last_result.at)}</span></p> : <details><summary className="flex cursor-pointer list-none items-center gap-2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><AlertCircle className="h-3.5 w-3.5" />最近发送失败<span className="ml-auto">查看原因</span><ChevronRight className="h-3.5 w-3.5" /></summary><p className="mt-3 select-text break-words leading-6">{channelSendError(t.last_result)}</p><div className="mt-2 flex items-center justify-between"><span>{formatDate(t.last_result.at)}</span><button className="inline-flex items-center gap-1 rounded px-1 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => void copy(channelSendError(t.last_result!), `error:${t.id}`)}>{copied === `error:${t.id}` ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}{copied === `error:${t.id}` ? '已复制' : '复制错误详情'}</button></div></details>}
            </div>}
          </article>)}</div>}
        </div>
      </div>
    </section>}

    <Dialog open={modal !== null} onOpenChange={open => { if (!open && !busy) setModal(null); }}>
      <DialogContent className={modalStyle} onCloseAutoFocus={event => { event.preventDefault(); modalTrigger.current?.focus(); }}>
        <DialogHeader>
          <div className="mb-3">{modal?.type === 'bind' ? <ChannelIcon channel={modal.channel} /> : <span className={`inline-flex h-11 w-11 items-center justify-center rounded-xl ${modal?.type === 'edit' ? 'bg-primary/10 text-primary' : 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-300'}`}>{modal?.type === 'edit' ? <Pencil className="h-5 w-5" /> : <Unplug className="h-5 w-5" />}</span>}</div>
          <DialogTitle>{modal?.type === 'bind' ? bound ? '绑定成功' : `${modal.kind === 'group' ? '添加群目标' : '绑定账号'} · ${channelNames[modal.channel]}` : modal?.type === 'edit' ? modal.target ? '编辑接收目标' : '添加 Webhook' : modal?.type === 'delete' ? '删除接收目标？' : '解除账号绑定？'}</DialogTitle>
          <DialogDescription className="pt-1 leading-6">{modal?.type === 'bind' ? bound ? '接收目标已就绪，可以在每日任务和预警中选择。' : modal.kind === 'group' ? '使用已绑定的账号，在目标群中 @机器人发送绑定指令。' : '在对应机器人的私聊中发送绑定指令，即可关联当前账号。' : modal?.type === 'edit' ? '为目标设置一个容易识别的名称。' : modal?.type === 'delete' ? `「${modal.target.name}」将从接收目标中移除，引用它的任务将无法继续推送。` : '该机器人下的个人接收目标将一并移除，相关任务将停止推送。'}</DialogDescription>
        </DialogHeader>
        {modalError && <p role="alert" className="break-words rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-700 dark:bg-red-950/30 dark:text-red-300">{modalError}</p>}

        {modal?.type === 'bind' && <>
          {bound ? <div role="status" className="rounded-xl bg-emerald-50 px-5 py-7 text-center dark:bg-emerald-500/10"><CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600 dark:text-emerald-400" /><p className="mt-3 text-sm font-medium text-emerald-700 dark:text-emerald-300">账号与接收目标已同步</p></div> : <>
            <ol className="space-y-3 text-sm">{['生成一次性绑定码', modal.kind === 'group' ? '在目标群 @机器人发送指令' : '私聊机器人并发送指令', '等待此页面自动确认'].map((step, i) => <li key={step} className="flex items-center gap-3"><span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs ${code && i === 0 ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300' : 'bg-muted text-muted-foreground'}`}>{code && i === 0 ? <Check className="h-3 w-3" /> : i + 1}</span>{step}</li>)}</ol>
            {code && <div className="rounded-xl border border-primary/20 bg-primary/[0.03] p-4"><div className="mb-3 flex items-center justify-between gap-2 text-xs text-muted-foreground"><span>完整绑定指令</span><span className={`flex items-center gap-1 tabular-nums ${expired ? 'text-amber-600 dark:text-amber-400' : ''}`}><Clock3 className="h-3 w-3" />{expired ? '已过期' : `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')} 后过期`}</span></div><code className={`block select-all break-all font-mono text-lg font-semibold tracking-wider sm:text-xl ${expired ? 'text-muted-foreground line-through' : ''}`}>绑定 {code.code}</code><Button className={`mt-4 w-full gap-2 ${subtleButton}`} variant="outline" disabled={expired} onClick={() => void copy(`绑定 ${code.code}`, 'code')}>{copied === 'code' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}{copied === 'code' ? '指令已复制' : '复制绑定指令'}</Button></div>}
            {code && !expired && <p role="status" className="flex items-center justify-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" />等待机器人确认，无需手动刷新</p>}
          </>}
          <DialogFooter className="gap-2"><Button variant="outline" className={subtleButton} disabled={busy} onClick={() => setModal(null)}>{bound ? '完成' : '关闭'}</Button>{!bound && (!code || expired) && <Button className="gap-2 rounded-lg" disabled={busy} onClick={() => void generateCode()}>{pending === 'code' ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}{expired ? '重新生成' : '生成绑定码'}</Button>}</DialogFooter>
        </>}

        {modal?.type === 'edit' && <form className="space-y-4" onSubmit={e => {
          e.preventDefault();
          if (!name.trim()) { setModalError('请输入接收目标名称。'); return; }
          const target = modal.target;
          void run('save', async () => {
            await channelRequest(target ? 'PATCH' : 'POST', target ? `/targets/${target.id}` : '/webhooks', { name: name.trim(), url: url.trim() });
            await refresh(); setModal(null); setNotice({ kind: 'success', text: target ? '接收目标已更新' : 'Webhook 已添加，可以发送测试消息了' });
          }, true);
        }}>
          <div className="space-y-2"><label htmlFor="channel-target-name" className="text-sm font-medium">目标名称</label><Input id="channel-target-name" autoFocus required maxLength={100} value={name} onChange={e => setName(e.target.value)} placeholder="例如：我的 QQ、团队通知群" className="rounded-lg" disabled={busy} /></div>
          {(!modal.target || modal.target.channel === 'webhook') && <div className="space-y-2"><label htmlFor="channel-webhook-url" className="text-sm font-medium">Webhook 地址</label><Input id="channel-webhook-url" type="url" autoComplete="off" required={!modal.target} value={url} onChange={e => setUrl(e.target.value)} placeholder={modal.target ? '留空保留现有地址' : 'https://example.com/webhook'} className="rounded-lg" disabled={busy} /><p className="text-xs leading-5 text-muted-foreground">使用公网 HTTPS 地址。{modal.target && '已保存的完整地址不会回显。'}</p></div>}
          <DialogFooter className="gap-2 pt-2"><Button type="button" variant="outline" className={subtleButton} disabled={busy} onClick={() => setModal(null)}>取消</Button><Button type="submit" className="gap-2 rounded-lg" disabled={busy}>{pending === 'save' && <Loader2 className="h-4 w-4 animate-spin" />}{pending === 'save' ? '保存中' : '保存目标'}</Button></DialogFooter>
        </form>}

        {(modal?.type === 'delete' || modal?.type === 'unbind') && <DialogFooter className="gap-2 pt-2"><Button variant="outline" className={subtleButton} disabled={busy} autoFocus onClick={() => setModal(null)}>取消</Button><Button className="gap-2 rounded-lg bg-red-600 text-white hover:bg-red-700" disabled={busy} onClick={() => void run('remove', async () => {
          await channelRequest('DELETE', modal.type === 'delete' ? `/targets/${modal.target.id}` : `/bindings/${modal.binding.id}`);
          await refresh(); setModal(null); setNotice({ kind: 'success', text: modal.type === 'delete' ? '接收目标已删除' : '账号已解绑' });
        }, true)}>{pending === 'remove' && <Loader2 className="h-4 w-4 animate-spin" />}{modal.type === 'delete' ? '确认删除' : '确认解绑'}</Button></DialogFooter>}
      </DialogContent>
    </Dialog>
  </div>;
}
