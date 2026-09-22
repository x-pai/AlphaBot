import React from 'react';
import { TaskInfo } from '@/types';
import { format } from 'date-fns';
import { Bot, Loader2, MessageSquare, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';

interface Session {
  id: string;
  title: string;
  last_updated: string;
  message_count: number;
}

interface AgentRunSidebarProps {
  activeView: 'conversation' | 'automation';
  currentSession: string | null;
  automationLabel: string;
  automationTasks: TaskInfo[];
  selectedAutomationId: string | null;
  onSelectAutomation: (task: TaskInfo) => void;
  onNewAutomation: () => void;
  canAccessAutomation?: boolean;
  isFetchingSessions: boolean;
  sessions: Session[];
  onNewChat: () => void;
  onOpenAutomation: () => void;
  onRefresh: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string, e: React.MouseEvent) => void;
}

export function AgentRunSidebar({
  activeView,
  currentSession,
  automationLabel, automationTasks, selectedAutomationId, onSelectAutomation, onNewAutomation,
  canAccessAutomation = false,
  isFetchingSessions,
  sessions,
  onNewChat,
  onOpenAutomation,
  onRefresh,
  onSelectSession,
  onDeleteSession,
}: AgentRunSidebarProps) {
  const visibleSessions = sessions.slice(0, 20);

  const handleSessionKeyDown = (event: React.KeyboardEvent<HTMLDivElement>, sessionId: string) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onSelectSession(sessionId);
    }
  };

  return (
    <aside className="flex h-full min-h-0 flex-col bg-background/95 text-foreground backdrop-blur">
      <div className="px-4 py-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Runs</p>
            <h2 className="mt-2 text-[1.05rem] font-semibold tracking-[-0.02em] text-foreground">任务工作台</h2>
          </div>
          <button
            type="button"
            className="rounded-xl p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            onClick={onRefresh}
            aria-label="刷新任务列表"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
        <Button variant="outline" className="w-full justify-start gap-2 rounded-2xl border-0 bg-muted/70 text-foreground shadow-none hover:bg-muted" onClick={onNewChat}>
          <Plus className="h-4 w-4" />
          新建对话
        </Button>
        {canAccessAutomation ? (
          <button
            type="button"
            className={`mt-3 flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left transition-colors ${
              activeView === 'automation'
                ? 'bg-primary/8 text-foreground'
                : 'text-foreground hover:bg-muted/70'
            }`}
            onClick={onOpenAutomation}
          >
            <span className={`rounded-xl p-2 ${activeView === 'automation' ? 'bg-primary/12 text-primary' : 'bg-muted text-muted-foreground'}`}>
              <Bot className="h-4 w-4" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium">自动化</span>
              <span className="mt-1 block truncate text-xs text-muted-foreground">{automationLabel}</span>
            </span>
          </button>
        ) : null}
      </div>

      <ScrollArea className="min-h-0 flex-1">
        {canAccessAutomation && <div className="px-4 pb-4"><div className="mb-2 flex items-center justify-between text-xs text-muted-foreground"><span>自动化任务</span><button onClick={onNewAutomation} className="rounded-lg p-2 hover:bg-muted" aria-label="新建自动化"><Plus className="h-4 w-4" /></button></div><div className="space-y-1">{automationTasks.map(task => <button key={task.task_id} onClick={() => onSelectAutomation(task)} className={`flex w-full items-center justify-between gap-3 rounded-xl px-3 py-3 text-left text-sm ${activeView === 'automation' && selectedAutomationId === task.task_id ? 'bg-primary/10 text-primary' : 'hover:bg-muted'}`}><span className="truncate">{task.description}</span><span className="shrink-0 text-xs text-muted-foreground">{task.is_enabled ? String(task.params?.daily_time || '定时') : '已暂停'}</span></button>)}</div></div>}

        <div className="p-3 pr-5">
        <div className="sticky top-0 z-10 mb-2 flex items-center justify-between px-1 py-1.5 backdrop-blur supports-[backdrop-filter]:bg-background/80">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">对话</div>
          <div className="text-[11px] text-muted-foreground">最近 20 条</div>
        </div>
        {isFetchingSessions ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : visibleSessions.length > 0 ? (
          <div className="space-y-1">
            {visibleSessions.map((session) => {
              const isActive = activeView === 'conversation' && currentSession === session.id;
              return (
                <div
                  key={session.id}
                  role="button"
                  tabIndex={0}
                  className={`w-full rounded-2xl px-3 py-2.5 text-left transition-colors ${
                    isActive
                      ? 'bg-primary/8 text-foreground'
                      : 'text-foreground hover:bg-muted/70'
                  }`}
                  onClick={() => onSelectSession(session.id)}
                  onKeyDown={(event) => handleSessionKeyDown(event, session.id)}
                  title={session.title}
                  aria-pressed={isActive}
                >
                  <div className="grid grid-cols-[auto_minmax(0,1fr)_36px] items-start gap-3">
                    <div className={`mt-0.5 rounded-xl p-2 ${isActive ? 'bg-primary/12 text-primary' : 'bg-muted text-muted-foreground'}`}>
                      <MessageSquare className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 pr-1">
                      <div className="truncate text-[15px] font-medium leading-6">{session.title}</div>
                      <div className="mt-1 truncate text-[12px] leading-5 text-muted-foreground">
                        {session.last_updated ? format(new Date(session.last_updated), 'MM/dd HH:mm') : '刚刚创建'}
                        {' · '}
                        {session.message_count} 条记录
                      </div>
                    </div>
                    <button
                      type="button"
                      className="relative z-10 mt-0.5 flex h-9 w-9 items-center justify-center self-start rounded-lg text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10 dark:hover:text-red-300"
                      onClick={(e) => onDeleteSession(session.id, e)}
                      aria-label="删除会话"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="rounded-2xl bg-muted/40 p-4 text-sm text-muted-foreground">
            还没有历史任务。新建一个任务，让 agent 开始分析。
          </div>
        )}
        </div>
      </ScrollArea>
    </aside>
  );
}
