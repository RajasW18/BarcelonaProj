/**
 * MessageBubble — renders a single chat message.
 *
 * User messages: right-aligned, Blaugrana gradient background.
 * Assistant messages: left-aligned, glassmorphism card with markdown support.
 * Shows tool badges when the agent used tools to answer.
 */
import ReactMarkdown from 'react-markdown'
import { Database, BookOpen } from 'lucide-react'
import type { Message } from '../hooks/useChat'

interface MessageBubbleProps {
  message: Message
}

const TOOL_BADGES: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  sql_query: {
    icon: <Database size={10} />,
    label: 'Database',
    color: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  },
  barca_knowledge: {
    icon: <BookOpen size={10} />,
    label: 'Knowledge Base',
    color: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
  },
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end animate-[slideUp_0.3s_ease-out]">
        <div className="max-w-[75%] lg:max-w-[60%]">
          <div className="px-4 py-3 rounded-2xl rounded-tr-sm blaugrana-gradient text-white text-sm leading-relaxed shadow-lg">
            {message.content}
          </div>
        </div>
      </div>
    )
  }

  // Assistant message
  return (
    <div className="flex items-start gap-3 animate-[slideUp_0.3s_ease-out]">
      {/* Avatar */}
      <div className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center blaugrana-gradient text-white text-xs font-bold shadow-md">
        B
      </div>

      <div className="flex-1 min-w-0 max-w-[80%] lg:max-w-[70%]">
        {/* Tool badges */}
        {(message.toolCalls ?? []).length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {[...new Set(message.toolCalls)].map(tool => {
              const badge = TOOL_BADGES[tool]
              if (!badge) return null
              return (
                <span
                  key={tool}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${badge.color}`}
                >
                  {badge.icon}
                  {badge.label}
                </span>
              )
            })}
          </div>
        )}

        {/* Message content */}
        <div className="px-4 py-3 rounded-2xl rounded-tl-sm glass text-sm leading-relaxed">
          {message.content ? (
            <ReactMarkdown
              components={{
                p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                strong: ({ children }) => (
                  <strong className="font-semibold text-[var(--color-barca-gold)]">{children}</strong>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>
                ),
                li: ({ children }) => (
                  <li className="text-[var(--color-barca-text)]/90">{children}</li>
                ),
                code: ({ children, className }) => {
                  const isBlock = className?.includes('language-')
                  return isBlock ? (
                    <pre className="bg-black/30 rounded-lg p-3 overflow-x-auto text-xs my-2 border border-[var(--color-barca-border)]">
                      <code>{children}</code>
                    </pre>
                  ) : (
                    <code className="bg-black/30 rounded px-1.5 py-0.5 text-xs text-[var(--color-barca-gold)] font-mono">
                      {children}
                    </code>
                  )
                },
                h3: ({ children }) => (
                  <h3 className="font-semibold text-[var(--color-barca-text)] mb-1 mt-2">{children}</h3>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="border-l-2 border-[var(--color-barca-blue)] pl-3 my-2 text-[var(--color-barca-muted)]">
                    {children}
                  </blockquote>
                ),
                hr: () => (
                  <hr className="border-[var(--color-barca-border)] my-3" />
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          ) : (
            <span className="opacity-0">…</span>
          )}

          {/* Streaming cursor */}
          {message.isStreaming && message.content && (
            <span className="inline-block w-0.5 h-4 bg-[var(--color-barca-blue)] animate-pulse ml-0.5 align-text-bottom" />
          )}
        </div>
      </div>
    </div>
  )
}
