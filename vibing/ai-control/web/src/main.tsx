import React, { useCallback, useEffect, useState } from 'react'
import ReactDOM from 'react-dom/client'
import { AddComputer } from './pages/AddComputer'
import { AuthPage } from './pages/AuthPage'
import { AdminUsers } from './pages/AdminUsers'
import { Dashboard } from './pages/Dashboard'
import { Tokens } from './pages/Tokens'
import { Teams } from './pages/Teams'
import './style.css'

function App() {
  const [authState, setAuthState] = useState<'checking' | 'signed-out' | 'signed-in'>('checking')
  const [showAddComputer, setShowAddComputer] = useState(false)
  const [showAdmin, setShowAdmin] = useState(false)
  const [showTokens, setShowTokens] = useState(false)
  const [showTeams, setShowTeams] = useState(false)
  const [isAdmin, setIsAdmin] = useState(false)
  const [repairTarget, setRepairTarget] = useState<{ id: string; label: string } | null>(null)
  const handleLogout = useCallback(() => setAuthState('signed-out'), [])
  const handleAddComputer = useCallback(() => setShowAddComputer(true), [])

  useEffect(() => {
    fetch('/api/auth/me', { credentials: 'include' })
      .then(async (response) => {
        if (!response.ok) { setAuthState('signed-out'); return }
        const user = await response.json()
        setIsAdmin(user.role === 'admin')
        if (new URLSearchParams(window.location.search).has('team_invite')) setShowTeams(true)
        setAuthState('signed-in')
      })
      .catch(() => setAuthState('signed-out'))
  }, [])

  async function handleAuthenticated() {
    const response = await fetch('/api/auth/me', { credentials: 'include' })
    if (!response.ok) { setAuthState('signed-out'); return }
    const user = await response.json()
    setIsAdmin(user.role === 'admin')
    if (new URLSearchParams(window.location.search).has('team_invite')) setShowTeams(true)
    setAuthState('signed-in')
  }

  if (authState === 'checking') return <main className="shell"><div className="auth-loading">Loading AI Control…</div></main>
  if (authState === 'signed-out') return <main className="shell"><AuthPage onAuthenticated={() => void handleAuthenticated()} /></main>
  if (showAdmin) return <main className="shell"><AdminUsers onBack={() => setShowAdmin(false)} /></main>
  if (showTokens) return <main className="shell"><Tokens onBack={() => setShowTokens(false)} isAdmin={isAdmin} /></main>
  if (showTeams) return <main className="shell"><Teams onBack={() => setShowTeams(false)} /></main>
  if (showAddComputer || repairTarget) return <main className="shell"><AddComputer onBack={() => { setShowAddComputer(false); setRepairTarget(null) }} repairComputerId={repairTarget?.id} repairLabel={repairTarget?.label} /></main>
  return <main className="shell"><Dashboard onAddComputer={handleAddComputer} onRepairComputer={(computer) => setRepairTarget(computer)} onLogout={handleLogout} onAdmin={() => setShowAdmin(true)} onTokens={() => setShowTokens(true)} onTeams={() => setShowTeams(true)} isAdmin={isAdmin} /></main>
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><App /></React.StrictMode>,
)
