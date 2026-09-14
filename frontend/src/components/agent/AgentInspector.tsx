import React from 'react';
import { Bot, Cable, CheckCircle2, Clock3, Globe, RefreshCw, Save, Send, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ExternalMcpServerInfo } from '@/types/user';

export interface AgentSkillOption {
  value: string;
  label: string;
  description: string;
  kind?: string;
}

export interface AutomationConfig {
  model: string | null;
  taskName: string;
  dailyTime: string;
  timezone: string;
  skillName: string;
  promptTemplate: string;
  enableWebSearch: boolean;
  publishTitle: string;
  publishCollectionSlug: string;
  publishSlug: string;
  selectedMcpServerIds: string[];
  notifyChannelType: string;
  notifyChannelChatId: string;
}

interface AccountContext {
  id: number;
  provider: string;
  name?: string;
}

interface AgentInspectorProps {
  embedded?: boolean;
  selectedAccount?: AccountContext | null;
  config: AutomationConfig;
  skillOptions: AgentSkillOption[];
  externalMcpServers: ExternalMcpServerInfo[];
  isSaving: boolean;
  isRunning: boolean;
  savedTaskId: string | null;
  publishUrl: string | null;
  feedbackMessage: string | null;
  automationTasks?: Array<{
    task_id: string;
    description: string;
    status?: string;
    current_stage?: string | null;
    next_run?: string;
  }>;
  taskStatus?: string | null;
  taskStage?: string | null;
  taskStatusDetail?: string | null;
  nextRun?: string | null;
  lastRun?: string | null;
  stageHistory?: Array<{
    stage: string;
    detail?: string | null;
    timestamp: string;
  }>;
  isRefreshingSkills?: boolean;
  onConfigChange: (updates: Partial<AutomationConfig>) => void;
  onToggleMcpServer: (serverId: string) => void;
  onRefreshSkills: () => void;
  onSave: () => void;
  onRunNow: () => void;
  onSelectTask?: (taskId: string) => void;
}

export function AgentInspector({
  embedded = false,
  selectedAccount,
  config,
  skillOptions,
  externalMcpServers,
  isSaving,
  isRunning,
  savedTaskId,
  publishUrl,
  feedbackMessage,
  automationTasks = [],
  taskStatus,
  taskStage,
  taskStatusDetail,
  nextRun,
  lastRun,
  stageHistory = [],
  isRefreshingSkills = false,
  onConfigChange,
  onToggleMcpServer,
  onRefreshSkills,
  onSave,
  onRunNow,
  onSelectTask,
}: AgentInspectorProps) {
  const isFailureStage = (stage?: string | null) =>
    stage === 'notify_failed' || stage === 'failed';

  return (
    <div className={embedded ? 'flex h-full min-h-0 flex-col' : 'hidden h-full min-h-0 xl:block xl:w-[320px] 2xl:w-[348px]'}>
      <div className={embedded ? 'flex h-full min-h-0 flex-col' : 'flex h-full min-h-0 flex-col border-l border-border/70 bg-background/72 pl-3'}>
        <div className={`mb-3 rounded-[22px] border border-border/70 bg-card/95 px-4 py-3 shadow-[0_8px_20px_rgba(15,23,42,0.05)] backdrop-blur ${embedded ? '' : ''}`}>
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Automation</p>
          <h2 className="mt-1 text-[0.95rem] font-semibold tracking-[-0.02em] text-foreground">Skill / MCP / Publish</h2>
        </div>

        <div className="min-h-0 flex-1 space-y-3 overflow-auto rounded-[22px] border border-border/70 bg-background/92 p-3 shadow-[0_8px_24px_rgba(15,23,42,0.05)] backdrop-blur">
          {automationTasks.length > 0 && (
            <section className="rounded-[18px] border border-border/80 bg-card/95 p-3">
              <div className="mb-2 flex items-center gap-2 text-[13px] font-medium text-foreground">
                <Bot className="h-4 w-4" />
                自动化任务
              </div>
              <div className="space-y-2">
                {automationTasks.map((task) => {
                  const isActive = task.task_id === savedTaskId;
                  return (
                    <button
                      key={task.task_id}
                      type="button"
                      onClick={() => onSelectTask?.(task.task_id)}
                      className={`w-full rounded-xl px-3 py-2 text-left transition-colors ${
                        isActive ? 'bg-primary/8 text-foreground' : 'bg-background text-foreground hover:bg-muted'
                      }`}
                    >
                      <div className="truncate text-[12px] font-medium">{task.description}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
                        <span>{task.status || 'pending'}</span>
                        {task.current_stage ? <span>· {task.current_stage}</span> : null}
                        {task.next_run ? <span>· {new Date(task.next_run).toLocaleString()}</span> : null}
                      </div>
                    </button>
                  );
                })}
              </div>
            </section>
          )}

          <section className="rounded-[18px] border border-border/80 bg-card/95 p-3">
            <div className="mb-2 flex items-center gap-2 text-[13px] font-medium text-foreground">
              <CheckCircle2 className="h-4 w-4" />
              当前状态
            </div>
            <div className="grid grid-cols-2 gap-2 text-[12px]">
              <div className="rounded-xl border border-border bg-background px-3 py-2">
                <div className="text-[11px] text-muted-foreground">任务状态</div>
                <div className="mt-1 text-foreground">{taskStatus || '未保存'}</div>
              </div>
              <div className="rounded-xl border border-border bg-background px-3 py-2">
                <div className="text-[11px] text-muted-foreground">当前阶段</div>
                <div className={`mt-1 truncate ${isFailureStage(taskStage) ? 'text-red-500' : 'text-foreground'}`}>
                  {taskStage || '未开始'}
                </div>
              </div>
              <div className="rounded-xl border border-border bg-background px-3 py-2">
                <div className="text-[11px] text-muted-foreground">下次运行</div>
                <div className="mt-1 text-foreground">{nextRun || '未设定'}</div>
              </div>
              <div className="rounded-xl border border-border bg-background px-3 py-2">
                <div className="text-[11px] text-muted-foreground">最近执行</div>
                <div className="mt-1 text-foreground">{lastRun || '暂无'}</div>
              </div>
            </div>
            {taskStatusDetail && (
              <div className={`mt-2 rounded-xl border border-border bg-background px-3 py-2 text-[11px] leading-5 ${
                isFailureStage(taskStage) ? 'text-red-500' : 'text-muted-foreground'
              }`}>
                {taskStatusDetail}
              </div>
            )}
            {savedTaskId && (
              <div className="mt-2 rounded-xl border border-border bg-background px-3 py-2 text-[11px] leading-5 text-muted-foreground">
                任务 ID：{savedTaskId}
              </div>
            )}
            {stageHistory.length > 0 && (
              <div className="mt-2 space-y-2">
                {stageHistory.slice(-4).reverse().map((item) => (
                  <div key={`${item.stage}-${item.timestamp}`} className="rounded-xl border border-border bg-background px-3 py-2">
                    <div className="flex items-center justify-between gap-2 text-[11px]">
                      <span className={`font-medium ${isFailureStage(item.stage) ? 'text-red-500' : 'text-foreground'}`}>{item.stage}</span>
                      <span className="text-muted-foreground">{new Date(item.timestamp).toLocaleTimeString()}</span>
                    </div>
                    {item.detail && (
                      <div className={`mt-1 text-[11px] leading-5 ${isFailureStage(item.stage) ? 'text-red-500' : 'text-muted-foreground'}`}>
                        {item.detail}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="rounded-[18px] border border-border/80 bg-card/95 p-3">
            <div className="mb-2 flex items-center gap-2 text-[13px] font-medium text-foreground">
              <Clock3 className="h-4 w-4" />
              定时
            </div>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-[11px] text-muted-foreground">任务名称</label>
                <input
                  value={config.taskName}
                  onChange={(e) => onConfigChange({ taskName: e.target.value })}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] text-foreground outline-none"
                  placeholder="例如：每日晨报"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="mb-1 block text-[11px] text-muted-foreground">每日执行时间</label>
                  <input
                    type="time"
                    value={config.dailyTime}
                    onChange={(e) => onConfigChange({ dailyTime: e.target.value })}
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] text-foreground outline-none"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] text-muted-foreground">时区</label>
                  <input
                    value={config.timezone}
                    onChange={(e) => onConfigChange({ timezone: e.target.value })}
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] text-foreground outline-none"
                    placeholder="从环境变量读取默认时区"
                  />
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-[18px] border border-border/80 bg-card/95 p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-[13px] font-medium text-foreground">
                <Sparkles className="h-4 w-4" />
                Skill
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 rounded-xl px-2 text-[11px] text-muted-foreground"
                onClick={onRefreshSkills}
                disabled={isRefreshingSkills}
              >
                <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${isRefreshingSkills ? 'animate-spin' : ''}`} />
                刷新
              </Button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-[11px] text-muted-foreground">执行 Skill</label>
                <select
                  value={config.skillName}
                  onChange={(e) => onConfigChange({ skillName: e.target.value })}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] text-foreground outline-none"
                >
                  {skillOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-[11px] leading-5 text-muted-foreground">
                  {skillOptions.find((option) => option.value === config.skillName)?.description}
                </p>
                <p className="mt-1 text-[11px] leading-5 text-muted-foreground">
                  自动化页只展示当前已启用的 Skill。新增本地 Skill 后可在这里手动刷新。
                </p>
              </div>
              <div>
                <label className="mb-1 block text-[11px] text-muted-foreground">Prompt 模板</label>
                <textarea
                  value={config.promptTemplate}
                  onChange={(e) => onConfigChange({ promptTemplate: e.target.value })}
                  className="min-h-[120px] w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] leading-5 text-foreground outline-none"
                  placeholder="例如：请基于今天的市场环境生成一份 A 股晨报。日期：{date}"
                />
                <p className="mt-1 text-[11px] text-muted-foreground">可使用变量：<code>{'{date}'}</code>、<code>{'{date_compact}'}</code>、<code>{'{datetime}'}</code>、<code>{'{datetime_compact}'}</code></p>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[12px]">
                <div className="rounded-xl border border-border bg-background px-3 py-2">
                  <div className="text-[11px] text-muted-foreground">模型</div>
                  <div className="mt-1 text-foreground">{config.model || '默认模型'}</div>
                </div>
                <div className="rounded-xl border border-border bg-background px-3 py-2">
                  <div className="text-[11px] text-muted-foreground">账户上下文</div>
                  <div className="mt-1 text-foreground">
                    {selectedAccount ? `${selectedAccount.name || '未命名账户'} · ${selectedAccount.provider}` : '未绑定'}
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-[18px] border border-border/80 bg-card/95 p-3">
            <div className="mb-2 flex items-center gap-2 text-[13px] font-medium text-foreground">
              <Cable className="h-4 w-4" />
              MCP
            </div>
            <div className="space-y-2">
              <label className="flex items-center gap-2 rounded-xl border border-border bg-background px-3 py-2 text-[12px] text-foreground">
                <input
                  type="checkbox"
                  checked={config.enableWebSearch}
                  onChange={(e) => onConfigChange({ enableWebSearch: e.target.checked })}
                />
                启用联网搜索
              </label>
              {externalMcpServers.length > 0 ? (
                externalMcpServers.map((server) => {
                  const checked = config.selectedMcpServerIds.includes(server.id);
                  return (
                    <label key={server.id} className="flex items-start gap-2 rounded-xl border border-border bg-background px-3 py-2 text-[12px] text-foreground">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => onToggleMcpServer(server.id)}
                      />
                      <div className="min-w-0">
                        <div className="font-medium">{server.id}</div>
                        <div className="mt-0.5 text-[11px] leading-5 text-muted-foreground">
                          {server.tool_count} 个工具 · {server.base_url}
                        </div>
                      </div>
                    </label>
                  );
                })
              ) : (
                <div className="rounded-xl border border-dashed border-border bg-background px-3 py-2 text-[11px] leading-5 text-muted-foreground">
                  当前没有可选的外部 MCP 服务。第一版会先按已选 Skill 和联网能力运行。
                </div>
              )}
            </div>
          </section>

          <section className="rounded-[18px] border border-border/80 bg-card/95 p-3">
            <div className="mb-2 flex items-center gap-2 text-[13px] font-medium text-foreground">
              <Globe className="h-4 w-4" />
              Publish
            </div>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-[11px] text-muted-foreground">页面标题</label>
                <input
                  value={config.publishTitle}
                  onChange={(e) => onConfigChange({ publishTitle: e.target.value })}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] text-foreground outline-none"
                  placeholder="例如：{date} · {brief}"
                />
                <p className="mt-1 text-[11px] text-muted-foreground">支持变量：<code>{'{date}'}</code>、<code>{'{brief}'}</code></p>
              </div>
              <div>
                <label className="mb-1 block text-[11px] text-muted-foreground">合集路径</label>
                <input
                  value={config.publishCollectionSlug}
                  onChange={(e) => onConfigChange({ publishCollectionSlug: e.target.value })}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] text-foreground outline-none"
                  placeholder="daily-market-brief"
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] text-muted-foreground">条目路径 Slug</label>
                <input
                  value={config.publishSlug}
                  onChange={(e) => onConfigChange({ publishSlug: e.target.value })}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] text-foreground outline-none"
                  placeholder="review-{date_compact}"
                />
              </div>
              <p className="text-[11px] leading-5 text-muted-foreground">
                公开路径会生成成 <code>/published/{config.publishCollectionSlug || 'daily-market-brief'}/{config.publishSlug || 'review-{date_compact}'}</code>。
              </p>
              {publishUrl && (
                <a href={publishUrl} target="_blank" rel="noreferrer" className="block rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 text-[11px] text-primary">
                  已发布：{publishUrl}
                </a>
              )}
            </div>
          </section>

          <section className="rounded-[18px] border border-border/80 bg-card/95 p-3">
            <div className="mb-2 flex items-center gap-2 text-[13px] font-medium text-foreground">
              <Send className="h-4 w-4" />
              推送通知
            </div>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-[11px] text-muted-foreground">通知渠道</label>
                <select
                  value={config.notifyChannelType}
                  onChange={(e) => onConfigChange({ notifyChannelType: e.target.value })}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] text-foreground outline-none"
                >
                  <option value="">不推送</option>
                  <option value="feishu">飞书</option>
                  <option value="telegram">Telegram</option>
                  <option value="webhook">Webhook</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[11px] text-muted-foreground">
                  {config.notifyChannelType === 'webhook' ? 'Webhook URL' : 'Chat ID'}
                </label>
                <input
                  value={config.notifyChannelChatId}
                  onChange={(e) => onConfigChange({ notifyChannelChatId: e.target.value })}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] text-foreground outline-none"
                  placeholder={config.notifyChannelType === 'webhook' ? 'https://example.com/webhook' : '推送目标 chat_id'}
                />
                <p className="mt-1 text-[11px] leading-5 text-muted-foreground">
                  配置后，日报发布成功会自动推送标题和访问链接。Webhook 会以 JSON
                  <code className="mx-1">{'{"text":"..."}'}</code>
                  发送。
                </p>
              </div>
            </div>
          </section>

          <section className="rounded-[18px] border border-border/80 bg-card/95 p-3">
            <div className="mb-3 flex items-center gap-2 text-[13px] font-medium text-foreground">
              <Bot className="h-4 w-4" />
              操作
            </div>
            <div className="space-y-2">
              <Button className="h-9 w-full gap-2 rounded-xl" disabled={isSaving} onClick={onSave}>
                <Save className="h-4 w-4" />
                {isSaving ? '保存中' : '保存自动化任务'}
              </Button>
              <Button variant="outline" className="h-9 w-full gap-2 rounded-xl" disabled={!savedTaskId || isRunning} onClick={onRunNow}>
                <Send className="h-4 w-4" />
                {isRunning ? '执行中' : '立即运行并发布'}
              </Button>
              {savedTaskId && (
                <div className="rounded-xl bg-muted/70 px-3 py-2 text-[11px] leading-5 text-muted-foreground">
                  当前任务 ID：{savedTaskId}
                </div>
              )}
              {feedbackMessage && (
                <div className="rounded-xl bg-muted/70 px-3 py-2 text-[11px] leading-5 text-foreground">
                  {feedbackMessage}
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
