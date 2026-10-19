import { FormEvent, useCallback, useEffect, useState } from 'react'

type AuditEvent = {
  id: string; created_at: string; actor_type: string; actor_user_id: string | null; actor_token_id: string | null
  computer_id: string | null; action: string; target_type: string | null; target_id: string | null
  outcome: string; source_ip: string | null; details: Record<string, unknown> | null
}
type AuditPage = { items: AuditEvent[]; offset: number; limit: number; total: number; has_more: boolean }

function csrfToken() { return document.cookie.split('; ').find((part) => part.startsWith('aic_csrf='))?.slice('aic_csrf='.length) ?? '' }

export function Audit({ onBack, computerId }: { onBack: () => void; computerId?: string }) {
  const [page, setPage] = useState<AuditPage>({ items: [], offset: 0, limit: 50, total: 0, has_more: false })
  const [action, setAction] = useState('')
  const [outcome, setOutcome] = useState('')
  const [actor, setActor] = useState('')
  const [actorToken, setActorToken] = useState('')
  const [actorType, setActorType] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const params = useCallback((pageOffset: number, format?: string) => {
    const query = new URLSearchParams()
    if (computerId) query.set('computer_id', computerId)
    if (action) query.set('action', action)
    if (outcome) query.set('outcome', outcome)
    if (actor) query.set('actor_user_id', actor)
    if (actorToken) query.set('actor_token_id', actorToken)
    if (actorType) query.set('actor_type', actorType)
    if (start) query.set('start', new Date(start).toISOString())
    if (end) query.set('end', new Date(end).toISOString())
    if (format) query.set('format', format)
    else { query.set('offset', String(pageOffset)); query.set('limit', '50') }
    return query
  }, [action, actor, actorToken, actorType, computerId, end, outcome, start])

  const load = useCallback(async (nextOffset = 0) => {
    setBusy(true); setError('')
    try {
      const response = await fetch(`/api/audit?${params(nextOffset)}`, { credentials: 'include', headers: { 'X-CSRF-Token': csrfToken() } })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail ?? 'Could not load audit events')
      setPage(body); setOffset(nextOffset)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load audit events') }
    finally { setBusy(false) }
  }, [params])
  useEffect(() => { void load(0) }, [load])

  async function applyFilters(event: FormEvent) { event.preventDefault(); await load(0) }
  async function exportEvents(format: 'json' | 'csv') {
    try {
      const response = await fetch(`/api/audit/export?${params(0, format)}`, { credentials: 'include', headers: { 'X-CSRF-Token': csrfToken() } })
      if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail ?? 'Could not export audit events') }
      const content = await response.blob()
      const link = document.createElement('a')
      link.href = URL.createObjectURL(content)
      link.download = `ai-control-audit.${format}`
      link.click()
      URL.revokeObjectURL(link.href)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not export audit events') }
  }

  return <div className="dashboard-page">
    <header className="topbar"><a className="brand" href="#" onClick={(event) => event.preventDefault()}><span className="brand-mark">⌘</span><span>AI Control</span></a><button className="text-button" onClick={onBack}>← Back to fleet</button></header>
    <main className="dashboard-content audit-content">
      <p className="eyebrow">IMMUTABLE ACTIVITY</p><h1 className="dashboard-title">{computerId ? 'Computer activity' : 'Audit log'}</h1><p className="intro dashboard-intro">{page.total} visible events. Operators see their own activity; owners and administrators see all permitted events.</p>
      <form className="pairing-card audit-filters" onSubmit={(event) => void applyFilters(event)}>
        <label className="admin-field">Action<input value={action} onChange={(event) => setAction(event.target.value)} maxLength={120} placeholder="computer.exec" /></label>
        <label className="admin-field">Actor user ID<input value={actor} onChange={(event) => setActor(event.target.value)} /></label>
        <label className="admin-field">Actor token ID<input value={actorToken} onChange={(event) => setActorToken(event.target.value)} /></label>
        <label className="admin-field">Actor type<select value={actorType} onChange={(event) => setActorType(event.target.value)}><option value="">Any</option><option value="user">User</option><option value="token">API token</option><option value="system">System</option><option value="ai">AI</option></select></label>
        <label className="admin-field">Outcome<select value={outcome} onChange={(event) => setOutcome(event.target.value)}><option value="">Any</option><option value="success">Success</option><option value="failure">Failure</option></select></label>
        <label className="admin-field">From<input type="datetime-local" value={start} onChange={(event) => setStart(event.target.value)} /></label>
        <label className="admin-field">To<input type="datetime-local" value={end} onChange={(event) => setEnd(event.target.value)} /></label>
        <div className="audit-actions"><button className="primary-button" disabled={busy}>Filter</button><button className="secondary-button" type="button" onClick={() => void exportEvents('json')}>Export JSON</button><button className="secondary-button" type="button" onClick={() => void exportEvents('csv')}>Export CSV</button></div>
      </form>
      {error && <p className="error-banner">{error}</p>}
      {busy ? <p className="muted-text">Loading audit events…</p> : <section className="audit-events">{page.items.map((event) => <article className="audit-event" key={event.id}>
        <div className="audit-event-heading"><strong>{event.action}</strong><span className={event.outcome === 'success' ? 'result-ok' : 'result-error'}>{event.outcome}</span></div>
        <div className="audit-event-meta"><span>{new Date(event.created_at).toLocaleString()}</span><span>{event.actor_type}{event.actor_user_id ? ` · ${event.actor_user_id}` : ''}{event.actor_token_id ? ` · token ${event.actor_token_id.slice(0, 8)}` : ''}</span><span>{event.computer_id ?? event.target_type ?? 'system'}{event.computer_id ? ` · ${event.computer_id}` : ''}</span><span>{event.source_ip ?? 'unknown IP'}</span></div>
        {event.details && <details><summary>Redacted event details</summary><pre>{JSON.stringify(event.details, null, 2)}</pre></details>}
      </article>)}</section>}
      <div className="audit-pagination"><button className="secondary-button" disabled={offset === 0 || busy} onClick={() => void load(Math.max(0, offset - page.limit))}>← Previous</button><span>{page.total === 0 ? 0 : offset + 1}–{Math.min(offset + page.items.length, page.total)} of {page.total}</span><button className="secondary-button" disabled={!page.has_more || busy} onClick={() => void load(offset + page.limit)}>Next →</button></div>
    </main>
  </div>
}
