import { ChatInterface } from './components/ChatInterface'
import { LandingPage } from './components/LandingPage'
import { LoginPage } from './components/LoginPage'
import { apiFetch } from './lib/api'
import { useEffect, useState } from 'react'

export default function App() {
  const [started, setStarted] = useState(false)
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)

  useEffect(() => {
    apiFetch('/auth/me', { credentials: 'include' })
      .then(response => setAuthenticated(response.ok))
      .catch(() => setAuthenticated(false))
  }, [])

  if (authenticated === null) return <div className="auth-loading">Loading Ninety...</div>
  if (!authenticated) return <LoginPage onAuthenticated={() => setAuthenticated(true)} />

  return started
    ? <ChatInterface onBack={() => setStarted(false)} onLogout={() => setAuthenticated(false)} />
    : <LandingPage onStart={() => setStarted(true)} />
}
