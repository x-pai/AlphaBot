'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Loader2, Send, Bot, User, TrendingUp, BarChart2, PieChart, LineChart, Plus, Trash2, MessageSquare, Copy, Search, Globe } from 'lucide-react';
import { useAuth } from '@/lib/contexts/AuthContext';
import { chatWithAgent, chatWithAgentStream, getAgentSessions, getAgentSessionHistory, deleteAgentSession, searchWeb, executeAgentTool } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import { ScrollArea } from './ui/scroll-area';
import { format } from 'date-fns';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus, vs } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { AgentMessageDisplay } from './chat/AgentMessageDisplay';

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

// 声明搜索结果类型
interface SearchResult {
  title: string;
  link: string;
  snippet: string;
  source: string;
}

interface SearchResultsProps {
  results: SearchResult[];
  query: string;
}

// 搜索结果组件
const SearchResults = ({ results, query }: SearchResultsProps) => {
  if (!results || results.length === 0) return null;
  
  return (
    <div className="mt-2 p-4 bg-blue-50 dark:bg-blue-900 rounded-md">
      <h3 className="text-md font-medium mb-2">搜索结果: {query}</h3>
      <div className="space-y-2">
        {results.map((result, index) => (
          <div key={index} className="p-2 bg-white dark:bg-gray-800 rounded shadow-sm">
            <h4 className="font-medium text-blue-600 dark:text-blue-400">
              <a href={result.link} target="_blank" rel="noopener noreferrer" className="hover:underline">
                {result.title}
              </a>
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-300">{result.snippet}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              来源: {result.source}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};

interface AgentMessageProps {
  message: {
    content: string;
  };
  isUser: boolean;
}

// 智能体消息组件 - 修改消息组件以支持搜索结果
const AgentMessage = ({ message, isUser }: AgentMessageProps) => {
  const messageText = message.content || '';
  
  // 检查消息是否包含搜索结果
  const hasSearchResults = !isUser && messageText.includes('"results":');
  let searchResults: { results: SearchResult[], query: string } | null = null;
  let cleanedMessage = messageText;
  
  if (hasSearchResults) {
    try {
      // 尝试提取JSON数据
      const jsonMatch = messageText.match(/```json\n([\s\S]*?)\n```/);
      if (jsonMatch && jsonMatch[1]) {
        const searchData = JSON.parse(jsonMatch[1]);
        if (searchData.results && searchData.query) {
          searchResults = searchData;
          // 移除JSON块
          cleanedMessage = messageText.replace(/```json\n[\s\S]*?\n```/, '');
        }
      }
    } catch (e) {
      console.error("解析搜索结果失败:", e);
    }
  }
  
  const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  
  return (
    <div className={`flex mb-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`rounded-lg px-4 py-2 max-w-[80%] ${
        isUser ? 'bg-blue-500 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200'
      }`}>
        <ReactMarkdown 
          components={{
            code: ({ className, children, ...props }: any) => {
              const match = /language-(\w+)/.exec(className || '');
              const language = match ? match[1] : '';
              
              if (language) {
                return (
                  <div className="rounded-md overflow-hidden my-2 bg-gray-50 dark:bg-gray-800">
                    <div className="flex items-center justify-between px-4 py-1.5 bg-gray-100 dark:bg-gray-700">
                      <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{language}</span>
                    </div>
                    <SyntaxHighlighter
                      language={language}
                      style={isDark ? vscDarkPlus : vs}
                      customStyle={{ margin: 0, padding: '1rem' }}
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  </div>
                );
              }
              
              return (
                <code className={className} {...props}>
                  {children}
                </code>
              );
            }
          }}
        >
          {cleanedMessage}
        </ReactMarkdown>
        
        {searchResults && (
          <SearchResults 
            results={searchResults.results} 
            query={searchResults.query} 
          />
        )}
      </div>
    </div>
  );
};

export default function AgentChat({ onSelectStock }: AgentChatProps) {
  const { isAuthenticated, user } = useAuth();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentSession, setCurrentSession] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [sessionList, setSessionList] = useState<Session[]>([]);
  const [showSidebar, setShowSidebar] = useState<boolean>(false);
  const [isFetchingSessions, setIsFetchingSessions] = useState<boolean>(false);
  const [isLoadingSession, setIsLoadingSession] = useState<boolean>(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState<boolean>(false);
  const [streamEnabled, setStreamEnabled] = useState<boolean>(true);
  const [streamingMessage, setStreamingMessage] = useState<string>('');
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState<Message | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const availableModels = [
    { value: '', label: '默认模型' },
    { value: 'gpt-4o-mini', label: 'GPT-4o-mini' },
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-4.1-mini', label: 'GPT-4.1-mini' },
  ];
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  
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
        const formattedMessages = response.data.messages.map((msg: any) => ({
          id: msg.id,
          role: msg.role,
          content: msg.content,
          timestamp: new Date(msg.timestamp)
        }));
        setMessages(formattedMessages);
        setCurrentSession(sessionId);
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
    if (!input.trim()) return;
    
    if (!isAuthenticated) {
      alert('请先登录后再使用智能助手功能');
      return;
    }
    
    // 如果是使用/search命令，检查积分
    if (input.trim().startsWith('/search') && !canUseWebSearch) {
      // 积分不足，直接显示错误信息，不展示思考状态
      const insufficientPointsMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '您的积分不足，需要2000积分才能使用联网搜索功能',
        timestamp: new Date()
      };
      
      // 添加用户消息和系统回复
      setMessages(prev => [
        ...prev, 
        {
          id: Date.now().toString(),
          role: 'user',
          content: input,
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
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '您的积分不足，需要2000积分才能使用联网搜索功能',
        timestamp: new Date()
      };
      
      // 添加用户消息和系统回复
      setMessages(prev => [
        ...prev, 
        {
          id: Date.now().toString(),
          role: 'user',
          content: input,
          timestamp: new Date()
        },
        insufficientPointsMessage
      ]);
      
      setInput('');
      return;
    }
    
    // 添加用户消息
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    
    try {
      if (streamEnabled) {
        // 使用流式传输 - 不添加思考消息，流式处理会自己管理状态
        await handleStreamingChat(input);
      } else {
        // 使用传统方式 - 添加思考消息
        setIsThinking(true);
        setTimeout(() => {
          // 模拟思考中...
          const thinkingMessage: Message = {
            id: 'thinking-' + Date.now().toString(),
            role: 'assistant',
            content: '_正在分析数据..._',
            timestamp: new Date()
          };
          setMessages(prev => [...prev, thinkingMessage]);
        }, 300);
        
        await handleTraditionalChat(input);
      }
    } catch (error) {
      // 移除思考消息
      setIsThinking(false);
      setMessages(prev => prev.filter(msg => !msg.id.startsWith('thinking-')));
      
      console.error('发送消息错误:', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '与服务器通信时出错，可能是处理时间过长导致超时。请尝试更简短的问题或稍后再试。',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
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
    const streamingMessageId = 'streaming-' + Date.now().toString();
    const streamingMessage: Message = {
      id: streamingMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date()
    };
    
    setCurrentStreamingMessage(streamingMessage);
    setMessages(prev => [...prev, streamingMessage]);
    
    let sessionId = currentSession;
    const toolOutputs: string[] = [];
    
    await chatWithAgentStream(
      {
        content: input,
        session_id: currentSession || undefined,
        enable_web_search: webSearchEnabled,
        model: model || undefined
      },
      (message) => {
        switch (message.type) {
          case 'start':
            sessionId = message.session_id;
            setCurrentSession(sessionId);
            break;
            
          case 'thinking':
            // 更新思考状态
            setStreamingMessage(message.content);
            break;
            
          case 'tool_calls':
            // 工具调用开始
            setStreamingMessage('正在执行工具调用...');
            break;
            
          case 'tool_start':
            // 工具执行开始
            setStreamingMessage(`正在执行 ${message.tool_name}...`);
            break;
            
          case 'tool_result':
            // 工具执行结果
            if (message.formatted_result) {
              toolOutputs.push(message.formatted_result);
            }
            setStreamingMessage('正在处理工具结果...');
            break;
            
          case 'content':
            // 最终内容
            setCurrentStreamingMessage(null);
            setStreamingMessage('');
            setMessages(prev => prev.map(msg => 
              msg.id === streamingMessageId 
                ? {
                    ...msg,
                    content: message.content,
                    toolOutputs: toolOutputs.length > 0 ? toolOutputs : undefined
                  }
                : msg
            ));
            break;
            
          case 'end':
            // 流式传输结束
            setCurrentStreamingMessage(null);
            setStreamingMessage('');
            // 刷新会话列表
            loadSessionList();
            break;
            
          case 'error':
            // 错误处理
            setCurrentStreamingMessage(null);
            setStreamingMessage('');
            setMessages(prev => prev.map(msg => 
              msg.id === streamingMessageId 
                ? {
                    ...msg,
                    content: `错误: ${message.error}`
                  }
                : msg
            ));
            break;
        }
      }
    );
  };
  
  // 传统传输处理
  const handleTraditionalChat = async (input: string) => {
    const response = await chatWithAgent({ 
      content: input,
      session_id: currentSession || undefined,
      enable_web_search: webSearchEnabled,
      model: model || undefined
    });
    
    if (response.success && response.data) {
      // 移除思考消息
      setIsThinking(false);
      setMessages(prev => prev.filter(msg => !msg.id.startsWith('thinking-')));
      
      // 检查是否有工具调用需要执行
      if (response.data.tool_calls && response.data.tool_calls.length > 0) {
        // 更新思考消息
        const updatedThinkingMessage: Message = {
          id: 'thinking-' + Date.now().toString(),
          role: 'assistant',
          content: '_正在执行工具调用..._',
          timestamp: new Date()
        };
        setMessages(prev => [...prev.filter(msg => !msg.id.startsWith('thinking-')), updatedThinkingMessage]);
        
        // 单独处理工具调用
        try {
          const toolResponse = await executeAgentTool(response.data.tool_calls);
          if (toolResponse.success && toolResponse.data) {
            // 工具调用成功，显示结果
            const assistantMessage: Message = {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              content: response.data.content || '已执行工具调用',
              timestamp: new Date(),
              toolOutputs: toolResponse.data.responses || []
            };
            
            // 移除思考消息，添加助手回复
            setIsThinking(false);
            setMessages(prev => [...prev.filter(msg => !msg.id.startsWith('thinking-')), assistantMessage]);
          } else {
            // 工具调用失败
            throw new Error(toolResponse.error || '工具调用失败');
          }
        } catch (error: any) {
          console.error('工具调用出错:', error);
          const errorMessage: Message = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: `执行工具时出错: ${error.message || '未知错误'}`,
            timestamp: new Date()
          };
          
          // 移除思考消息，添加错误消息
          setIsThinking(false);
          setMessages(prev => [...prev.filter(msg => !msg.id.startsWith('thinking-')), errorMessage]);
        }
      } else {
        // 没有工具调用，直接显示回复
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response.data.content,
          timestamp: new Date(),
          toolOutputs: response.data.tool_outputs || []
        };
        
        setMessages(prev => [...prev, assistantMessage]);
      }
      
      // 更新会话ID
      if (response.data.session_id) {
        setCurrentSession(response.data.session_id);
        
        // 刷新会话列表
        loadSessionList();
      }
      
      // 检查是否有股票代码可以点击
      if (onSelectStock && response.data.content.match(/\$[A-Z0-9\.]+/)) {
        const stockCode = response.data.content.match(/\$([A-Z0-9\.]+)/)[1];
        // 可以实现点击股票代码跳转功能
      }
    } else {
      // 移除思考消息
      setIsThinking(false);
      setMessages(prev => prev.filter(msg => !msg.id.startsWith('thinking-')));
      
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.error || '与智能助手通信时出错',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    }
  };
  
  // 键盘事件处理
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };
  
  // 新建会话
  const handleNewChat = () => {
    setCurrentSession(null);
    setMessages([
      {
        id: '1',
        role: 'assistant',
        content: '我是AlphaBot智能助手，您的专业股票分析专家。\n\n我能帮您分析市场趋势、评估个股表现、比较不同公司财务状况，并提供基于AI的量化分析。有什么可以帮到您的？',
        timestamp: new Date()
      }
    ]);
    
    // 聚焦输入框
    inputRef.current?.focus();
  };

  // 切换会话
  const switchSession = (sessionId: string) => {
    loadSessionHistory(sessionId);
  };
  
  // 复制消息内容
  const copyMessageContent = (content: string) => {
    navigator.clipboard.writeText(content);
    alert('已复制到剪贴板');
  };

  // 渲染消息列表
  const renderMessages = () => {
    return messages.map((message, index) => {
      const isUser = message.role === 'user';
      const isThinking = message.id === 'thinking';
      const isStreaming = message.id.startsWith('streaming-');
      const isLast = index === messages.length - 1;

      if (isThinking) {
        return (
          <div key="thinking" className={`flex gap-3 justify-start mb-4`}>
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

  // 渲染会话列表项
  const renderSessionItem = (session: Session) => {
    const isActive = currentSession === session.id;
    
    // 处理标题长度，超过12个字符则截断
    const displayTitle = session.title.length > 12 
      ? session.title.substring(0, 12) + "..."
      : session.title;
    
    return (
      <div 
        key={session.id}
        className={`flex items-center gap-3 p-3 cursor-pointer text-sm mb-1 ${
          isActive ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' : 'hover:bg-gray-100 dark:hover:bg-gray-800'
        } rounded-md`}
        onClick={() => switchSession(session.id)}
        title={session.title} // 鼠标悬停时显示完整标题
      >
        <MessageSquare className={`h-5 w-5 flex-shrink-0 ${isActive ? 'text-blue-600 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400'}`} />
        <div className="flex-1 min-w-0">
          <div className="font-medium truncate">{displayTitle}</div>
          <div className="text-xs text-gray-500 truncate">
            {session.last_updated ? format(new Date(session.last_updated), 'MM/dd HH:mm') : ''}
          </div>
        </div>
        <button 
          className="opacity-60 hover:opacity-100 flex-shrink-0"
          onClick={(e) => handleDeleteSession(session.id, e)}
          aria-label="删除会话"
        >
          <Trash2 className="h-4 w-4 text-red-500 dark:text-red-400" />
        </button>
      </div>
    );
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

  const renderExample = (example: {text: string, icon: React.ReactNode}) => (
    <button
      key={example.text}
      className="text-sm flex items-center px-4 py-3 rounded-md border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      onClick={() => {
        setInput(example.text);
        inputRef.current?.focus();
      }}
    >
      <span className="text-gray-500 dark:text-gray-400">{example.icon}</span>
      <span className="dark:text-gray-300">{example.text}</span>
    </button>
  );

  // 处理搜索功能
  const handleSearch = () => {
    if (!input.trim() || isLoading) return;
    
    // 先检查积分是否足够
    if (!canUseWebSearch) {
      // 积分不足，直接显示错误信息，不展示思考状态
      const insufficientPointsMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '您的积分不足，需要2000积分才能使用联网搜索功能',
        timestamp: new Date()
      };
      
      // 添加用户消息和系统回复
      setMessages(prev => [
        ...prev, 
        {
          id: Date.now().toString(),
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
    
    // 使用修改后的查询调用handleSendMessage
    setInput(searchQuery);
    setTimeout(() => handleSendMessage(), 0);
  };

  // 检查用户是否有足够积分使用联网搜索
  const canUseWebSearch = user && user.points >= 2000;

  // 切换联网搜索状态
  const toggleWebSearch = () => {
    if (!canUseWebSearch) {
      alert('您的积分不足，需要2000积分才能使用联网搜索功能');
      return;
    }
    setWebSearchEnabled(!webSearchEnabled);
  };

  return (
    <div className="flex h-[calc(100vh-60px)] bg-white dark:bg-gray-900">
      {/* 会话侧边栏 */}
      <div 
        className={`h-full border-r border-gray-200 dark:border-gray-700 ${
          showSidebar ? 'block absolute z-10 w-72 shadow-lg' : 'hidden'
        } md:block md:relative md:w-72 md:shadow-none`}
      >
        <div className="h-full flex flex-col">
          <div className="p-3 border-b border-gray-200 dark:border-gray-700">
            <Button 
              variant="outline" 
              className="w-full justify-start text-sm gap-2"
              onClick={handleNewChat}
            >
              <Plus className="h-4 w-4" />
              新建会话
            </Button>
          </div>
          
          <ScrollArea className="flex-1 p-3">
            {isFetchingSessions ? (
              <div className="flex justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-gray-400 dark:text-gray-500" />
              </div>
            ) : sessionList.length > 0 ? (
              sessionList.map(session => renderSessionItem(session))
            ) : (
              <div className="text-center py-6 text-sm text-gray-500 dark:text-gray-400">
                没有历史会话
              </div>
            )}
          </ScrollArea>
        </div>
      </div>

      {/* 主聊天区域 */}
      <div className="flex-1 flex flex-col h-full bg-white dark:bg-gray-900">
        {/* 聊天头部 */}
        <div className="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
          <div className="flex items-center">
            <Button 
              variant="ghost" 
              size="sm" 
              className="md:hidden mr-2"
              onClick={() => setShowSidebar(!showSidebar)}
            >
              <MessageSquare className="h-5 w-5" />
            </Button>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 dark:bg-blue-700">
                <Bot className="h-5 w-5 text-white" />
              </div>
              <div>
                <div className="font-medium dark:text-gray-100">AlphaBot 智能助手</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {isLoadingSession ? '正在加载会话...' : currentSession ? '会话进行中' : '新会话'}
                </div>
              </div>
            </div>
          </div>
          
          {/* 模型选择 + 联网搜索和流式传输开关 */}
          <div className="flex items-center gap-2">
            <div className="hidden md:flex items-center">
              <select
                value={model ?? ''}
                onChange={(e) => setModel(e.target.value || null)}
                className="text-xs h-8 px-2 py-1 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200"
                title="选择模型"
              >
                {availableModels.map(m => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>

            <div className="flex items-center">
              <Button
                variant={webSearchEnabled ? "primary" : "outline"}
                size="sm"
                className={`gap-1 ${!canUseWebSearch ? 'opacity-60 cursor-not-allowed' : ''}`}
                disabled={!canUseWebSearch}
                onClick={toggleWebSearch}
                title={canUseWebSearch ? "开启/关闭联网搜索" : "需要2000积分才能使用联网搜索"}
              >
                <Globe className="h-4 w-4" />
                <span className="text-xs">联网搜索</span>
                <span className={`${"ml-1 h-2 w-2 rounded-full"} ${webSearchEnabled ? 'bg-green-500' : 'bg-gray-300'}`}></span>
              </Button>
            </div>
            
            <div className="flex items-center">
              <Button
                variant={streamEnabled ? "primary" : "outline"}
                size="sm"
                className="gap-1"
                onClick={() => setStreamEnabled(!streamEnabled)}
                title="开启/关闭流式传输"
              >
                <div className="h-4 w-4 flex items-center justify-center">
                  <div className={`h-2 w-2 rounded-full ${streamEnabled ? 'bg-green-500 animate-pulse' : 'bg-gray-300'}`}></div>
                </div>
                <span className="text-xs">流式传输</span>
              </Button>
            </div>
          </div>
        </div>

        {/* 消息区域 */}
        <div className="flex-1 overflow-auto bg-gray-50 dark:bg-gray-800">
          {isLoadingSession ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-8 w-8 animate-spin text-blue-600 dark:text-blue-400" />
            </div>
          ) : (
            <>
              {renderMessages()}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>
        
        {/* 输入区域 */}
        <div className="p-3 md:p-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
          {messages.length === 1 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2 md:gap-3 mb-4">
              {examples.map(renderExample)}
            </div>
          )}
          
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入您的问题或使用 /search 进行网络搜索..."
              disabled={isLoading || isLoadingSession}
              className="flex-1 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            />
            
            <Button 
              onClick={handleSendMessage} 
              disabled={!input.trim() || isLoading || isLoadingSession}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
          
          <div className="text-xs text-center text-gray-400 dark:text-gray-500 mt-2">
            结果仅供参考，不构成投资建议
          </div>
        </div>
      </div>
    </div>
  );
} 