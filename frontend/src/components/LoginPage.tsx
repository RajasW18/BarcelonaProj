import { useState } from 'react'
import { ArrowRight, KeyRound, Mail, Sparkles } from 'lucide-react'
import { apiFetch, apiUrl } from '../lib/api'

interface LoginPageProps {
  onAuthenticated: () => void
}

export function LoginPage({ onAuthenticated }: LoginPageProps) {
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const requestCode = async () => {
    setBusy(true); setError('')
    try {
      const response = await apiFetch('/auth/request-otp', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail ?? 'Could not send your code.')
      setSent(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send your code.')
    } finally { setBusy(false) }
  }

  const verifyCode = async () => {
    setBusy(true); setError('')
    try {
      const response = await apiFetch('/auth/verify-otp', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail ?? 'That code did not work.')
      onAuthenticated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That code did not work.')
    } finally { setBusy(false) }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="brand-lockup"><div className="brand-mark"><Sparkles size={16} /></div><span>Ninety</span></div>
        <div className="auth-icon"><KeyRound size={20} /></div>
        <p className="hero-kicker">Your matchday desk</p>
        <h1>Keep every<br /><em>read together.</em></h1>
        <p className="auth-copy">Sign in to save your football conversations and pick them up on any device.</p>

        <button className="google-button" onClick={() => { window.location.href = apiUrl('/auth/google/login') }}>
          <span className="google-g">G</span> Continue with Google <ArrowRight size={15} />
        </button>
        <div className="auth-divider"><span>or use email</span></div>

        <label htmlFor="email">Email address</label>
        <div className="auth-input-wrap"><Mail size={16} /><input id="email" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" /></div>
        {!sent ? (
          <button className="primary-button auth-submit" disabled={busy || !email.trim()} onClick={requestCode}>{busy ? 'Sending...' : 'Send sign-in code'} <ArrowRight size={16} /></button>
        ) : (
          <>
            <label htmlFor="code">Six-digit code</label>
            <input id="code" className="auth-code" inputMode="numeric" maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ''))} placeholder="000000" />
            <button className="primary-button auth-submit" disabled={busy || code.length !== 6} onClick={verifyCode}>{busy ? 'Checking...' : 'Open Ninety'} <ArrowRight size={16} /></button>
            <button className="auth-link" onClick={() => setSent(false)}>Use a different email</button>
          </>
        )}
        {error && <p className="auth-error">{error}</p>}
        <p className="auth-legal">By continuing, you agree to use Ninety responsibly. No password is stored.</p>
      </section>
    </main>
  )
}
