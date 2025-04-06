'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Loader2, Send, Bot, User, TrendingUp, BarChart2, PieChart, LineChart, Plus, Trash2, MessageSquare, Copy, Search } from 'lucide-react';
import { useAuth } from '@/lib/contexts/AuthContext';
import { chatWithAgent, getAgentSessions, getAgentSessionHistory, deleteAgentSession, searchWeb } from '@/lib/api';
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
  const { isAuthenticated } = useAuth();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentSession, setCurrentSession] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [sessionList, setSessionList] = useState<Session[]>([]);
  const [showSidebar, setShowSidebar] = useState<boolean>(false);
  const [isFetchingSessions, setIsFetchingSessions] = useState<boolean>(false);
  const [isLoadingSession, setIsLoadingSession] = useState<boolean>(false);
  
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
  useEffect(() => {
    if (isAuthenticated) {
      loadSessionList();
    }
  }, [isAuthenticated]);
  
  // 滚动到最新消息
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 加载会话列表
  const loadSessionList = async () => {
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
  };

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
    
    // 显示思考状态
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
    
    try {
      const response = await chatWithAgent({ 
        content: input,
        session_id: currentSession || undefined
      });
      
      if (response.success && response.data) {
        // 移除思考消息
        setIsThinking(false);
        setMessages(prev => prev.filter(msg => !msg.id.startsWith('thinking-')));
        
        // 添加助手回复
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response.data.content,
          timestamp: new Date(),
          toolOutputs: response.data.tool_outputs || []
        };
        
        setMessages(prev => [...prev, assistantMessage]);
        
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
        
        alert(response.error || '与智能助手通信时出错');
      }
    } catch (error) {
      // 移除思考消息
      setIsThinking(false);
      setMessages(prev => prev.filter(msg => !msg.id.startsWith('thinking-')));
      
      console.error('发送消息错误:', error);
      alert('与服务器通信时出错');
    } finally {
      setIsLoading(false);
      // 聚焦输入框以便继续对话
      inputRef.current?.focus();
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

    return (
      <div 
        key={session.id}
        className={`flex items-center gap-3 p-3 cursor-pointer text-sm mb-1 ${
          isActive ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' : 'hover:bg-gray-100 dark:hover:bg-gray-800'
        }`}
        onClick={() => switchSession(session.id)}
      >
        <MessageSquare className={`h-5 w-5 ${isActive ? 'text-blue-600 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400'}`} />
        <div className="flex-1 overflow-hidden">
          <div className="font-medium truncate">{session.title}</div>
        </div>
        <button 
          className="opacity-60 hover:opacity-100"
          onClick={(e) => handleDeleteSession(session.id, e)}
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
    
    // 如果不是以/search开头，自动添加
    const searchQuery = input.trim().startsWith('/search')
      ? input.trim()
      : `/search ${input.trim()}`;
    
    // 使用修改后的查询调用handleSendMessage
    setInput(searchQuery);
    setTimeout(() => handleSendMessage(), 0);
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
        <div className="flex items-center p-3 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
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
              placeholder="输入您的问题..."
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