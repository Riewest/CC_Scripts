import { useCallback, useEffect, useState } from 'react'

type AdminUser = { id: string; username: string; role: 'admin' | 'user'; disabled: boolean; created_at?: string }

function csrfToken() {
  return document.cookie.split('; ').find((part) => part.startsWith('aic_csrf='))?.slice('aic_csrf='.length) ?? ''
}

export function AdminUsers({ onBack }: { onBack: () => void }) {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/api/admin/users', { credentials: 'include' })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail ?? 'Could not load users')
      setUsers(body)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not load users')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  async function update(user: AdminUser, changes: Partial<Pick<AdminUser, 'role' | 'disabled'>>) {
    setError('')
    try {
      const response = await fetch(`/api/admin/users/${encodeURIComponent(user.id)}`, {
        method: 'PATCH', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
        body: JSON.stringify(changes),
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail ?? 'Could not update user')
      setUsers((current) => current.map((entry) => entry.id === user.id ? { ...entry, ...body } : entry))
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not update user') }
  }

  return <div className="dashboard-page">
    <header className="topbar"><a className="brand" href="#" onClick={(event) => event.preventDefault()}><span className="brand-mark">⌘</span><span>AI Control</span></a><button className="text-button" onClick={onBack}>← Back to fleet</button></header>
    <main className="dashboard-content admin-content">
      <p className="eyebrow">ACCESS CONTROL</p><h1 className="dashboard-title">Users</h1><p className="intro dashboard-intro">Manage administrator access and disable accounts. Disabled users lose their sessions and cannot sign in.</p>
      {error && <p className="error-banner">{error}</p>}
      {loading ? <p className="muted-text">Loading users…</p> : <div className="admin-user-list">{users.map((user) => <article className="admin-user" key={user.id}>
        <div><strong>{user.username}</strong><small>{user.disabled ? 'Disabled' : 'Active'}{user.created_at ? ` · Created ${new Date(user.created_at).toLocaleDateString()}` : ''}</small></div>
        <label className="admin-field">Role<select value={user.role} onChange={(event) => void update(user, { role: event.target.value as AdminUser['role'] })}><option value="user">User</option><option value="admin">Admin</option></select></label>
        <button className={user.disabled ? 'secondary-button' : 'danger-button'} onClick={() => void update(user, { disabled: !user.disabled })}>{user.disabled ? 'Enable' : 'Disable'}</button>
      </article>)}</div>}
    </main>
  </div>
}
