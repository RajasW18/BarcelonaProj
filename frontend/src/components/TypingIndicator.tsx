/**
 * TypingIndicator — animated three-dot typing indicator
 * shown while the agent is processing / streaming.
 */
import { Database, BookOpen, Loader2 } from 'lucide-react'

interface TypingIndicatorProps {
  activeTools?: string[]
}

const TOOL_LABELS: Record<string, { icon: React.ReactNode; label: string }> = {
  sql_query: {
    icon: <Database size={12} />,
    label: 'Querying match database…',
  },
  barca_knowledge: {
    icon: <BookOpen size={12} />,
    label: 'Searching knowledge base…',
  },
}

export function TypingIndicator({ activeTools = [] }: TypingIndicatorProps) {
  const activeTool = activeTools[activeTools.length - 1]
  const toolInfo = activeTool ? TOOL_LABELS[activeTool] : null

  return (
    <div className="flex items-start gap-3 animate-[slideUp_0.3s_ease-out]">
      {/* Avatar */}
      <div className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center blaugrana-gradient text-white text-xs font-bold">
        B
      </div>

      <div className="flex flex-col gap-1.5">
        {/* Tool indicator */}
        {toolInfo && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg glass text-[var(--color-barca-muted)] text-xs animate-[fadeIn_0.3s_ease-out]">
            <span className="text-[var(--color-barca-blue)]">{toolInfo.icon}</span>
            <span>{toolInfo.label}</span>
            <Loader2 size={10} className="animate-spin ml-1 text-[var(--color-barca-blue)]" />
          </div>
        )}

        {/* Typing dots bubble */}
        <div className="px-4 py-3 rounded-2xl rounded-tl-sm glass">
          <div className="flex items-center gap-1.5">
            <span className="typing-dot w-2 h-2 rounded-full bg-[var(--color-barca-muted)]" />
            <span className="typing-dot w-2 h-2 rounded-full bg-[var(--color-barca-muted)]" />
            <span className="typing-dot w-2 h-2 rounded-full bg-[var(--color-barca-muted)]" />
          </div>
        </div>
      </div>
    </div>
  )
}
