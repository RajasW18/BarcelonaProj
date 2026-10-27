import { ChatInterface } from './components/ChatInterface'
import { LandingPage } from './components/LandingPage'
import { LoginPage } from './components/LoginPage'
import { apiFetch } from './lib/api'
import { Component, useEffect, useState, type ErrorInfo, type ReactNode } from 'react'

class AppErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Ninety workspace failed to render', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <main className="auth-shell">
          <section className="auth-panel">
            <div className="brand-lockup"><div className="brand-mark">N</div><span>Ninety</span></div>
            <p className="hero-kicker">Workspace error</p>
            <h1>We could not open<br /><em>your match room.</em></h1>
            <p className="auth-copy">{this.state.error.message || 'The workspace hit an unexpected rendering error.'}</p>
            <button className="primary-button auth-submit" onClick={() => window.location.reload()}>
              Reload workspace
            </button>
          </section>
        </main>
      )
    }
    return this.props.children
  }
}

export default function App() {
  const [started, setStarted] = useState(false)
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 8000)
    apiFetch('/auth/me', { credentials: 'include', signal: controller.signal })
      .then(response => setAuthenticated(response.ok))
      .catch(() => setAuthenticated(false))
      .finally(() => window.clearTimeout(timeout))
    return () => {
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [])

  if (authenticated === null) return <div className="auth-loading"><div className="auth-loading-panel"><strong>Loading Ninety...</strong><span>Checking your account session</span></div></div>
  if (!authenticated) return <LoginPage onAuthenticated={() => setAuthenticated(true)} />

  return (
    <AppErrorBoundary>
      {started
        ? <ChatInterface onBack={() => setStarted(false)} onLogout={() => setAuthenticated(false)} />
        : <LandingPage onStart={() => setStarted(true)} />}
    </AppErrorBoundary>
  )
}
