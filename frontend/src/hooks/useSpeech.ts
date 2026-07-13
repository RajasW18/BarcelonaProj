/**
 * useSpeech — Web Speech API hook
 *
 * Manages a SpeechRecognition instance. Supports interim transcripts
 * (real-time display) and fires onTranscript with the final result.
 */
import { useState, useRef, useCallback, useEffect } from 'react'

interface UseSpeechOptions {
  onTranscript: (text: string) => void
  language?: string
}

interface UseSpeechReturn {
  isListening: boolean
  isSupported: boolean
  interimTranscript: string
  startListening: () => void
  stopListening: () => void
}

const SpeechRecognition =
  (window as any).SpeechRecognition ||
  (window as any).webkitSpeechRecognition

export function useSpeech({
  onTranscript,
  language = 'en-US',
}: UseSpeechOptions): UseSpeechReturn {
  const [isListening, setIsListening] = useState(false)
  const [interimTranscript, setInterimTranscript] = useState('')
  const recognitionRef = useRef<any>(null)
  const isSupported = Boolean(SpeechRecognition)

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
    }
  }, [])

  const startListening = useCallback(() => {
    if (!isSupported || isListening) return

    const recognition = new SpeechRecognition()
    recognition.lang = language
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setIsListening(true)
      setInterimTranscript('')
    }

    recognition.onresult = (event: any) => {
      let interim = ''
      let final = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        if (event.results[i].isFinal) {
          final += transcript
        } else {
          interim += transcript
        }
      }
      setInterimTranscript(interim)
      if (final.trim()) {
        onTranscript(final.trim())
        setInterimTranscript('')
      }
    }

    recognition.onerror = (event: any) => {
      console.error('Speech recognition error:', event.error)
      setIsListening(false)
      setInterimTranscript('')
    }

    recognition.onend = () => {
      setIsListening(false)
      setInterimTranscript('')
    }

    recognitionRef.current = recognition
    recognition.start()
  }, [isSupported, isListening, language, onTranscript])

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort()
      }
    }
  }, [])

  return { isListening, isSupported, interimTranscript, startListening, stopListening }
}
