/**
 * useChat — chat state management + SSE streaming hook
 *
 * Manages messages array, sends to /chat endpoint, reads the
 * Server-Sent Events stream and updates the last assistant message
 * in real time as tokens arrive.
 */
import { useState, useCallback, useRef, useEffect } from 'react'
import { apiFetch } from '../lib/api'

export type MessageRole = 'user' | 'assistant'

export interface Message {
  id: string
  role: MessageRole
  content: string
  toolCalls?: string[]   // names of tools called during this response
  isStreaming?: boolean
  sources?: string[]
}

interface UseChatReturn {
  messages: Message[]
  sessions: ChatSession[]
  activeSessionId: string | null
  isStreaming: boolean
  activeTools: string[]
  sendMessage: (text: string, context?: string, sources?: string[]) => Promise<void>
  clearMessages: () => Promise<void>
  selectSession: (id: string) => Promise<void>
  createNewSession: () => Promise<void>
  signOut: () => Promise<void>
}

export interface ChatSession { id: string; title: string; updated_at: string }

function createId(): string {
  return Math.random().toString(36).slice(2)
}

function normalizeSources(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.filter((source): source is string => typeof source === 'string')
  }
  if (typeof value !== 'string' || !value.trim()) return []

  try {
    const parsed: unknown = JSON.parse(value)
    if (Array.isArray(parsed)) {
      return parsed.filter((source): source is string => typeof source === 'string')
    }
  } catch {
    // Older records may contain a plain source string rather than JSON.
  }

  return [value]
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([])
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [activeTools, setActiveTools] = useState<string[]>([])
  const abortRef = useRef<AbortController | null>(null)

  const loadSessions = useCallback(async () => {
    const response = await apiFetch('/chat/sessions', { credentials: 'include' })
    if (!response.ok) throw new Error('Could not load chat history.')
    const data = await response.json() as ChatSession[]
    setSessions(data)
    if (data.length > 0) {
      setActiveSessionId(current => current ?? data[0].id)
    }
  }, [])

  const createNewSession = useCallback(async () => {
    const response = await apiFetch('/chat/session', { method: 'POST', credentials: 'include' })
    if (!response.ok) throw new Error('Could not create a chat.')
    const data = await response.json()
    setActiveSessionId(data.session_id)
    setMessages([])
    await loadSessions()
  }, [loadSessions])

  const selectSession = useCallback(async (id: string) => {
    const response = await apiFetch(`/chat/sessions/${id}`, { credentials: 'include' })
    if (!response.ok) throw new Error('Could not load that chat.')
    const data = await response.json()
    setActiveSessionId(id)
    setMessages(data.map((message: { id: number; role: MessageRole; content: string; sources?: unknown }) => ({
      id: String(message.id), role: message.role, content: message.content, sources: normalizeSources(message.sources),
    })))
  }, [])

  useEffect(() => {
    loadSessions().catch(() => undefined)
  }, [loadSessions])

  useEffect(() => {
    if (!activeSessionId) return
    selectSession(activeSessionId).catch(() => undefined)
  }, [activeSessionId, selectSession])

  const sendMessage = useCallback(async (text: string, context = '', sources: string[] = []) => {
    if (!text.trim() || isStreaming) return
    let sessionId = activeSessionId
    if (!sessionId) {
      const response = await apiFetch('/chat/session', { method: 'POST', credentials: 'include' })
      if (!response.ok) throw new Error('Could not create a chat.')
      sessionId = (await response.json()).session_id
      setActiveSessionId(sessionId)
      await loadSessions()
    }

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
      const res = await apiFetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ message: text.trim(), session_id: sessionId, context, sources }),
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
            } else if (event.type === 'sources') {
              setMessages(prev =>
                prev.map(m => m.id === assistantId ? { ...m, sources: normalizeSources(event.sources) } : m)
              )
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
  }, [activeSessionId, isStreaming, loadSessions])

  const clearMessages = useCallback(async () => {
    if (activeSessionId) {
      await apiFetch(`/chat/sessions/${activeSessionId}`, { method: 'DELETE', credentials: 'include' })
      setSessions(current => current.filter(session => session.id !== activeSessionId))
    }
    setMessages([])
    setActiveSessionId(null)
  }, [activeSessionId])

  const signOut = useCallback(async () => {
    await apiFetch('/auth/logout', { method: 'POST', credentials: 'include' })
  }, [])

  return { messages, sessions, activeSessionId, isStreaming, activeTools, sendMessage, clearMessages, selectSession, createNewSession, signOut }
}
