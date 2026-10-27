import { Activity, ArrowUpRight, BarChart3, FileText, Image, Radio, Sparkles, Trophy } from 'lucide-react'

interface LandingPageProps {
  onStart: () => void
}

const capabilities = [
  { icon: BarChart3, title: 'Live match data', text: 'Ask about standings, fixtures, scores, and player numbers from the stats database.' },
  { icon: Activity, title: 'Tactical thinking', text: 'Break down formations, pressing structures, transitions, and match patterns.' },
  { icon: Trophy, title: 'Football context', text: 'Explore players, clubs, competitions, history, and the stories behind the game.' },
  { icon: FileText, title: 'Your own evidence', text: 'Add reports, images, spreadsheets, or a public URL for grounded analysis.' },
]

export function LandingPage({ onStart }: LandingPageProps) {
  return (
    <main className="landing-shell">
      <nav className="landing-nav">
        <div className="brand-lockup">
          <div className="brand-mark"><Sparkles size={16} /></div>
          <span>Ninety</span>
        </div>
        <div className="nav-note">Football intelligence · Runs locally</div>
        <button className="nav-button" onClick={onStart}>Open workspace <ArrowUpRight size={15} /></button>
      </nav>

      <section className="landing-hero">
        <div className="hero-copy">
          <p className="hero-kicker">Football intelligence, without the noise</p>
          <h1>Read the game<br /><em>more deeply.</em></h1>
          <p className="hero-description">
            Ask about the match, the numbers, or the ideas behind the system. Bring your own context when it matters.
          </p>
          <div className="hero-actions">
            <button className="primary-button" onClick={onStart}>Open the match room <ArrowUpRight size={17} /></button>
            <span className="hero-meta">No account required</span>
          </div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="orb orb-one" />
          <div className="orb orb-two" />
          <div className="football-marker"><Trophy size={22} /></div>
          <div className="signal-card signal-main">
            <div className="signal-top"><span className="signal-live" /> match room ready <span>LIVE</span></div>
            <div className="signal-line signal-long" />
            <div className="signal-line signal-short" />
            <div className="signal-line signal-medium" />
            <div className="signal-prompt">What changed after half-time?<span className="blink">_</span></div>
          </div>
          <div className="signal-card signal-float"><Radio size={13} /> Live analysis</div>
        </div>
      </section>

      <section className="capability-section">
        <div className="section-heading">
          <p className="section-kicker">A sharper matchday companion</p>
          <h2>From the first whistle to the final read.</h2>
        </div>
        <div className="capability-grid">
          {capabilities.map(({ icon: Icon, title, text }) => (
            <article className="capability-item" key={title}>
              <Icon size={20} strokeWidth={1.6} />
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="landing-footer">
        <span>Ninety</span>
        <span>For the curious supporter</span>
      </footer>
    </main>
  )
}
