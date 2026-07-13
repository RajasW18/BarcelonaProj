/**
 * useChat — chat state management + SSE streaming hook
 *
 * Manages messages array, sends to /chat endpoint, reads the
 * Server-Sent Events stream and updates the last assistant message
 * in real time as tokens arrive.
 */
import { useState, useCallback, useRef } from 'react'

export type MessageRole = 'user' | 'assistant'

export interface Message {
  id: string
  role: MessageRole
  content: string
  toolCalls?: string[]   // names of tools called during this response
  isStreaming?: boolean
}

interface UseChatReturn {
  messages: Message[]
  isStreaming: boolean
  activeTools: string[]
  sendMessage: (text: string) => Promise<void>
  clearMessages: () => void
}

let _sessionId: string | null = null

function getSessionId(): string {
  if (!_sessionId) {
    _sessionId =
      sessionStorage.getItem('barca_session_id') ||
      crypto.randomUUID()
    sessionStorage.setItem('barca_session_id', _sessionId)
  }
  return _sessionId
}

function createId(): string {
  return Math.random().toString(36).slice(2)
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [activeTools, setActiveTools] = useState<string[]>([])
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return

    // Add user message
    const userMsg: Message = {
      id: createId(),
      role: 'user',
      content: text.trim(),
    }

    // Placeholder assistant message to stream into
    const assistantId = createId()
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      toolCalls: [],
      isStreaming: true,
    }

    setMessages(prev => [...prev, userMsg, assistantMsg])
    setIsStreaming(true)
    setActiveTools([])

    abortRef.current = new AbortController()

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text.trim(), session_id: getSessionId() }),
        signal: abortRef.current.signal,
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue

          try {
            const event = JSON.parse(raw)

            if (event.type === 'token') {
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? { ...m, content: m.content + event.content }
                    : m
                )
              )
            } else if (event.type === 'tool_call') {
              setActiveTools(prev => [...new Set([...prev, event.tool])])
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? { ...m, toolCalls: [...(m.toolCalls ?? []), event.tool] }
                    : m
                )
              )
            } else if (event.type === 'error') {
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? { ...m, content: `⚠️ Error: ${event.content ?? 'Something went wrong. Please try again.'}` }
                    : m
                )
              )
              break
            } else if (event.type === 'done') {
              break
            }
          } catch {
            // non-JSON line, skip
          }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId
              ? { ...m, content: '⚠️ Connection error. Please try again.' }
              : m
          )
        )
      }
    } finally {
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId ? { ...m, isStreaming: false } : m
        )
      )
      setIsStreaming(false)
      setActiveTools([])
    }
  }, [isStreaming])

  const clearMessages = useCallback(() => {
    setMessages([])
    sessionStorage.removeItem('barca_session_id')
    _sessionId = null
  }, [])

  return { messages, isStreaming, activeTools, sendMessage, clearMessages }
}
