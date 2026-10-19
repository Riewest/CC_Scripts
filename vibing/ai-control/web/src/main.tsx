import React, { useCallback, useEffect, useState } from 'react'
import ReactDOM from 'react-dom/client'
import { AddComputer } from './pages/AddComputer'
import { AuthPage } from './pages/AuthPage'
import { Dashboard } from './pages/Dashboard'
import './style.css'

function App() {
  const [authState, setAuthState] = useState<'checking' | 'signed-out' | 'signed-in'>('checking')
  const [showAddComputer, setShowAddComputer] = useState(false)
  const [repairTarget, setRepairTarget] = useState<{ id: string; label: string } | null>(null)
  const handleLogout = useCallback(() => setAuthState('signed-out'), [])
  const handleAddComputer = useCallback(() => setShowAddComputer(true), [])

  useEffect(() => {
    fetch('/api/auth/me', { credentials: 'include' })
      .then((response) => setAuthState(response.ok ? 'signed-in' : 'signed-out'))
      .catch(() => setAuthState('signed-out'))
  }, [])

  if (authState === 'checking') return <main className="shell"><div className="auth-loading">Loading AI Control…</div></main>
  if (authState === 'signed-out') return <main className="shell"><AuthPage onAuthenticated={() => setAuthState('signed-in')} /></main>
  if (showAddComputer || repairTarget) return <main className="shell"><AddComputer onBack={() => { setShowAddComputer(false); setRepairTarget(null) }} repairComputerId={repairTarget?.id} repairLabel={repairTarget?.label} /></main>
  return <main className="shell"><Dashboard onAddComputer={handleAddComputer} onRepairComputer={(computer) => setRepairTarget(computer)} onLogout={handleLogout} /></main>
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><App /></React.StrictMode>,
)
