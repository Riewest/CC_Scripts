import { FormEvent, useCallback, useEffect, useState } from 'react'

type Computer = { id: string; label: string }
type TokenRecord = {
  id: string; label: string; prefix: string; scopes: string[]; computer_ids: string[] | null
  group_ids: string[] | null; expires_at: string | null; last_used_at: string | null; last_used_ip: string | null
}
const scopeChoices = ['computers:read', 'computers:exec', 'scripts:rw', 'ai:use', 'admin']

function csrfToken() {
  return document.cookie.split('; ').find((part) => part.startsWith('aic_csrf='))?.slice('aic_csrf='.length) ?? ''
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: {
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init.method ? { 'X-CSRF-Token': csrfToken() } : {}),
      ...init.headers,
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail ?? `Request failed (${response.status})`)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

export function Tokens({ onBack, isAdmin }: { onBack: () => void; isAdmin: boolean }) {
  const [tokens, setTokens] = useState<TokenRecord[]>([])
  const [computers, setComputers] = useState<Computer[]>([])
  const [label, setLabel] = useState('')
  const [scopes, setScopes] = useState<string[]>(['computers:read'])
  const [selectedComputers, setSelectedComputers] = useState<string[]>([])
  const [groupIds, setGroupIds] = useState('')
  const [expiry, setExpiry] = useState('')
  const [newToken, setNewToken] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [items, devices] = await Promise.all([
        request<TokenRecord[]>('/api/auth/tokens'), request<Computer[]>('/api/computers'),
      ])
      setTokens(items)
      setComputers(devices)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load API tokens') }
  }, [])
  useEffect(() => { void refresh() }, [refresh])

  function toggleScope(scope: string) {
    setScopes((current) => current.includes(scope) ? current.filter((item) => item !== scope) : [...current, scope])
  }
  function toggleComputer(id: string) {
    setSelectedComputers((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])
  }
  async function create(event: FormEvent) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const created = await request<TokenRecord & { token: string }>('/api/auth/tokens', {
        method: 'POST', body: JSON.stringify({
          label, scopes, computer_ids: selectedComputers.length ? selectedComputers : null,
          group_ids: groupIds.split(/[\s,]+/).filter(Boolean).length
            ? groupIds.split(/[\s,]+/).filter(Boolean)
            : null,
          expires_at: expiry ? new Date(expiry).toISOString() : null,
        }),
      })
      setNewToken(created.token)
      setLabel('')
      setScopes(['computers:read'])
      setSelectedComputers([])
      setGroupIds('')
      setExpiry('')
      await refresh()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not create token') }
    finally { setBusy(false) }
  }
  async function revoke(tokenId: string) {
    if (!window.confirm('Revoke this API token immediately? Existing requests using it will fail.')) return
    try { await request(`/api/auth/tokens/${encodeURIComponent(tokenId)}`, { method: 'DELETE' }); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not revoke token') }
  }

  return <div className="dashboard-page">
    <header className="topbar"><a className="brand" href="#" onClick={(event) => event.preventDefault()}><span className="brand-mark">⌘</span><span>AI Control</span></a><button className="text-button" onClick={onBack}>← Back to fleet</button></header>
    <main className="dashboard-content admin-content">
      <p className="eyebrow">PROGRAMMATIC ACCESS</p><h1 className="dashboard-title">API tokens</h1><p className="intro dashboard-intro">Create scoped credentials for scripts and automation. Tokens are shown once and are never stored in plaintext.</p>
      {error && <p className="error-banner">{error}</p>}
      {newToken && <section className="token-once"><strong>Copy this token now. It will not be shown again.</strong><code>{newToken}</code><button className="secondary-button" onClick={() => void navigator.clipboard.writeText(newToken)}>Copy token</button><button className="text-button" onClick={() => setNewToken('')}>Dismiss</button></section>}
      <form className="pairing-card token-form" onSubmit={(event) => void create(event)}>
        <label className="field-label" htmlFor="token-label">TOKEN LABEL</label><input id="token-label" value={label} onChange={(event) => setLabel(event.target.value)} maxLength={100} required />
        <p className="field-label">SCOPES</p><div className="scope-grid">{scopeChoices.filter((scope) => scope !== 'admin' || isAdmin).map((scope) => <label key={scope}><input type="checkbox" checked={scopes.includes(scope)} onChange={() => toggleScope(scope)} />{scope}</label>)}</div>
        <p className="field-label">COMPUTER RESTRICTION <span>optional · no selection means all computers you can access</span></p><div className="scope-grid">{computers.map((computer) => <label key={computer.id}><input type="checkbox" checked={selectedComputers.includes(computer.id)} onChange={() => toggleComputer(computer.id)} />{computer.label}</label>)}</div>
        <label className="field-label" htmlFor="token-groups">GROUP ID RESTRICTION <span>optional · paste group IDs separated by spaces or commas</span></label><input id="token-groups" value={groupIds} onChange={(event) => setGroupIds(event.target.value)} placeholder="Group IDs" />
        <label className="field-label" htmlFor="token-expiry">EXPIRATION <span>optional</span></label><input id="token-expiry" type="datetime-local" value={expiry} onChange={(event) => setExpiry(event.target.value)} />
        <button className="primary-button" disabled={busy || !label.trim() || scopes.length === 0}>{busy ? 'Creating…' : 'Create API token'}<span>→</span></button>
      </form>
      <section className="token-list"><p className="field-label">ACTIVE AND REVOKED TOKENS</p>{tokens.length === 0 ? <p className="muted-text">No API tokens yet.</p> : tokens.map((token) => <article className="admin-user" key={token.id}>
        <div><strong>{token.label}</strong><small>{token.prefix}… · {token.scopes.join(', ')}{token.expires_at ? ` · expires ${new Date(token.expires_at).toLocaleString()}` : ''}</small><small>Last used {token.last_used_at ? `${new Date(token.last_used_at).toLocaleString()} · ${token.last_used_ip ?? 'unknown IP'}` : 'Never'}</small></div>
        <button className="danger-button" onClick={() => void revoke(token.id)}>Revoke</button>
      </article>)}</section>
    </main>
  </div>
}
