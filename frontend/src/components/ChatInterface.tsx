/**
 * ChatInterface — the main chat UI component.
 *
 * Layout:
 *   ┌──────────────┬──────────────────────────────────┐
 *   │   Sidebar    │          Message Area             │
 *   │  (branding,  │  [messages scroll area]           │
 *   │   examples,  │  [input bar + voice button]       │
 *   │   history)   │                                   │
 *   └──────────────┴──────────────────────────────────┘
 */
import { useState, useRef, useEffect, useCallback, type KeyboardEvent } from 'react'
import {
  Send, Trash2, Zap, ChevronRight, Paperclip, Globe, X, FileText, Image as ImageIcon,
  Sparkles, ArrowLeft, Trophy, BarChart3, Shield
} from 'lucide-react'
import { useChat } from '../hooks/useChat'
import { MessageBubble } from './MessageBubble'
import { TypingIndicator } from './TypingIndicator'
import { VoiceButton } from './VoiceButton'
import { apiFetch } from '../lib/api'

const SUGGESTED_QUESTIONS = [
  { icon: <Trophy size={14} />, text: "What are the latest league standings?" },
  { icon: <BarChart3 size={14} />, text: "Compare two teams' recent form" },
  { icon: <Shield size={14} />, text: "Explain a 4-3-3 pressing structure" },
  { icon: <FileText size={14} />, text: "Analyze this match report" },
]

const WELCOME_MESSAGE = `**Welcome to Ninety.**

I'm your football intelligence workspace. I can help you with:

- Live standings, fixtures, scores, and player statistics
- Tactical analysis and match explanations
- Player, club, and competition context
- Reports, images, and public URLs you attach

Ask about the game, or attach context when you want a grounded analysis.

Your context stays in this browser session.`

export function ChatInterface({ onBack, onLogout }: { onBack?: () => void; onLogout?: () => void }) {
  const { messages, sessions, isStreaming, activeTools, sendMessage, clearMessages, selectSession, createNewSession, signOut } = useChat()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [url, setUrl] = useState('')
  const [processingAttachments, setProcessingAttachments] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }, [input])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if ((!text && pendingFiles.length === 0 && !url.trim()) || isStreaming) return
    setInput('')
    let context = ''
    let sources: string[] = []
    if (pendingFiles.length || url.trim()) {
      setProcessingAttachments(true)
      try {
        const form = new FormData()
        pendingFiles.forEach(file => form.append('files', file))
        if (url.trim()) form.append('url', url.trim())
        const response = await apiFetch('/attachments/prepare', { method: 'POST', body: form, credentials: 'include' })
        if (!response.ok) {
          const error = await response.json().catch(() => ({}))
          throw new Error(error.detail ?? 'Could not process attachments.')
        }
        const prepared = await response.json()
        context = prepared.context ?? ''
        sources = prepared.sources ?? []
      } catch (error) {
        setInput(error instanceof Error ? error.message : 'Attachment processing failed.')
        setProcessingAttachments(false)
        return
      }
      setPendingFiles([])
      setUrl('')
      setProcessingAttachments(false)
    }
    await sendMessage(text || 'Analyze the attached context.', context, sources)
  }, [input, isStreaming, pendingFiles, url, sendMessage])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleTranscript = useCallback((text: string) => {
    setInput(text)
    // Auto-send after a brief delay to let user see the transcript
    setTimeout(() => {
      sendMessage(text)
      setInput('')
    }, 600)
  }, [sendMessage])

  const handleSuggestion = (text: string) => {
    setInput(text)
    textareaRef.current?.focus()
  }

  const showWelcome = messages.length === 0

  return (
    <div className="football-app-shell flex min-h-[100dvh] overflow-hidden bg-[var(--color-barca-dark)]">
      {/* ── Sidebar ──────────────────────────────────────────────── */}
      <aside
        className={[
          'flex flex-col flex-shrink-0 transition-all duration-300 ease-in-out',
          'glass-strong border-r border-[var(--color-barca-border)]',
          sidebarOpen ? 'w-64' : 'w-0 overflow-hidden',
        ].join(' ')}
      >
        {/* Club branding */}
        <div className="p-5 border-b border-[var(--color-barca-border)]">
          {/* Barça stripe bar */}
          <div className="barca-stripe h-1 rounded-full mb-4 opacity-80" />

          <div className="flex items-center gap-3 mb-1">
            {/* Shield icon */}
            <div className="relative w-10 h-10 flex items-center justify-center blaugrana-gradient rounded-xl shadow-lg">
              <Sparkles size={18} />
            </div>
            <div>
              <h1 className="font-bold text-[var(--color-barca-text)] text-sm leading-tight">
                Ninety
              </h1>
              <p className="text-[10px] text-[var(--color-barca-muted)]">
                Match intelligence
              </p>
            </div>
          </div>
        </div>

        {/* Suggested questions */}
        <div className="p-4 flex-1 overflow-y-auto">
          <button onClick={() => createNewSession()} className="new-chat-button"><span>+</span> New chat</button>
          <p className="history-label">History</p>
          <div className="history-list">
            {sessions.map(session => (
              <button key={session.id} onClick={() => selectSession(session.id)} className="history-item">
                <span>{session.title}</span>
              </button>
            ))}
            {sessions.length === 0 && <p className="history-empty">Your saved chats will appear here.</p>}
          </div>
          <p className="text-[10px] uppercase tracking-widest text-[var(--color-barca-muted)] mb-3 font-semibold">
            Try asking…
          </p>
          <div className="space-y-2">
            {SUGGESTED_QUESTIONS.map((q, i) => (
              <button
                key={i}
                onClick={() => handleSuggestion(q.text)}
                className="w-full text-left px-3 py-2.5 rounded-xl text-xs text-[var(--color-barca-muted)] 
                  hover:text-[var(--color-barca-text)] hover:bg-[var(--color-barca-blue)]/10
                  border border-transparent hover:border-[var(--color-barca-blue)]/20
                  transition-all duration-200 flex items-center gap-2 group"
              >
                <span className="text-[var(--color-barca-blue)] flex-shrink-0">{q.icon}</span>
                <span className="flex-1">{q.text}</span>
                <ChevronRight size={10} className="opacity-0 group-hover:opacity-100 transition-opacity" />
              </button>
            ))}
          </div>
        </div>

        {/* Clear chat */}
        <div className="p-4 border-t border-[var(--color-barca-border)]">
          <button
            onClick={async () => { await signOut(); onLogout?.() }}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs text-[var(--color-barca-muted)] hover:text-[var(--color-barca-text)] hover:bg-white/5 transition-all duration-200"
          >
            Sign out
          </button>
          <button
            onClick={clearMessages}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl 
              text-xs text-[var(--color-barca-muted)] hover:text-[var(--color-barca-red)]
              hover:bg-[var(--color-barca-red)]/10 transition-all duration-200 border border-transparent
              hover:border-[var(--color-barca-red)]/20"
          >
            <Trash2 size={12} />
            Clear conversation
          </button>
        </div>
      </aside>

      {/* ── Main Chat Area ───────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="flex items-center gap-3 px-4 py-3 border-b border-[var(--color-barca-border)] glass-strong flex-shrink-0">
          <button
            onClick={() => setSidebarOpen(o => !o)}
            className="p-1.5 rounded-lg text-[var(--color-barca-muted)] hover:text-[var(--color-barca-text)]
              hover:bg-white/5 transition-colors"
            aria-label="Toggle sidebar"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M1 3h14M1 8h14M1 13h14" stroke="currentColor" strokeWidth="1.5"
                strokeLinecap="round" fill="none" />
            </svg>
          </button>
          {onBack && (
            <button
              onClick={onBack}
              className="p-1.5 rounded-lg text-[var(--color-barca-muted)] hover:text-[var(--color-barca-text)] hover:bg-white/5 transition-colors"
              aria-label="Back to home"
              title="Back to home"
            >
              <ArrowLeft size={16} />
            </button>
          )}

          <div className="h-5 w-px bg-[var(--color-barca-border)]" />

          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-sm font-medium text-[var(--color-barca-text)]">Ninety</span>
            <span className="text-xs text-[var(--color-barca-muted)]">• Qwen 2.5</span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            {isStreaming && (
              <span className="text-xs text-[var(--color-barca-blue)] animate-pulse">
                Thinking…
              </span>
            )}
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
          {/* Decorative background blobs */}
          <div className="fixed inset-0 pointer-events-none overflow-hidden -z-10">
            <div
              className="absolute -top-40 -right-40 w-96 h-96 opacity-5 rounded-full"
              style={{ background: 'var(--color-barca-blue)', animation: 'blob 8s ease-in-out infinite' }}
            />
            <div
              className="absolute -bottom-40 -left-40 w-96 h-96 opacity-5 rounded-full"
              style={{ background: 'var(--color-barca-red)', animation: 'blob 10s ease-in-out infinite 2s' }}
            />
          </div>

          {/* Welcome state */}
          {showWelcome && (
            <div className="flex flex-col items-center justify-center h-full text-center py-16 animate-[fadeIn_0.5s_ease-out]">
              <div className="w-20 h-20 blaugrana-gradient rounded-2xl flex items-center justify-center mb-6 shadow-2xl glow-blue">
                <Sparkles size={22} />
              </div>
              <h2 className="text-2xl font-bold blaugrana-text mb-2">Ninety</h2>
              <p className="text-sm text-[var(--color-barca-muted)] mb-8">
                Your matchday intelligence desk
              </p>

              <div className="max-w-md glass rounded-2xl p-5 text-left text-sm text-[var(--color-barca-text)]/80 leading-relaxed">
                <ReactMarkdownWelcome content={WELCOME_MESSAGE} />
              </div>
            </div>
          )}

          {/* Message list */}
          {messages.map(msg => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {/* Typing indicator */}
          {isStreaming && messages[messages.length - 1]?.role === 'user' && (
            <TypingIndicator activeTools={activeTools} />
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <div className="flex-shrink-0 px-4 pb-4 pt-2 border-t border-[var(--color-barca-border)]">
          <div className="max-w-4xl mx-auto">
            <div
              className={[
                'flex items-end gap-2 p-2 rounded-2xl glass transition-all duration-200',
                'focus-within:border-[var(--color-barca-blue)]/50 focus-within:shadow-[0_0_0_1px_rgba(0,77,152,0.3)]',
              ].join(' ')}
            >
              <textarea
                ref={textareaRef}
                id="chat-input"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about the game…"
                disabled={isStreaming || processingAttachments}
                rows={1}
                className="flex-1 bg-transparent resize-none outline-none text-sm 
                  text-[var(--color-barca-text)] placeholder-[var(--color-barca-muted)]
                  min-h-[40px] max-h-[160px] py-2.5 px-2 leading-relaxed
                  disabled:opacity-50"
                style={{ scrollbarWidth: 'none' }}
              />

              <div className="flex items-center gap-1 flex-shrink-0 pb-1">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.docx,.txt,.md,.csv,.json,.py,.ts,.tsx,.js,.jsx,.html,.css,.sql,image/*"
                  className="hidden"
                  onChange={event => {
                    setPendingFiles(prev => [...prev, ...Array.from(event.target.files ?? [])])
                    event.target.value = ''
                  }}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isStreaming || processingAttachments}
                  title="Attach files or images"
                  className="p-2.5 rounded-xl text-[var(--color-barca-muted)] hover:text-[var(--color-barca-text)] hover:bg-white/5 disabled:opacity-40"
                >
                  <Paperclip size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const value = window.prompt('Paste a public website URL to analyze')
                    if (value?.trim()) setUrl(value.trim())
                  }}
                  disabled={isStreaming || processingAttachments}
                  title="Add a website URL"
                  className="p-2.5 rounded-xl text-[var(--color-barca-muted)] hover:text-[var(--color-barca-text)] hover:bg-white/5 disabled:opacity-40"
                >
                  <Globe size={16} />
                </button>
                <VoiceButton onTranscript={handleTranscript} disabled={isStreaming} />

                <button
                  id="send-btn"
                  onClick={handleSend}
                  disabled={(!input.trim() && !pendingFiles.length && !url.trim()) || isStreaming || processingAttachments}
                  aria-label="Send message"
                  className={[
                    'p-2.5 rounded-xl transition-all duration-200',
                    input.trim() && !isStreaming
                      ? 'blaugrana-gradient text-white shadow-md hover:opacity-90 hover:scale-105 active:scale-95'
                      : 'text-[var(--color-barca-muted)] cursor-not-allowed opacity-40',
                  ].join(' ')}
                >
                  <Send size={16} />
                </button>
              </div>
            </div>

            {(pendingFiles.length > 0 || url) && (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                {pendingFiles.map((file, index) => (
                  <span key={`${file.name}-${index}`} className="inline-flex items-center gap-1 rounded-lg border border-[var(--color-barca-border)] bg-white/5 px-2 py-1">
                    <FileText size={12} /> {file.name}
                    <button type="button" onClick={() => setPendingFiles(files => files.filter((_, i) => i !== index))} aria-label={`Remove ${file.name}`}>
                      <X size={12} />
                    </button>
                  </span>
                ))}
                {url && (
                  <span className="inline-flex items-center gap-1 rounded-lg border border-[var(--color-barca-border)] bg-white/5 px-2 py-1">
                    <Globe size={12} /> {url}
                    <button type="button" onClick={() => setUrl('')} aria-label="Remove URL"><X size={12} /></button>
                  </span>
                )}
                <span className="text-[var(--color-barca-muted)]">
                  Attachments will be analyzed when you press send.
                </span>
              </div>
            )}

            <p className="text-center text-[10px] text-[var(--color-barca-muted)] mt-2">
              {processingAttachments ? 'Preparing context…' : <>Press <kbd className="px-1 py-0.5 rounded bg-white/5 text-[9px]">Enter</kbd> to send •{' '}
              <kbd className="px-1 py-0.5 rounded bg-white/5 text-[9px]">Shift+Enter</kbd> for new line
              </>}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// Inline minimal markdown renderer for the welcome message
function ReactMarkdownWelcome({ content }: { content: string }) {
  const lines = content.split('\n')
  return (
    <div className="space-y-1">
      {lines.map((line, i) => {
        if (line.startsWith('**') && line.endsWith('**')) {
          return <p key={i} className="font-bold text-[var(--color-barca-text)]">{line.slice(2, -2)}</p>
        }
        if (line.startsWith('- ')) {
          const inner = line.slice(2).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
          return <li key={i} className="list-none flex gap-1" dangerouslySetInnerHTML={{ __html: inner }} />
        }
        if (!line.trim()) return <div key={i} className="h-1" />
        const inner = line.replace(/\*\*(.*?)\*\*/g, '<strong class="text-[var(--color-barca-gold)]">$1</strong>')
          .replace(/\*(.*?)\*/g, '<em>$1</em>')
        return <p key={i} dangerouslySetInnerHTML={{ __html: inner }} />
      })}
    </div>
  )
}
