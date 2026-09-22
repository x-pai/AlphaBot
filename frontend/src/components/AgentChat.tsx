'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Loader2, Bot, TrendingUp, BarChart2, PieChart, LineChart, Trash2 } from 'lucide-react';
import { useAuth } from '@/lib/contexts/AuthContext';
import { useAccounts } from '@/lib/contexts/AccountContext';
import { chatWithAgent, chatWithAgentStream, getAgentSessions, getAgentSessionHistory, deleteAgentSession, executeAgentTool, getAvailableModels, getAgentSkills, createTask, updateTask, runTaskNow, listExternalMcpServers, getAllTasks, deleteTask } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import { AgentMessageDisplay } from './chat/AgentMessageDisplay';
import { AgentRunSidebar } from './agent/AgentRunSidebar';
import { AgentWorkspaceHeader } from './agent/AgentWorkspaceHeader';
import { AgentInspector, AgentSkillOption, AutomationConfig } from './agent/AgentInspector';
import { AgentComposer } from './agent/AgentComposer';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { AgentArtifact, AgentRunEvent, AgentToolInvocation } from '@/types/agent';
import { TaskInfo } from '@/types';
import { ExternalMcpServerInfo } from '@/types/user';

const DEFAULT_APP_TIMEZONE = process.env.NEXT_PUBLIC_APP_TIMEZONE || 'Asia/Shanghai';

const generateId = (): string => {
  try {
    const g = globalThis as unknown as { crypto?: { randomUUID?: () => string } };
    if (g.crypto && typeof g.crypto.randomUUID === 'function') {
      return g.crypto.randomUUID();
    }
  } catch {}
  return `id-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
};

interface AgentChatProps {
  onSelectStock?: (symbol: string) => void;
}

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  toolOutputs?: string[];
}

interface Session {
  id: string;
  title: string;
  last_updated: string;
  message_count: number;
}

const createTimestamp = () => new Date().toISOString();

const extractSymbols = (text: string): string[] => {
  const matches = text.match(/\$?[A-Z]{2,5}(?:\.[A-Z]+)?/g) || [];
  return Array.from(new Set(matches.map((item) => item.replace(/^\$/, '')))).slice(0, 5);
};

const slugify = (value: string): string =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'daily-report';

const normalizeSlugTemplate = (value: string): string =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9{}_-]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'review-{date_compact}';

const toBrief = (value: string, maxLength = 44): string => {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (!normalized) return '';
  return normalized.length > maxLength ? `${normalized.slice(0, maxLength).trimEnd()}...` : normalized;
};

export default function AgentChat({ onSelectStock }: AgentChatProps) {
  void onSelectStock;
  const { isAuthenticated, user } = useAuth();
  const { selectedAccount } = useAccounts();
  const canUseWebSearch = user && user.points >= 2000;
  const canAccessAutomation = Boolean(user?.is_admin);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentSession, setCurrentSession] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'conversation' | 'automation'>('conversation');
  const [isLoading, setIsLoading] = useState(false);
  const [, setIsThinking] = useState(false);
  const [sessionList, setSessionList] = useState<Session[]>([]);
  const [showSidebar, setShowSidebar] = useState<boolean>(false);
  const [isFetchingSessions, setIsFetchingSessions] = useState<boolean>(false);
  const [isLoadingSession, setIsLoadingSession] = useState<boolean>(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState<boolean>(false);
  const [streamEnabled, setStreamEnabled] = useState<boolean>(true);
  const [streamingMessage, setStreamingMessage] = useState<string>('');
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState<Message | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<{value: string, label: string}[]>([{ value: '', label: '默认模型' }]);
  const [isRefreshingSkills, setIsRefreshingSkills] = useState(false);
  const [activeSkillName, setActiveSkillName] = useState<string | null>(null);
  const [skillOptions, setSkillOptions] = useState<AgentSkillOption[]>([
    { value: 'research', label: 'Research', description: '适合每日市场研究、热点梳理和资讯摘要。', kind: 'builtin' },
    { value: 'portfolio', label: 'Portfolio', description: '适合围绕持仓、组合和账户上下文生成输出。', kind: 'builtin' },
    { value: 'risk', label: 'Risk', description: '适合风控巡检、回撤监控和风险提示。', kind: 'builtin' },
    { value: 'general', label: 'General', description: '适合综合性任务，由通用助手执行。', kind: 'builtin' },
    { value: 'alert', label: 'Alert', description: '适合预警策略、提醒规则和触发结果整理。', kind: 'builtin' },
  ]);
  const [runEvents, setRunEvents] = useState<AgentRunEvent[]>([]);
  const [toolInvocations, setToolInvocations] = useState<AgentToolInvocation[]>([]);
  const [artifacts, setArtifacts] = useState<AgentArtifact[]>([]);
  const [externalMcpServers, setExternalMcpServers] = useState<ExternalMcpServerInfo[]>([]);
  const [automationOverview, setAutomationOverview] = useState(true);
  const [templatePicker, setTemplatePicker] = useState(false);
  const automationDirty = useRef(false);
  const automationSelection = useRef<string | null>(null);
  const [automationEnabled, setAutomationEnabled] = useState(true);
  const [automationTaskId, setAutomationTaskId] = useState<string | null>(null);
  const [automationPublishUrl, setAutomationPublishUrl] = useState<string | null>(null);
  const [automationFeedback, setAutomationFeedback] = useState<string | null>(null);
  const [automationTaskInfo, setAutomationTaskInfo] = useState<TaskInfo | null>(null);
  const [automationTasks, setAutomationTasks] = useState<TaskInfo[]>([]);
  const [isDeletingAutomation, setIsDeletingAutomation] = useState(false);
  const [isSavingAutomation, setIsSavingAutomation] = useState(false);
  const [isRunningAutomation, setIsRunningAutomation] = useState(false);
  const [streamAbortController, setStreamAbortController] = useState<AbortController | null>(null);
  const [automationConfig, setAutomationConfig] = useState<AutomationConfig>({
    model: null,
    taskName: '每日市场复盘',
    dailyTime: '09:00',
    tradingDaysOnly: false,
    timezone: DEFAULT_APP_TIMEZONE,
    skillName: 'research',
    promptTemplate: '请基于 {date} 的市场环境，生成一份结构化的 A 股每日市场复盘，包含指数表现、热点板块、风险提醒、值得关注的标的与后续观察点。',
    enableWebSearch: false,
    publishTitle: '{date} · {brief}',
    publishCollectionSlug: 'daily-market-brief',
    publishSlug: 'review-{date_compact}',
    selectedMcpServerIds: [],
    notifyChannelType: '',
    notifyChannelChatId: '',
    notifyTargetId: '',
  });

  const appendRunEvent = useCallback((event: Omit<AgentRunEvent, 'id' | 'createdAt'>) => {
    setRunEvents((prev) => [
      ...prev,
      {
        id: generateId(),
        createdAt: createTimestamp(),
        ...event,
      },
    ]);
  }, []);

  const updateLatestRunEvent = useCallback(
    (
      matcher: (event: AgentRunEvent) => boolean,
      updates: Partial<Omit<AgentRunEvent, 'id' | 'createdAt'>>,
    ) => {
      setRunEvents((prev) => {
        const next = [...prev];
        const index = [...next].reverse().findIndex(matcher);
        if (index === -1) return prev;
        const actualIndex = next.length - 1 - index;
        next[actualIndex] = {
          ...next[actualIndex],
          ...updates,
        };
        return next;
      });
    },
    [],
  );

  const settleRunningEvents = useCallback((status: 'done' | 'error') => {
    setRunEvents((prev) =>
      prev.map((event) =>
        event.status === 'running'
          ? {
              ...event,
              status,
            }
          : event
      )
    );
  }, []);

  const registerArtifact = useCallback((artifact: Omit<AgentArtifact, 'id' | 'createdAt'>) => {
    setArtifacts((prev) => {
      const exists = prev.some((item) => item.kind === artifact.kind && item.title === artifact.title && item.content === artifact.content);
      if (exists) return prev;
      return [
        ...prev,
        {
          id: generateId(),
          createdAt: createTimestamp(),
          ...artifact,
        },
      ];
    });
  }, []);

  const ingestArtifactsFromText = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    registerArtifact({
      kind: 'summary',
      title: '最新分析摘要',
      content: trimmed.slice(0, 500),
    });

    extractSymbols(trimmed).forEach((symbol) => {
      registerArtifact({
        kind: 'symbol',
        title: `提及标的 ${symbol}`,
        content: symbol,
      });
    });
  }, [registerArtifact]);

  const startToolInvocation = useCallback((toolName: string, argsText?: string) => {
    const invocationId = generateId();
    setToolInvocations((prev) => [
      ...prev,
      {
        id: invocationId,
        toolName,
        status: 'running',
        argsText,
        createdAt: createTimestamp(),
        updatedAt: createTimestamp(),
      },
    ]);
    return invocationId;
  }, []);

  const finishLatestToolInvocation = useCallback((toolName: string, updates: Partial<AgentToolInvocation>) => {
    setToolInvocations((prev) => {
      const next = [...prev];
      const index = [...next].reverse().findIndex((item) => item.toolName === toolName && item.status === 'running');
      if (index === -1) return prev;
      const actualIndex = next.length - 1 - index;
      next[actualIndex] = {
        ...next[actualIndex],
        ...updates,
        updatedAt: createTimestamp(),
      };
      return next;
    });
  }, []);

  useEffect(() => {
    (async () => {
      const res = await getAvailableModels();
      if (res.success && res.data) {
        const options = (res.data.models || []).map((m: string) => ({ value: m, label: m }));
        const defaultModel = res.data.default || '';
        setAvailableModels([{ value: '', label: '默认模型' }, ...options]);
        setModel(defaultModel || null);
      }
    })();
  }, []);

  const loadSkillOptions = useCallback(async () => {
    setIsRefreshingSkills(true);
    try {
      const res = await getAgentSkills();
      const options = res.data;
      if (res.success && options?.length) {
        setSkillOptions(options);
        setAutomationConfig((prev) => {
          const exists = options.some((item) => item.value === prev.skillName);
          return exists ? prev : { ...prev, skillName: options[0].value };
        });
      }
    } finally {
      setIsRefreshingSkills(false);
    }
  }, []);

  useEffect(() => {
    void loadSkillOptions();
  }, [loadSkillOptions]);

  useEffect(() => {
    (async () => {
      const res = await listExternalMcpServers();
      if (res.success && res.data) {
        setExternalMcpServers(res.data.filter((server) => server.enabled));
      }
    })();
  }, []);

  const hydrateAutomationTask = useCallback((task: TaskInfo) => {
    const params = (task.params || {}) as Record<string, unknown>;
    const notifyChannel = params.notify_channel as Record<string, unknown> | undefined;
    automationDirty.current = false;
    automationSelection.current = task.task_id;
    setAutomationEnabled(task.is_enabled);
    setAutomationTaskInfo(task);
    setAutomationTaskId(task.task_id);
    setAutomationConfig((prev) => ({
      ...prev,
      model: typeof params.model === 'string' && params.model.trim() ? params.model : null,
      taskName: typeof task.description === 'string' && task.description.trim() ? task.description : prev.taskName,
      dailyTime: typeof params.daily_time === 'string' && params.daily_time ? params.daily_time : prev.dailyTime,
      timezone: typeof params.timezone === 'string' && params.timezone ? params.timezone : prev.timezone,
      skillName: typeof params.skill_name === 'string' && params.skill_name ? params.skill_name : prev.skillName,
      promptTemplate: typeof params.prompt_template === 'string' && params.prompt_template ? params.prompt_template : prev.promptTemplate,
      tradingDaysOnly: typeof params.trading_days_only === 'boolean' ? params.trading_days_only : params.skill_name === 'ashare-daily-review',
      enableWebSearch: Boolean(params.enable_web_search),
      publishTitle: typeof params.publish_title === 'string' && params.publish_title ? params.publish_title : prev.publishTitle,
      publishCollectionSlug: typeof params.publish_collection_slug === 'string' && params.publish_collection_slug ? params.publish_collection_slug : prev.publishCollectionSlug,
      publishSlug: typeof params.publish_slug === 'string' && params.publish_slug ? params.publish_slug : prev.publishSlug,
      selectedMcpServerIds: Array.isArray(params.mcp_servers)
        ? params.mcp_servers.map((item) => String(item)).filter(Boolean)
        : prev.selectedMcpServerIds,
      notifyChannelType:
        typeof notifyChannel?.type === 'string'
          ? String(notifyChannel.type)
          : '',
      notifyTargetId: notifyChannel?.target_id ? String(notifyChannel.target_id) : '',
      notifyChannelChatId:
        typeof notifyChannel?.chat_id === 'string' ||
        typeof notifyChannel?.chat_id === 'number' ||
        typeof notifyChannel?.webhook_url === 'string'
          ? String(notifyChannel?.webhook_url ?? notifyChannel?.chat_id)
          : '',
    }));

    const publishedUrl =
      task.result && typeof task.result.published_url === 'string'
        ? task.result.published_url
        : null;
    setAutomationPublishUrl(publishedUrl);
  }, []);

  const loadAutomationTask = useCallback(async () => {
    if (!isAuthenticated || !canAccessAutomation) {
      setAutomationTasks([]);
      setAutomationTaskId(null);
      setAutomationTaskInfo(null);
      setAutomationPublishUrl(null);
      return;
    }
    const response = await getAllTasks();
    if (!response.success || !response.data) return;

    const tasks = [...response.data]
      .filter((item) => item.task_type === 'skill_publish_job')
      .sort((a, b) => {
        const aTime = new Date(a.last_run || a.next_run || 0).getTime();
        const bTime = new Date(b.last_run || b.next_run || 0).getTime();
        return bTime - aTime;
      });
    setAutomationTasks(tasks);

    const task = tasks.find((item) => item.task_id === automationSelection.current);
    if (task) {
      if (!automationDirty.current) hydrateAutomationTask(task);
      else setAutomationTaskInfo(task);
    }
  }, [canAccessAutomation, hydrateAutomationTask, isAuthenticated]);

  useEffect(() => {
    void loadAutomationTask();
  }, [loadAutomationTask]);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  
  // 初始消息
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([
        {
          id: '1',
          role: 'assistant',
          content: '我是AlphaBot智能助手，您的专业股票分析专家。\n\n我能帮您分析市场趋势、评估个股表现、比较不同公司财务状况，并提供基于AI的量化分析。有什么可以帮到您的？',
          timestamp: new Date()
        }
      ]);
      setRunEvents([
        {
          id: generateId(),
          type: 'status',
          title: '工作台已就绪',
          detail: '等待你创建新的分析任务。',
          status: 'done',
          createdAt: createTimestamp(),
        },
      ]);
      setToolInvocations([]);
      setArtifacts([]);
      setActiveSkillName(null);
    }
    
    // 聚焦输入框
    setTimeout(() => {
      inputRef.current?.focus();
    }, 100);
  }, [messages.length]);

  // 加载会话列表
  const loadSessionList = useCallback(async () => {
    if (!isAuthenticated) return;
    
    setIsFetchingSessions(true);
    try {
      const response = await getAgentSessions();
      if (response.success && response.data && response.data.sessions) {
        setSessionList(response.data.sessions);
      }
    } catch (error) {
      console.error('获取会话列表失败:', error);
    } finally {
      setIsFetchingSessions(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      loadSessionList();
    }
  }, [isAuthenticated, loadSessionList]);
  
  // 滚动到最新消息
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 加载会话历史
  const loadSessionHistory = async (sessionId: string) => {
    if (!isAuthenticated || !sessionId) return;
    
    setIsLoadingSession(true);
    try {
      const response = await getAgentSessionHistory(sessionId);
      if (response.success && response.data && response.data.messages) {
        const formattedMessages: Message[] = response.data.messages.map((msg: { id: string; role: 'user' | 'assistant' | 'system'; content: string; timestamp: string }) => ({
          id: msg.id,
          role: msg.role,
          content: msg.content,
          timestamp: new Date(msg.timestamp)
        }));
        setMessages(formattedMessages);
        setCurrentSession(sessionId);
        setActiveSkillName(null);
        setRunEvents(
          formattedMessages.map((msg) => ({
            id: generateId(),
            type: msg.role === 'user' ? 'goal' : 'answer',
            title: msg.role === 'user' ? '已恢复用户目标' : '已恢复助手输出',
            detail: msg.content.slice(0, 280),
            status: 'done' as const,
            createdAt: msg.timestamp.toISOString(),
          }))
        );
        setToolInvocations([]);
        setArtifacts([]);
        formattedMessages.forEach((msg) => {
          if (msg.role === 'assistant') {
            ingestArtifactsFromText(msg.content);
          }
        });
        setActiveView('conversation');
      }
    } catch (error) {
      console.error('获取会话历史失败:', error);
    } finally {
      setIsLoadingSession(false);
    }
  };

  // 删除会话
  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isAuthenticated || !sessionId) return;
    
    if (window.confirm('确定要删除这个会话吗？')) {
      try {
        const response = await deleteAgentSession(sessionId);
        if (response.success) {
          // 更新会话列表
          setSessionList(prev => prev.filter(session => session.id !== sessionId));
          
          // 如果删除的是当前会话，则创建新会话
          if (currentSession === sessionId) {
            handleNewChat();
          }
        }
      } catch (error) {
        console.error('删除会话失败:', error);
      }
    }
  };
  
  // 处理发送消息
  const handleSendMessage = async () => {
    await submitMessage(input);
  };

  const submitMessage = async (rawInput: string) => {
    const trimmedInput = rawInput.trim();
    if (!trimmedInput) return;
    
    if (!isAuthenticated) {
      alert('请先登录后再使用智能助手功能');
      return;
    }
    
    // 如果是使用/search命令，检查积分
    if (trimmedInput.startsWith('/search') && !canUseWebSearch) {
      // 积分不足，直接显示错误信息，不展示思考状态
      const insufficientPointsMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: '您的积分不足，需要2000积分才能使用联网搜索功能',
        timestamp: new Date()
      };
      
      // 添加用户消息和系统回复
      setMessages(prev => [
        ...prev, 
        {
          id: generateId(),
          role: 'user',
          content: trimmedInput,
          timestamp: new Date()
        },
        insufficientPointsMessage
      ]);
      
      setInput('');
      return;
    }
    
    // 如果启用联网搜索，先检查积分
    if (webSearchEnabled && !canUseWebSearch) {
      // 积分不足，直接显示错误信息，不展示思考状态
      const insufficientPointsMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: '您的积分不足，需要2000积分才能使用联网搜索功能',
        timestamp: new Date()
      };
      
      // 添加用户消息和系统回复
      setMessages(prev => [
        ...prev, 
        {
          id: generateId(),
          role: 'user',
          content: trimmedInput,
          timestamp: new Date()
        },
        insufficientPointsMessage
      ]);
      
      setInput('');
      return;
    }
    
    // 添加用户消息
    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: trimmedInput,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    appendRunEvent({
      type: 'goal',
      title: '收到新的任务目标',
      detail: trimmedInput,
      status: 'done',
    });
    setInput('');
    setIsLoading(true);
    
    try {
      if (streamEnabled) {
        // 使用流式传输 - 不添加思考消息，流式处理会自己管理状态
        await handleStreamingChat(trimmedInput);
      } else {
        // 使用传统方式 - 添加思考消息
        setIsThinking(true);
        setTimeout(() => {
          // 模拟思考中...
          const thinkingMessage: Message = {
            id: 'thinking-' + generateId(),
            role: 'assistant',
            content: '_正在分析数据..._',
            timestamp: new Date()
          };
          setMessages(prev => [...prev, thinkingMessage]);
        }, 300);
        appendRunEvent({
          type: 'thinking',
          title: '进入分析阶段',
          detail: 'Agent 正在整理上下文并准备回答。',
          status: 'running',
        });
        
        await handleTraditionalChat(trimmedInput);
      }
    } catch (error) {
      // 移除思考消息
      setIsThinking(false);
      setMessages(prev => prev.filter(msg => !msg.id.startsWith('thinking-')));
      settleRunningEvents('error');
      
      console.error('发送消息错误:', error);
      const errorMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: '与服务器通信时出错，可能是处理时间过长导致超时。请尝试更简短的问题或稍后再试。',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
      appendRunEvent({
        type: 'error',
        title: '任务执行失败',
        detail: '与服务器通信时出错，处理被中断。',
        status: 'error',
      });
    } finally {
      setIsLoading(false);
      // 聚焦输入框以便继续对话
      inputRef.current?.focus();
    }
  };
  
  // 流式传输处理
  const handleStreamingChat = async (input: string) => {
    // 移除思考消息
    setIsThinking(false);
    setMessages(prev => prev.filter(msg => !msg.id.startsWith('thinking-')));
    
    // 创建流式消息
    const streamingMessageId = 'streaming-' + generateId();
    const streamingMessage: Message = {
      id: streamingMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date()
    };
    
    setCurrentStreamingMessage(streamingMessage);
    setMessages(prev => [...prev, streamingMessage]);
    const abortController = new AbortController();
    setStreamAbortController(abortController);
    
    let sessionId = currentSession;
    const toolOutputs: string[] = [];
    
    await chatWithAgentStream(
      {
        content: input,
        session_id: currentSession || undefined,
        enable_web_search: webSearchEnabled,
        model: model || undefined,
        account_context: selectedAccount ? {
          account_id: selectedAccount.id,
          provider: selectedAccount.provider,
          name: selectedAccount.name,
        } : undefined,
      },
      (message) => {
        switch (message.type) {
          case 'start':
            sessionId = message.session_id;
            setCurrentSession(sessionId);
            appendRunEvent({
              type: 'status',
              title: '任务已创建',
              detail: `运行标识 ${message.session_id}`,
              status: 'done',
            });
            break;

          case 'phase':
            setStreamingMessage(message.detail || message.title || '');
            appendRunEvent({
              type: 'phase',
              title: message.title || '阶段更新',
              detail: message.detail || message.phase || '',
              status: 'running',
            });
            break;
          
          case 'delta':
            // 增量内容
            setMessages(prev => prev.map(msg =>
              msg.id === streamingMessageId
                ? { ...msg, content: (msg.content || '') + (message.content || '') }
                : msg
            ));
            break;
            
          case 'thinking':
            // 更新思考状态
            setStreamingMessage(message.content);
            updateLatestRunEvent(
              (event) => event.type === 'thinking' && event.status === 'running',
              {
                detail: message.content,
              }
            );
            appendRunEvent({
              type: 'thinking',
              title: 'Agent 正在思考',
              detail: message.content,
              status: 'running',
            });
            break;

          case 'skill_loaded':
            setStreamingMessage(`已加载 Skill：${message.skill_name}`);
            setActiveSkillName(String(message.skill_name || ''));
            appendRunEvent({
              type: 'status',
              title: '已加载 Skill',
              detail: String(message.skill_name || ''),
              status: 'done',
            });
            break;
            
          case 'tool_calls':
            // 工具调用开始
            setStreamingMessage('正在执行工具调用...');
            updateLatestRunEvent(
              (event) => event.type === 'thinking' && event.status === 'running',
              {
                status: 'done',
              }
            );
            appendRunEvent({
              type: 'tool_call',
              title: '准备调用工具',
              detail: '模型决定通过工具补充外部信息。',
              status: 'running',
            });
            break;
            
          case 'tool_start':
            // 工具执行开始
            setStreamingMessage(`正在执行 ${message.tool_name}...`);
            startToolInvocation(message.tool_name);
            appendRunEvent({
              type: 'tool_call',
              title: `调用工具 ${message.tool_name}`,
              detail: '工具执行中',
              status: 'running',
            });
            break;
            
          case 'tool_result':
            // 工具执行结果
            if (message.formatted_result) {
              toolOutputs.push(message.formatted_result);
              registerArtifact({
                kind: 'tool_output',
                title: `工具结果 · ${message.tool_name}`,
                content: message.formatted_result.slice(0, 500),
              });
            }
            setStreamingMessage('正在处理工具结果...');
            finishLatestToolInvocation(message.tool_name, {
              status: 'done',
              resultText: message.formatted_result,
            });
            updateLatestRunEvent(
              (event) =>
                event.type === 'tool_call' &&
                event.status === 'running' &&
                event.title === `调用工具 ${message.tool_name}`,
              {
                status: 'done',
                detail: '工具执行完成',
              }
            );
            appendRunEvent({
              type: 'tool_result',
              title: `工具 ${message.tool_name} 已返回`,
              detail: message.formatted_result?.slice(0, 220) || '工具已完成',
              status: 'done',
            });
            break;
            
          case 'content':
            // 最终内容
            setCurrentStreamingMessage(null);
            setStreamingMessage('');
            setStreamAbortController(null);
            settleRunningEvents('done');
            setMessages(prev => prev.map(msg => 
              msg.id === streamingMessageId 
                ? {
                    ...msg,
                    content: message.content,
                    toolOutputs: toolOutputs.length > 0 ? toolOutputs : undefined
                  }
                : msg
            ));
            ingestArtifactsFromText(message.content);
            appendRunEvent({
              type: 'answer',
              title: '生成最终回答',
              detail: message.content.slice(0, 280),
              status: 'done',
            });
            break;
            
          case 'end':
            // 流式传输结束
            setCurrentStreamingMessage(null);
            setStreamingMessage('');
            setStreamAbortController(null);
            settleRunningEvents('done');
            // 刷新会话列表
            loadSessionList();
            appendRunEvent({
              type: 'status',
              title: '本轮任务完成',
              detail: '你可以继续追问、修改约束，或开始新的任务。',
              status: 'done',
            });
            break;
            
          case 'error':
            // 错误处理
            setCurrentStreamingMessage(null);
            setStreamingMessage('');
            setStreamAbortController(null);
            settleRunningEvents('error');
            setMessages(prev => prev.map(msg => 
              msg.id === streamingMessageId 
                ? {
                    ...msg,
                    content: `错误: ${message.error}`
                  }
                : msg
            ));
            appendRunEvent({
              type: 'error',
              title: '流式执行失败',
              detail: message.error,
              status: 'error',
            });
            break;

          case 'aborted':
            setCurrentStreamingMessage(null);
            setStreamingMessage('');
            setStreamAbortController(null);
            settleRunningEvents('done');
            setMessages(prev => prev.map(msg =>
              msg.id === streamingMessageId
                ? {
                    ...msg,
                    content: msg.content?.trim() ? msg.content : '已停止生成。',
                    toolOutputs: toolOutputs.length > 0 ? toolOutputs : undefined
                  }
                : msg
            ));
            appendRunEvent({
              type: 'status',
              title: '已停止生成',
              detail: '当前流式执行已被手动中断。',
              status: 'done',
            });
            void loadSessionList();
            break;
        }
      },
      abortController.signal
    );
  };
  
  // 传统传输处理
  const handleTraditionalChat = async (input: string) => {
    const response = await chatWithAgent({ 
      content: input,
      session_id: currentSession || undefined,
      enable_web_search: webSearchEnabled,
      model: model || undefined,
      account_context: selectedAccount ? {
        account_id: selectedAccount.id,
        provider: selectedAccount.provider,
        name: selectedAccount.name,
      } : undefined,
    });
    
      if (response.success && response.data) {
      setActiveSkillName(typeof response.data.active_skill === 'string' ? response.data.active_skill : null);
      // 移除思考消息
      setIsThinking(false);
      setMessages(prev => prev.filter(msg => !msg.id.startsWith('thinking-')));
      
      // 检查是否有工具调用需要执行
      if (response.data.tool_calls && response.data.tool_calls.length > 0) {
        // 更新思考消息
        const updatedThinkingMessage: Message = {
          id: 'thinking-' + generateId(),
          role: 'assistant',
          content: '_正在执行工具调用..._',
          timestamp: new Date()
        };
        setMessages(prev => [...prev.filter(msg => !msg.id.startsWith('thinking-')), updatedThinkingMessage]);
        appendRunEvent({
          type: 'tool_call',
          title: '准备执行工具调用',
          detail: `共 ${response.data.tool_calls.length} 个工具动作`,
          status: 'running',
        });
        
        // 单独处理工具调用
        try {
          response.data.tool_calls.forEach((toolCall: { function?: { name?: string; arguments?: string } }) => {
            const name = toolCall.function?.name || 'unknown_tool';
            startToolInvocation(name, toolCall.function?.arguments);
          });
          const toolResponse = await executeAgentTool(
            response.data.tool_calls,
            selectedAccount ? {
              account_id: selectedAccount.id,
              provider: selectedAccount.provider,
              name: selectedAccount.name,
            } : undefined,
          );
          if (toolResponse.success && toolResponse.data) {
            // 工具调用成功，显示结果
            const assistantMessage: Message = {
              id: generateId(),
              role: 'assistant',
              content: response.data.content || '已执行工具调用',
              timestamp: new Date(),
              toolOutputs: toolResponse.data.responses || []
            };
            
            // 移除思考消息，添加助手回复
            setIsThinking(false);
            setMessages(prev => [...prev.filter(msg => !msg.id.startsWith('thinking-')), assistantMessage]);
            (toolResponse.data.responses || []).forEach((toolItem: { output?: string; tool_call_id?: string }, index: number) => {
              const toolName = response.data.tool_calls[index]?.function?.name || `tool_${index + 1}`;
              finishLatestToolInvocation(toolName, {
                status: 'done',
                resultText: toolItem.output,
              });
              updateLatestRunEvent(
                (event) =>
                  event.type === 'tool_call' &&
                  event.status === 'running' &&
                  (event.title === `调用工具 ${toolName}` || event.title === '准备执行工具调用'),
                {
                  status: 'done',
                }
              );
              if (toolItem.output) {
                registerArtifact({
                  kind: 'tool_output',
                  title: `工具结果 · ${toolName}`,
                  content: toolItem.output.slice(0, 500),
                });
                appendRunEvent({
                  type: 'tool_result',
                  title: `工具 ${toolName} 已完成`,
                  detail: toolItem.output.slice(0, 220),
                  status: 'done',
                });
              }
            });
            ingestArtifactsFromText(assistantMessage.content);
            settleRunningEvents('done');
            appendRunEvent({
              type: 'answer',
              title: '生成最终回答',
              detail: assistantMessage.content.slice(0, 280),
              status: 'done',
            });
          } else {
            // 工具调用失败
            throw new Error(toolResponse.error || '工具调用失败');
          }
        } catch (error: unknown) {
          const message = error instanceof Error ? error.message : '未知错误';
          console.error('工具调用出错:', error);
          const errorMessage: Message = {
            id: generateId(),
            role: 'assistant',
            content: `执行工具时出错: ${message}`,
            timestamp: new Date()
          };
          
          // 移除思考消息，添加错误消息
          setIsThinking(false);
          setMessages(prev => [...prev.filter(msg => !msg.id.startsWith('thinking-')), errorMessage]);
          settleRunningEvents('error');
          appendRunEvent({
            type: 'error',
            title: '工具执行失败',
            detail: message,
            status: 'error',
          });
        }
      } else {
        // 没有工具调用，直接显示回复
        const assistantMessage: Message = {
          id: generateId(),
          role: 'assistant',
          content: response.data.content,
          timestamp: new Date(),
          toolOutputs: response.data.tool_outputs || []
        };
        
        setMessages(prev => [...prev, assistantMessage]);
        ingestArtifactsFromText(assistantMessage.content);
        settleRunningEvents('done');
        if (response.data.metadata?.staged_response_used) {
          appendRunEvent({
            type: 'phase',
            title: '最终成稿',
            detail: `本次回复已走成稿阶段 · ${response.data.metadata?.completion_reason || 'completed'}`,
            status: 'done',
          });
        }
        appendRunEvent({
          type: 'answer',
          title: '生成直接回答',
          detail: assistantMessage.content.slice(0, 280),
          status: 'done',
        });
      }
      
      // 更新会话ID
      if (response.data.session_id) {
        setCurrentSession(response.data.session_id);
        
        // 刷新会话列表
        loadSessionList();
      }
      
    } else {
      // 移除思考消息
      setIsThinking(false);
      setMessages(prev => prev.filter(msg => !msg.id.startsWith('thinking-')));
      
      const errorMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: response.error || '与智能助手通信时出错',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
      settleRunningEvents('error');
      appendRunEvent({
        type: 'error',
        title: '响应失败',
        detail: response.error || '与智能助手通信时出错',
        status: 'error',
      });
    }
  };
  
  // 键盘事件处理
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };
  
  // 新建会话
  const handleNewChat = () => {
    setActiveView('conversation');
    setCurrentSession(null);
    setActiveSkillName(null);
    setMessages([
      {
        id: '1',
        role: 'assistant',
        content: '我是AlphaBot智能助手，您的专业股票分析专家。\n\n我能帮您分析市场趋势、评估个股表现、比较不同公司财务状况，并提供基于AI的量化分析。有什么可以帮到您的？',
        timestamp: new Date()
      }
    ]);
    setRunEvents([
      {
        id: generateId(),
        type: 'status',
        title: '新的任务工作台已创建',
        detail: '输入一个新的目标，agent 会把它作为任务来执行。',
        status: 'done',
        createdAt: createTimestamp(),
      },
    ]);
    setToolInvocations([]);
    setArtifacts([]);
    setStreamingMessage('');
    setCurrentStreamingMessage(null);
    setShowSidebar(false);
    
    // 聚焦输入框
    inputRef.current?.focus();
  };

  // 切换会话
  const switchSession = (sessionId: string) => {
    setShowSidebar(false);
    setActiveView('conversation');
    loadSessionHistory(sessionId);
  };
  
  // 渲染消息列表
  const renderMessages = () => {
    return messages.map((message, index) => {
      const isThinking = message.id.startsWith('thinking-');
      const isStreaming = message.id.startsWith('streaming-');
      const isLast = index === messages.length - 1;

      if (isThinking) {
        return (
          <div key={message.id} className={`flex gap-3 justify-start mb-4`}>
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white">
              <Bot size={18} />
            </div>
            
            <div className="max-w-[80%]">
              <div className="prose prose-sm max-w-none dark:prose-invert text-gray-400 dark:text-gray-500">
                <div className="bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 px-4 py-2 rounded-lg">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>
              </div>
            </div>
          </div>
        );
      }

      if (isStreaming && currentStreamingMessage) {
        return (
          <div key={message.id} className={`flex gap-3 justify-start mb-4`}>
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white">
              <Bot size={18} />
            </div>
            
            <div className="max-w-[80%]">
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <div className="bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 px-4 py-2 rounded-lg">
                  {streamingMessage && (
                    <div className="text-sm text-gray-500 dark:text-gray-400 mb-2 italic">
                      {streamingMessage}
                    </div>
                  )}
                  {message.content && (
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  )}
                  {!message.content && !streamingMessage && (
                    <div className="text-sm text-gray-500 dark:text-gray-400 italic">
                      正在思考中...
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      }

      return (
        <AgentMessageDisplay 
          key={message.id} 
          message={{ 
            id: message.id, 
            role: message.role, 
            content: message.content,
            toolOutputs: message.toolOutputs,
          }} 
          isLast={isLast} 
        />
      );
    });
  };

  // 示例快速提问
  const examples = [
    {
      text: "分析贵州茅台近期表现",
      icon: <LineChart className="h-4 w-4 mr-1.5" />
    },
    {
      text: "比较阿里巴巴和腾讯的财务状况",
      icon: <BarChart2 className="h-4 w-4 mr-1.5" />
    },
    {
      text: "查询近期银行股走势",
      icon: <TrendingUp className="h-4 w-4 mr-1.5" />
    },
    {
      text: "分析A股市场热点板块",
      icon: <PieChart className="h-4 w-4 mr-1.5" />
    }
  ];

  // 处理搜索功能
  const handleSearch = () => {
    if (!input.trim() || isLoading) return;
    
    // 先检查积分是否足够
    if (!canUseWebSearch) {
      // 积分不足，直接显示错误信息，不展示思考状态
      const insufficientPointsMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: '您的积分不足，需要2000积分才能使用联网搜索功能',
        timestamp: new Date()
      };
      
      // 添加用户消息和系统回复
      setMessages(prev => [
        ...prev, 
        {
          id: generateId(),
          role: 'user',
          content: input,
          timestamp: new Date()
        },
        insufficientPointsMessage
      ]);
      
      setInput('');
      return;
    }
    
    // 如果不是以/search开头，自动添加
    const searchQuery = input.trim().startsWith('/search')
      ? input.trim()
      : `/search ${input.trim()}`;
    
    setInput(searchQuery);
    void submitMessage(searchQuery);
  };

  useEffect(() => {
    if (!canAccessAutomation && activeView === 'automation') {
      setActiveView('conversation');
    }
  }, [activeView, canAccessAutomation]);

  const latestToolOutputs = [...messages]
    .reverse()
    .find((message) => message.role === 'assistant' && message.toolOutputs && message.toolOutputs.length > 0)
    ?.toolOutputs || [];

  const hasActiveConversation = messages.length > 1 || !!currentSession || isLoading || runEvents.length > 1;
  const latestUserGoal = [...messages].reverse().find((message) => message.role === 'user')?.content;
  const latestUserGoalBrief = latestUserGoal ? toBrief(latestUserGoal) : '';

  const buildAutomationPayload = useCallback(() => {
    if (automationConfig.notifyChannelType && !automationConfig.notifyTargetId) {
      throw new Error('请选择已绑定的接收目标，或选择不推送');
    }
    const promptTemplate = automationConfig.promptTemplate.trim();
    if (!automationConfig.taskName.trim() || !promptTemplate) throw new Error('请填写任务名称和执行指令');
    const publishTitle = automationConfig.publishTitle.trim() || automationConfig.taskName.trim() || '自动化报告';
    const publishCollectionSlug = slugify(automationConfig.publishCollectionSlug.trim() || 'daily-market-brief');
    const publishSlug = normalizeSlugTemplate(automationConfig.publishSlug.trim() || 'review-{date_compact}');

    return {
      task_type: 'skill_publish_job',
      interval: 86400,
      is_enabled: automationEnabled,
      description: automationConfig.taskName.trim() || publishTitle,
      params: {
        daily_time: automationConfig.dailyTime,
        trading_days_only: automationConfig.tradingDaysOnly,
        timezone: automationConfig.timezone.trim() || DEFAULT_APP_TIMEZONE,
        skill_name: automationConfig.skillName,
        prompt_template: promptTemplate,
        enable_web_search: automationConfig.enableWebSearch,
        publish_title: publishTitle,
        publish_collection_slug: publishCollectionSlug,
        publish_slug: publishSlug,
        mcp_servers: automationConfig.selectedMcpServerIds,
        notify_channel: automationConfig.notifyChannelType && automationConfig.notifyTargetId
          ? { type: automationConfig.notifyChannelType, target_id: Number(automationConfig.notifyTargetId) }
          : null,
        model: automationConfig.model,
        account_id: selectedAccount?.id,
        account_provider: selectedAccount?.provider,
        account_name: selectedAccount?.name,
      },
    };
  }, [automationConfig, automationEnabled, selectedAccount]);

  const handleAutomationConfigChange = useCallback((updates: Partial<AutomationConfig>) => {
    automationDirty.current = true;
    setAutomationConfig((prev) => {
      const next = { ...prev, ...updates };
      return next;
    });
  }, []);

  const handleToggleMcpServer = useCallback((serverId: string) => {
    automationDirty.current = true;
    setAutomationConfig((prev) => ({
      ...prev,
      selectedMcpServerIds: prev.selectedMcpServerIds.includes(serverId)
        ? prev.selectedMcpServerIds.filter((id) => id !== serverId)
        : [...prev.selectedMcpServerIds, serverId],
    }));
  }, []);

  const handleSaveAutomation = useCallback(async () => {
    setIsSavingAutomation(true);
    setAutomationFeedback(null);
    try {
      const payload = buildAutomationPayload();
      const response = automationTaskId
        ? await updateTask(automationTaskId, {
            interval: payload.interval,
            is_enabled: payload.is_enabled,
            description: payload.description,
            params: payload.params,
          })
        : await createTask(payload);

      if (response.success && response.data) {
        hydrateAutomationTask(response.data);
        void loadAutomationTask();
        setAutomationFeedback(`已保存自动化任务：${response.data.description}`);
      } else {
        setAutomationFeedback(response.error || '保存自动化任务失败');
      }
    } catch (error) {
      console.error('保存自动化任务失败:', error);
      setAutomationFeedback(error instanceof Error ? error.message : '保存自动化任务失败');
    } finally {
      setIsSavingAutomation(false);
    }
  }, [automationTaskId, buildAutomationPayload, hydrateAutomationTask, loadAutomationTask]);

  const handleRunAutomationNow = useCallback(async () => {
    if (!automationTaskId) {
      setAutomationFeedback('请先保存自动化任务');
      return;
    }
    if (automationDirty.current) {
      setAutomationFeedback('请先保存修改，再立即执行。');
      return;
    }
    setIsRunningAutomation(true);
    setAutomationFeedback(null);
    try {
      const response = await runTaskNow(automationTaskId);
      if (response.success && response.data) {
        const data = response.data as TaskInfo;
        hydrateAutomationTask(data);
        setActiveView('automation');
        void loadSessionList();
        void loadAutomationTask();
        const publishedUrl = typeof data?.result?.published_url === 'string' ? data.result.published_url : null;
        if (publishedUrl) {
          setAutomationPublishUrl(publishedUrl);
          setAutomationFeedback(`运行完成，已发布到 ${publishedUrl}`);
        } else {
          setAutomationFeedback(data?.description || '任务已开始运行');
        }
      } else {
        setAutomationFeedback(response.error || '运行自动化任务失败');
      }
    } catch (error) {
      console.error('运行自动化任务失败:', error);
      setAutomationFeedback('运行自动化任务失败');
    } finally {
      setIsRunningAutomation(false);
    }
  }, [automationTaskId, hydrateAutomationTask, loadSessionList, loadAutomationTask]);

  const handleDeleteAutomationTask = useCallback(async () => {
    if (!automationTaskId) return;
    if (!window.confirm('确定要删除当前自动化任务吗？')) {
      return;
    }
    setIsDeletingAutomation(true);
    try {
      const response = await deleteTask(automationTaskId);
      if (response.success) {
        automationSelection.current = null;
        automationDirty.current = false;
        setAutomationTaskId(null);
        setAutomationTaskInfo(null);
        setAutomationOverview(true);
        setAutomationFeedback('自动化任务已删除');
        await loadAutomationTask();
      } else {
        setAutomationFeedback(response.error || '删除自动化任务失败');
      }
    } catch (error) {
      console.error('删除自动化任务失败:', error);
      setAutomationFeedback('删除自动化任务失败');
    } finally {
      setIsDeletingAutomation(false);
    }
  }, [automationTaskId, loadAutomationTask]);

  const leaveAutomation = () => !automationDirty.current || window.confirm('当前修改尚未保存，确定离开吗？');
  const selectAutomation = (task: TaskInfo) => {
    if (!leaveAutomation()) return;
    hydrateAutomationTask(task);
    setAutomationOverview(false);
    setActiveView('automation');
    setShowSidebar(false);
    setAutomationFeedback(null);
  };
  const newAutomation = (template: 'blank' | 'noon' | 'close' | 'copy') => {
    if (!leaveAutomation()) return;
    const copy = template === 'copy';
    const name = template === 'noon' ? '午间复盘' : template === 'close' ? '收盘复盘' : '新自动化任务';
    setAutomationConfig(prev => ({
      ...prev,
      taskName: copy ? `${prev.taskName} · 副本` : name,
      dailyTime: copy ? prev.dailyTime : template === 'noon' ? '11:40' : '15:30',
      tradingDaysOnly: copy ? prev.tradingDaysOnly : template !== 'blank',
      skillName: copy ? prev.skillName : 'research',
      model: copy ? prev.model : null,
      promptTemplate: copy ? prev.promptTemplate : template === 'blank' ? '' : `请基于 {date} 的${template === 'noon' ? '上午行情生成午间复盘，严格区分上午已发生行情与下午关注点' : '收盘行情生成收盘复盘'}，包含指数表现、热点板块、风险与后续观察点。非 A 股交易日请明确说明。`,
      publishTitle: copy ? prev.publishTitle : `{date} · ${name}`,
      publishSlug: `${copy ? 'copy' : template}-${generateId().slice(0, 8)}-{date_compact}`,
      publishCollectionSlug: copy ? prev.publishCollectionSlug : 'daily-market-brief',
      selectedMcpServerIds: copy ? prev.selectedMcpServerIds : [],
      notifyChannelType: copy ? prev.notifyChannelType : '',
      notifyTargetId: copy ? prev.notifyTargetId : '',
      enableWebSearch: copy ? prev.enableWebSearch : false,
    }));
    automationSelection.current = null;
    automationDirty.current = true;
    setAutomationTaskId(null);
    setAutomationTaskInfo(null);
    setAutomationPublishUrl(null);
    setAutomationFeedback(null);
    setAutomationEnabled(!copy);
    setAutomationOverview(false);
    setTemplatePicker(false);
    setActiveView('automation');
    setShowSidebar(false);
  };
  const toggleAutomation = async () => {
    if (!automationTaskId) { setAutomationEnabled(value => !value); return; }
    setIsSavingAutomation(true);
    try {
      const response = await updateTask(automationTaskId, { is_enabled: !automationEnabled });
      if (!response.success || !response.data) throw new Error(response.error || '更新失败');
      setAutomationEnabled(response.data.is_enabled);
      setAutomationTaskInfo(response.data);
      setAutomationTasks(tasks => tasks.map(task => task.task_id === response.data!.task_id ? response.data! : task));
    } catch (error) { setAutomationFeedback(error instanceof Error ? error.message : '更新失败'); }
    finally { setIsSavingAutomation(false); }
  };

  const handleRefreshWorkspace = useCallback(() => {
    void loadSessionList();
    void loadAutomationTask();
  }, [loadSessionList, loadAutomationTask]);

  const handleStopGenerating = useCallback(() => {
    if (streamAbortController) {
      streamAbortController.abort();
      setStreamAbortController(null);
    }
  }, [streamAbortController]);

  // 切换联网搜索状态
  const toggleWebSearch = () => {
    if (!canUseWebSearch) {
      alert('您的积分不足，需要2000积分才能使用联网搜索功能');
      return;
    }
    setWebSearchEnabled(!webSearchEnabled);
  };

  return (
    <div className="flex h-full min-h-0 overflow-hidden bg-background text-foreground">
      {showSidebar && (
        <button
          type="button"
          className="fixed inset-0 z-20 bg-slate-950/45 backdrop-blur-[1px] md:hidden"
          onClick={() => setShowSidebar(false)}
          aria-label="关闭任务列表"
        />
      )}
      <div
        className={`${
          showSidebar ? 'fixed inset-y-0 left-0 z-30 w-[340px] max-w-[92vw] shadow-2xl shadow-slate-950/30' : 'hidden'
        } md:relative md:block md:h-full md:w-[340px] md:shadow-none xl:w-[360px]`}
      >
        <AgentRunSidebar
          activeView={activeView}
          currentSession={currentSession}
          automationLabel={`${automationTasks.length} 个任务`}
          automationTasks={automationTasks}
          selectedAutomationId={automationOverview ? null : automationTaskId}
          onSelectAutomation={selectAutomation}
          onNewAutomation={() => setTemplatePicker(true)}
          canAccessAutomation={canAccessAutomation}
          isFetchingSessions={isFetchingSessions}
          sessions={sessionList}
          onNewChat={handleNewChat}
          onOpenAutomation={() => {
            if (canAccessAutomation) {
              if (!leaveAutomation()) return;
              setAutomationOverview(true);
              setActiveView('automation');
              setShowSidebar(false);
            }
          }}
          onRefresh={handleRefreshWorkspace}
          onSelectSession={switchSession}
          onDeleteSession={handleDeleteSession}
        />
      </div>

      <Dialog open={templatePicker} onOpenChange={setTemplatePicker}>
        <DialogContent><DialogHeader><DialogTitle>新建自动化</DialogTitle><DialogDescription>选择一个起点，随后调整执行指令、时间和接收目标。</DialogDescription></DialogHeader>
          <div className="grid gap-3 py-3">{([{id: 'blank', name: '自定义任务', detail: '从空白指令开始，定义自己的自动化。'}, {id: 'noon', name: '午间复盘', detail: '交易日 11:40，总结上午行情与下午关注点。'}, {id: 'close', name: '收盘复盘', detail: '交易日 15:30，整理全天行情与后续观察点。'}] as const).map(item => <button key={item.id} onClick={() => newAutomation(item.id)} className="rounded-xl border p-4 text-left hover:border-primary hover:bg-primary/5"><div className="font-medium">{item.name}</div><p className="mt-1 text-sm text-muted-foreground">{item.detail}</p></button>)}</div>
        </DialogContent>
      </Dialog>
      <div className="flex min-w-0 flex-1 overflow-hidden">
        <main className="flex min-w-0 min-h-0 flex-1 flex-col overflow-hidden">
          <AgentWorkspaceHeader
            currentSession={currentSession}
            isLoadingSession={isLoadingSession}
            isLoading={isLoading}
            activeSkillName={activeSkillName}
            streamEnabled={streamEnabled}
            webSearchEnabled={webSearchEnabled}
            canUseWebSearch={!!canUseWebSearch}
            canAccessAutomation={canAccessAutomation}
            model={activeView === 'automation' ? automationConfig.model : model}
            availableModels={availableModels}
            onModelChange={activeView === 'automation'
              ? (value) => handleAutomationConfigChange({ model: value })
              : setModel}
            onToggleStream={() => setStreamEnabled(!streamEnabled)}
            onToggleWebSearch={toggleWebSearch}
            onOpenRuns={() => setShowSidebar(!showSidebar)}
            onOpenInspector={() => {
              if (canAccessAutomation) {
                setActiveView('automation');
              }
            }}
          />

          <div className="min-h-0 flex-1 overflow-auto bg-[radial-gradient(circle_at_top,_rgba(37,99,235,0.06),_transparent_26%),linear-gradient(to_bottom,_rgba(255,255,255,0.98),_rgba(248,250,252,1))] dark:bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.10),_transparent_20%),linear-gradient(to_bottom,_#020617,_#0f172a)]">
            {isLoadingSession ? (
              <div className="flex h-full items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : activeView === 'automation' && canAccessAutomation ? (
              automationOverview ? <div className="mx-auto w-full max-w-5xl px-5 py-8 sm:px-8">
                <div className="mb-8 flex items-center justify-between"><div><h1 className="text-xl font-semibold">自动化</h1><p className="mt-2 text-sm text-muted-foreground">让 Agent 按计划执行任务，发布结果并发送通知。</p></div><Button onClick={() => setTemplatePicker(true)}>新建自动化</Button></div>
                <div className="space-y-3">{automationTasks.map(task => <button key={task.task_id} onClick={() => selectAutomation(task)} className="flex w-full flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-card p-5 text-left transition hover:border-primary/40 hover:bg-muted/40"><div><div className="font-medium">{task.description}</div><div className="mt-2 text-xs text-muted-foreground">{task.params?.trading_days_only || (task.params?.trading_days_only === undefined && task.params?.skill_name === 'ashare-daily-review') ? '交易日' : '每天'} {String(task.params?.daily_time || '—')} · {String(task.params?.timezone || DEFAULT_APP_TIMEZONE)}</div></div><div className="text-right text-xs"><div>{task.is_enabled ? '已启用' : '已暂停'}</div><div className="mt-2 text-muted-foreground">{task.current_stage || task.status || '尚未执行'}</div></div></button>)}{!automationTasks.length && <div className="rounded-2xl border border-dashed p-12 text-center text-muted-foreground">还没有自动化任务。从一个模板开始，配置你的第一项任务。</div>}</div>
              </div> :
              <div className="mx-auto flex min-h-full w-full max-w-[1160px] flex-col px-4 py-4 sm:px-6 xl:px-8">
                <section className="mb-4 px-1 py-1">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Automation</div>
                      <div className="mt-1 text-[1rem] font-semibold tracking-[-0.03em] text-foreground">
                        {automationTaskInfo?.description || automationConfig.taskName}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button variant="ghost" size="sm" onClick={() => { if (leaveAutomation()) setAutomationOverview(true); }}>所有任务</Button>
                      <Button variant="outline" size="sm" disabled={isSavingAutomation} onClick={() => void toggleAutomation()}>{automationEnabled ? '已启用 · 点击暂停' : '已暂停 · 点击启用'}</Button>
                      <Button variant="ghost" size="sm" onClick={() => newAutomation('copy')}>复制任务</Button>
                      {automationTaskInfo?.status && (
                        <span className="rounded-full bg-muted px-2.5 py-1 text-[10px] text-muted-foreground">
                          {automationTaskInfo.status}
                        </span>
                      )}
                      {automationTaskInfo?.next_run && (
                        <span className="rounded-full bg-muted px-2.5 py-1 text-[10px] text-muted-foreground">
                          下次 {new Date(automationTaskInfo.next_run).toLocaleString()}
                        </span>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        className="rounded-2xl border-transparent bg-muted/80 hover:bg-muted"
                        disabled={!automationTaskId || isDeletingAutomation}
                        onClick={handleDeleteAutomationTask}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        {isDeletingAutomation ? '删除中' : '删除任务'}
                      </Button>
                    </div>
                  </div>
                </section>

                <section className="min-h-0 flex-1 rounded-[28px] bg-card/72 p-4 ring-1 ring-border/50 backdrop-blur sm:p-5">
                  <AgentInspector
                    key={automationTaskId || 'draft'}
                    embedded
                    selectedAccount={selectedAccount || null}
                    config={automationConfig}
                    skillOptions={skillOptions}
                    externalMcpServers={externalMcpServers}
                    isSaving={isSavingAutomation}
                    isRunning={isRunningAutomation}
                    savedTaskId={automationTaskId}
                    publishUrl={automationPublishUrl}
                    feedbackMessage={automationFeedback}

                    taskStatus={automationTaskInfo?.status || null}
                    taskStage={automationTaskInfo?.current_stage || null}
                    taskStatusDetail={automationTaskInfo?.status_detail || null}
                    nextRun={automationTaskInfo?.next_run || null}
                    lastRun={automationTaskInfo?.last_run || null}
                    stageHistory={automationTaskInfo?.stage_history || []}
                    isRefreshingSkills={isRefreshingSkills}
                    onConfigChange={handleAutomationConfigChange}
                    onToggleMcpServer={handleToggleMcpServer}
                    onRefreshSkills={() => void loadSkillOptions()}
                    onSave={handleSaveAutomation}
                    onRunNow={handleRunAutomationNow}

                  />
                </section>
              </div>
            ) : (
              <div className="mx-auto flex min-h-full w-full max-w-[1180px] flex-col px-4 py-4 sm:px-6 xl:px-8">
                <section className="mb-4 px-1 py-1">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="min-w-0 max-w-3xl">
                      <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Run</div>
                      <div className="mt-1 text-[0.96rem] font-semibold tracking-[-0.03em] text-foreground sm:text-[1rem]">
                        {latestUserGoalBrief
                          ? latestUserGoalBrief
                          : '输入一个明确目标，开始新的分析任务'}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
                      <span className="rounded-full bg-muted px-2.5 py-1">
                        {isLoading ? '运行中' : currentSession ? '进行中' : '待启动'}
                      </span>
                      <span className="rounded-full bg-muted px-2.5 py-1">
                        {messages.length} 条消息
                      </span>
                      <span className="rounded-full bg-muted px-2.5 py-1">
                        联网{webSearchEnabled ? '已开启' : '未开启'}
                      </span>
                    </div>
                  </div>
                </section>

                {!hasActiveConversation ? (
                  <section className="mb-4 rounded-[24px] bg-card/46 p-5 sm:p-6">
                    <div className="max-w-2xl">
                      <h2 className="text-[0.96rem] font-semibold tracking-[-0.03em] text-foreground sm:text-[1rem]">
                        从一个具体问题开始
                      </h2>
                      <p className="mt-1.5 text-[12px] leading-5 text-muted-foreground">
                        比如分析一只股票、比较两家公司，或者梳理一个板块的风险与机会。
                      </p>
                    </div>
                    <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                          {examples.map((example) => (
                            <button
                              key={`hero-${example.text}`}
                              type="button"
                              className="flex items-center gap-2.5 rounded-[18px] bg-background/70 px-3.5 py-3 text-left text-[12px] text-foreground transition-colors hover:bg-primary/5"
                              onClick={() => {
                                setInput(example.text);
                                inputRef.current?.focus();
                              }}
                            >
                              <span className="flex h-7 w-7 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                                {example.icon}
                              </span>
                              <span>{example.text}</span>
                            </button>
                          ))}
                    </div>
                  </section>
                ) : (
                  <div className="min-h-0 flex-1">
                    <section className="flex h-full min-h-[320px] flex-col px-3 py-2 sm:px-4 sm:py-3">
                      <div className="mb-3 flex items-center justify-between gap-4">
                        <div>
                          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Conversation</div>
                          <h3 className="mt-1 text-[0.95rem] font-semibold tracking-[-0.03em] text-foreground">对话与结果</h3>
                        </div>
                        <div className="text-[11px] text-muted-foreground">{messages.length} 条消息</div>
                      </div>

                      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
                        <div className="space-y-0.5">
                        {renderMessages()}
                        <div ref={messagesEndRef} />
                        </div>
                      </div>
                    </section>
                  </div>
                )}

                {hasActiveConversation && (
                  <div className="mt-4 sm:hidden">
                    <Button variant="outline" size="sm" className="rounded-2xl border-0 bg-muted/70 shadow-none" onClick={() => setActiveView('automation')}>
                      查看自动化配置
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>

          {activeView !== 'automation' && (
            <AgentComposer
              input={input}
              disabled={isLoading || isLoadingSession}
              isLoading={isLoading}
              showExamples={messages.length === 1}
              examples={examples}
              onInputChange={setInput}
              onKeyDown={handleKeyDown}
              onSubmit={handleSendMessage}
              onStop={handleStopGenerating}
              onSearch={handleSearch}
              onSelectExample={(value) => {
                setInput(value);
                inputRef.current?.focus();
              }}
              inputRef={inputRef}
            />
          )}
        </main>
      </div>
    </div>
  );
}
