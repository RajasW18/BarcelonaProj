/**
 * VoiceButton — microphone button using the Web Speech API.
 *
 * Shows a pulsing red ring while recording. Fills the input field
 * with the transcribed text and auto-submits when done.
 */
import { Mic, MicOff } from 'lucide-react'
import { useSpeech } from '../hooks/useSpeech'

interface VoiceButtonProps {
  onTranscript: (text: string) => void
  disabled?: boolean
}

export function VoiceButton({ onTranscript, disabled }: VoiceButtonProps) {
  const { isListening, isSupported, interimTranscript, startListening, stopListening } =
    useSpeech({ onTranscript })

  if (!isSupported) {
    return (
      <button
        disabled
        title="Voice input not supported in this browser"
        className="p-3 rounded-xl text-[var(--color-barca-muted)] cursor-not-allowed opacity-40"
        aria-label="Voice input not supported"
      >
        <MicOff size={20} />
      </button>
    )
  }

  return (
    <div className="relative flex items-center justify-center">
      {/* Interim transcript bubble */}
      {interimTranscript && (
        <div className="absolute bottom-14 left-1/2 -translate-x-1/2 w-max max-w-xs px-3 py-2 rounded-lg glass text-sm text-[var(--color-barca-text)] text-center animate-[fadeIn_0.2s_ease-out] z-10">
          <span className="opacity-70">{interimTranscript}</span>
          <span className="ml-1 animate-pulse">|</span>
        </div>
      )}

      <button
        id="voice-btn"
        onClick={isListening ? stopListening : startListening}
        disabled={disabled}
        aria-label={isListening ? 'Stop recording' : 'Start voice input'}
        title={isListening ? 'Click to stop recording' : 'Click to speak'}
        className={[
          'relative p-3 rounded-xl transition-all duration-300',
          'focus:outline-none focus:ring-2 focus:ring-[var(--color-barca-red)] focus:ring-offset-2 focus:ring-offset-[var(--color-barca-dark)]',
          disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
          isListening
            ? 'bg-[var(--color-barca-red)] text-white mic-pulse'
            : 'text-[var(--color-barca-muted)] hover:text-[var(--color-barca-red)] hover:bg-[var(--color-barca-red)]/10',
        ].join(' ')}
      >
        {isListening ? <Mic size={20} /> : <Mic size={20} />}

        {/* Ripple rings when active */}
        {isListening && (
          <>
            <span className="absolute inset-0 rounded-xl border border-[var(--color-barca-red)] animate-ping opacity-40" />
            <span className="absolute -inset-1 rounded-xl border border-[var(--color-barca-red)]/30 animate-ping animation-delay-200 opacity-20" />
          </>
        )}
      </button>
    </div>
  )
}
