import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import { cn } from '@/lib/utils';
import { CodeHighlight } from 'components/CodeHighlight';
import type { ChatMessage as ChatMessageType } from 'utils/workspaceStore';

interface Props {
  message: ChatMessageType;
}

/**
 * Individual chat message component
 * Displays user or AI messages with markdown and code syntax highlighting
 */
export const ChatMessage = memo(({ message }: Props) => {
  const isUser = message.role === 'user';
  const timestamp = new Date(message.timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div
      className={cn(
        'flex w-full gap-3 py-4 px-4',
        isUser ? 'justify-end' : 'justify-start'
      )}
    >
      <div className={cn('flex gap-3 max-w-[80%]', isUser && 'flex-row-reverse')}>
        {/* Avatar */}
        <div
          className={cn(
            'flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-semibold',
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-gradient-to-br from-purple-500 to-pink-500 text-white'
          )}
        >
          {isUser ? 'U' : 'AI'}
        </div>

        {/* Message content */}
        <div className="flex-1 space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {isUser ? 'You' : 'AI Assistant'}
            </span>
            <span className="text-xs text-muted-foreground">{timestamp}</span>
          </div>

          <div
            className={cn(
              'rounded-lg px-4 py-3',
              isUser
                ? 'bg-blue-600/10 border border-blue-600/20'
                : 'bg-muted border border-border'
            )}
          >
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown
                components={{
                  code({ node, inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    const language = match ? match[1] : 'text';
                    const codeString = String(children).replace(/\n$/, '');

                    return !inline && match ? (
                      <CodeHighlight 
                        code={codeString}
                        language={language}
                        className="rounded-md my-2"
                      />
                    ) : (
                      <code
                        className={cn(
                          'bg-muted px-1.5 py-0.5 rounded text-xs font-mono',
                          className
                        )}
                        {...props}
                      >
                        {children}
                      </code>
                    );
                  },
                  p({ children }) {
                    return <p className="mb-2 last:mb-0">{children}</p>;
                  },
                  ul({ children }) {
                    return <ul className="list-disc list-inside mb-2">{children}</ul>;
                  },
                  ol({ children }) {
                    return <ol className="list-decimal list-inside mb-2">{children}</ol>;
                  },
                  li({ children }) {
                    return <li className="mb-1">{children}</li>;
                  },
                  h1({ children }) {
                    return <h1 className="text-lg font-bold mb-2">{children}</h1>;
                  },
                  h2({ children }) {
                    return <h2 className="text-base font-bold mb-2">{children}</h2>;
                  },
                  h3({ children }) {
                    return <h3 className="text-sm font-bold mb-2">{children}</h3>;
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

ChatMessage.displayName = 'ChatMessage';
