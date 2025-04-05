'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Loader2, Send, Bot, User, Sparkles, TrendingUp, BarChart2, PieChart, LineChart } from 'lucide-react';
import { useAuth } from '@/lib/contexts/AuthContext';
import { chatWithAgent } from '@/lib/api';
import ReactMarkdown from 'react-markdown';

interface AgentChatProps {
  onSelectStock?: (symbol: string) => void;
}

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

export default function AgentChat({ onSelectStock }: AgentChatProps) {
  const { isAuthenticated } = useAuth();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentSession, setCurrentSession] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
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
  
  // 滚动到最新消息
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  
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
          timestamp: new Date()
        };
        
        setMessages(prev => [...prev, assistantMessage]);
        
        // 更新会话ID
        if (response.data.session_id) {
          setCurrentSession(response.data.session_id);
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
  
  // 渲染消息
  const renderMessage = (message: Message, index: number) => {
    const isUser = message.role === 'user';
    const isThinking = message.id.startsWith('thinking-');
    
    return (
      <div
        key={message.id}
        className={`flex w-full ${isUser ? 'bg-gray-50 dark:bg-gray-800/50' : 'bg-white dark:bg-gray-900'} border-b border-gray-100 dark:border-gray-800`}
      >
        <div className="w-full max-w-4xl mx-auto flex gap-4 p-4 md:p-6">
          <div className="flex-shrink-0 mt-1">
            {isUser ? (
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gray-300 dark:bg-gray-700">
                <User className="h-4 w-4 text-gray-800 dark:text-gray-200" />
              </div>
            ) : (
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600">
                <Bot className="h-4 w-4 text-white" />
              </div>
            )}
          </div>
          
          <div className={`flex-1 prose prose-sm max-w-none dark:prose-invert ${isThinking ? 'animate-pulse' : ''}`}>
            <ReactMarkdown
              components={{
                a: ({ node, ...props }) => {
                  // 检查链接是否包含股票代码格式
                  const isStockLink = props.href?.startsWith('#stock:');
                  if (isStockLink && onSelectStock && props.href) {
                    const stockCode = props.href.replace('#stock:', '');
                    return (
                      <button
                        className="text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center"
                        onClick={() => onSelectStock(stockCode)}
                      >
                        <TrendingUp className="h-3 w-3 mr-1" />
                        {props.children}
                      </button>
                    );
                  }
                  return <a {...props} className="text-blue-600 dark:text-blue-400 hover:underline" />;
                }
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        </div>
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
      className="text-sm flex items-center px-4 py-3 rounded-md border border-gray-200 dark:border-gray-800 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      onClick={() => {
        setInput(example.text);
        inputRef.current?.focus();
      }}
    >
      <span className="text-gray-500 dark:text-gray-400">{example.icon}</span>
      <span>{example.text}</span>
    </button>
  );
  
  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-white dark:bg-gray-900">
      {/* 消息区域 */}
      <div className="flex-1 overflow-auto">
        <div>
          {messages.length > 0 && messages.map((message, i) => renderMessage(message, i))}
          <div ref={messagesEndRef} />
        </div>
        
        {/* 若无消息，显示欢迎界面和示例 */}
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center p-6">
            <div className="flex items-center justify-center mb-6">
              <div className="bg-blue-600 p-3 rounded-full">
                <Bot className="h-8 w-8 text-white" />
              </div>
            </div>
            <h1 className="text-2xl font-semibold mb-3 text-center">
              AlphaBot 智能股票分析助手
            </h1>
            <p className="text-gray-500 dark:text-gray-400 mb-8 text-center max-w-lg">
              您的专业投资决策伙伴，提供股票分析、市场洞察和投资建议
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 w-full max-w-xl mb-4">
              {examples.map(renderExample)}
            </div>
          </div>
        )}
      </div>
      
      {/* 输入区域 */}
      <div className="border-t border-gray-200 dark:border-gray-800 p-3 sticky bottom-0 bg-white dark:bg-gray-900">
        <div className="max-w-4xl mx-auto relative">
          <form 
            onSubmit={(e) => { 
              e.preventDefault();
              handleSendMessage();
            }}
            className="relative"
          >
            <Input
              ref={inputRef}
              placeholder="输入您的问题..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              className="pr-12 py-3 pl-4 rounded-lg border-gray-300 dark:border-gray-700 shadow-sm focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:border-blue-500"
            />
            <Button 
              type="submit"
              onClick={handleSendMessage} 
              disabled={!input.trim() || isLoading}
              size="sm"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md h-8 w-8 p-0 bg-blue-600 hover:bg-blue-700"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </form>
          
          {messages.length > 1 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleNewChat}
              className="absolute -top-12 left-0 text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-300 dark:hover:bg-gray-800"
            >
              <Sparkles className="h-4 w-4 mr-1" />
              新对话
            </Button>
          )}
        </div>
        <div className="text-xs text-center mt-2 text-gray-500 dark:text-gray-400">
          结果仅供参考，不构成投资建议
        </div>
      </div>
    </div>
  );
} 