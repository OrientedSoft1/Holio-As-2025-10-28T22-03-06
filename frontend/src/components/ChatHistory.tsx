import { useEffect, useRef } from 'react';
import { ChatMessage } from 'components/ChatMessage';
import type { ChatMessage as ChatMessageType } from 'utils/workspaceStore';
import { ScrollArea } from '@/components/ui/scroll-area';

interface Props {
  messages: ChatMessageType[];
  isLoading?: boolean;
}

/**
 * Chat history component
 * Displays a scrollable list of chat messages
 */
export const ChatHistory = ({ messages, isLoading }: Props) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <ScrollArea className="flex-1 h-full">
      <div ref={scrollRef} className="flex flex-col">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full p-8">
            <div className="text-center space-y-2">
              <div className="text-4xl mb-4">🚀</div>
              <h3 className="text-lg font-semibold text-foreground">
                Start Building Your App
              </h3>
              <p className="text-sm text-muted-foreground max-w-md">
                Describe what you want to build in natural language, and I'll help you
                create it step by step.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-0">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {isLoading && (
              <div className="flex gap-3 py-4 px-4">
                <div className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-semibold bg-gradient-to-br from-purple-500 to-pink-500 text-white">
                  AI
                </div>
                <div className="flex-1 space-y-1">
                  <div className="text-xs text-muted-foreground">AI Assistant</div>
                  <div className="rounded-lg px-4 py-3 bg-muted border border-border">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </ScrollArea>
  );
};
