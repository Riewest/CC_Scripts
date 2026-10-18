import React from 'react'
import ReactDOM from 'react-dom/client'
import './style.css'

function App() {
  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="AI Control home">
          <span className="brand-mark">⌘</span>
          <span>AI Control</span>
        </a>
        <span className="connection"><i /> Control plane ready</span>
      </header>
      <section className="hero">
        <p className="eyebrow">COMPUTERCRAFT · CONTROL PLANE</p>
        <h1>Your fleet,<br /><em>within reach.</em></h1>
        <p className="intro">Connect computers, turtles, and pocket computers. Build and run the control experience that fits your world.</p>
        <div className="empty-state">
          <div className="terminal-icon"><span>›_</span></div>
          <div>
            <h2>No computers connected</h2>
            <p>Once you pair a device, its status and controls will appear here.</p>
          </div>
          <span className="status-pill">WAITING FOR DEVICE</span>
        </div>
      </section>
      <footer><span>AI CONTROL <b>·</b> EARLY ACCESS</span><span>Made for your world.</span></footer>
    </main>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><App /></React.StrictMode>,
)
