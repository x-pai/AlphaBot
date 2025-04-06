import React, { useState, FormEvent, KeyboardEvent } from 'react';
import { SendHorizontal, Search } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';

interface ChatInputProps {
  onSubmit: (message: string) => void;
  isLoading: boolean;
  placeholder?: string;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSubmit,
  isLoading,
  placeholder = '输入消息或以 /search 开头进行网络搜索...'
}) => {
  const [message, setMessage] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isLoading) {
      onSubmit(message);
      setMessage('');
    }
  };

  const handleSearch = () => {
    if (!isLoading && message.trim()) {
      // 如果不是以/search开头，自动添加
      const searchQuery = message.trim().startsWith('/search')
        ? message.trim()
        : `/search ${message.trim()}`;
      onSubmit(searchQuery);
      setMessage('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="border rounded-lg flex items-end overflow-hidden bg-background">
        <Textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="min-h-[60px] max-h-[200px] border-0 focus-visible:ring-0 resize-none py-3 px-4"
          disabled={isLoading}
        />
        <div className="p-2 flex gap-1">
          <Button 
            type="button" 
            variant="ghost" 
            size="sm" 
            onClick={handleSearch}
            disabled={isLoading || !message.trim()}
            title="搜索网络"
          >
            <Search className="h-5 w-5" />
          </Button>
          <Button 
            type="submit" 
            variant="ghost" 
            size="sm" 
            disabled={isLoading || !message.trim()}
          >
            <SendHorizontal className="h-5 w-5" />
          </Button>
        </div>
      </div>
    </form>
  );
}; 