import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Bot, User } from 'lucide-react';
import { Message } from '../../types/chat';
import { Card } from '../ui/card';

interface AgentMessageDisplayProps {
  message: Message;
  isLast: boolean;
}

// Utility function for class names
const cn = (...classes: string[]) => classes.filter(Boolean).join(' ');

export function AgentMessageDisplay({ message, isLast }: AgentMessageDisplayProps) {
  const isUser = message.role === 'user';
  const isAgent = message.role === 'assistant';
  
  // 渲染工具输出结果
  const renderToolOutputs = () => {
    if (!message.toolOutputs || message.toolOutputs.length === 0) {
      return null;
    }
    
    return (
      <div className="mt-3 space-y-3">
        {message.toolOutputs.map((output: string, index: number) => (
          <Card key={index} className="p-3 bg-muted/50 text-sm">
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <ReactMarkdown>{output}</ReactMarkdown>
            </div>
          </Card>
        ))}
      </div>
    );
  };

  return (
    <div className={cn('flex items-start gap-3 py-4', isUser ? 'justify-end' : 'justify-start')}>
      {/* 机器人头像 - 仅在非用户消息时显示 */}
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white shrink-0">
          <Bot className="h-4 w-4" />
        </div>
      )}

      {/* 消息内容 */}
      <div className={cn('max-w-[80%]')}>
        <div
          className={cn(
            'px-4 py-3 rounded-lg shadow-sm',
            isUser
              ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white' 
              : 'bg-card border border-border'
          )}
        >
          <div className={cn(
            'prose prose-sm max-w-none',
            isUser ? 'dark:prose-invert prose-headings:text-white prose-p:text-white' : 'dark:prose-invert'
          )}>
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        </div>
        
        {/* 渲染工具输出 */}
        {isAgent && renderToolOutputs()}
      </div>

      {/* 用户头像 - 仅在用户消息时显示 */}
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-gray-700 dark:text-gray-300 shadow-sm shrink-0">
          <User className="h-4 w-4" />
        </div>
      )}
    </div>
  );
} 