import { useCallback, useEffect, useMemo, useState } from 'react'

type Computer = {
  id: string
  label: string
  kind: 'computer' | 'turtle' | 'pocket' | string
  status: 'online' | 'offline' | string
  cc_version: string | null
  last_seen: string | null
  telemetry: Record<string, unknown> | null
  owner_team_id?: string | null
  ownership?: 'team' | 'personal'
}

type Run = {
  id: string
  code: string
  started_at: string
  finished_at: string | null
  result: { ok?: boolean; output?: string; error?: string; traceback?: string; return_values?: unknown[]; duration_ms?: number } | null
}

function csrfToken() {
  return document.cookie.split('; ').find((part) => part.startsWith('aic_csrf='))?.slice('aic_csrf='.length) ?? ''
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: {
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init.method && init.method !== 'GET' ? { 'X-CSRF-Token': csrfToken() } : {}),
      ...init.headers,
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(response.status === 401 ? `401 ${body.detail ?? 'Authentication required'}` : body.detail ?? `Request failed (${response.status})`)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

function pretty(value: unknown): string {
  return value === undefined || value === null ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value)
}

function equipmentLabel(value: unknown): string {
  if (!value || typeof value !== 'object') return 'Empty'
  const item = value as { displayName?: unknown; name?: unknown; count?: unknown; damage?: unknown; maxDamage?: unknown }
  const label = typeof item.displayName === 'string'
    ? item.displayName
    : typeof item.name === 'string'
      ? item.name.split(':').pop()?.replaceAll('_', ' ') ?? 'Item'
      : 'Item'
  const details = [
    typeof item.count === 'number' && item.count > 1 ? `×${item.count}` : null,
    typeof item.damage === 'number' && typeof item.maxDamage === 'number' ? `${item.maxDamage - item.damage}/${item.maxDamage} durability` : null,
  ].filter(Boolean)
  return details.length ? `${label} · ${details.join(' · ')}` : label
}

function coordinateText(value: unknown): string | null {
  if (!value || typeof value !== 'object') return null
  const position = value as { x?: unknown; y?: unknown; z?: unknown }
  const coordinates = [position.x, position.y, position.z].map((coordinate) => {
    if (typeof coordinate === 'number' && Number.isFinite(coordinate)) return String(coordinate)
    if (typeof coordinate === 'string' && coordinate.trim() !== '' && Number.isFinite(Number(coordinate))) return String(Number(coordinate))
    return null
  })
  return coordinates.every((coordinate) => coordinate !== null) ? coordinates.join(' ') : null
}

export function Dashboard({
  onAddComputer,
  onRepairComputer,
  onLogout,
  onAdmin,
  onTokens,
  onTeams,
  isAdmin,
}: {
  onAddComputer: () => void
  onRepairComputer: (computer: Pick<Computer, 'id' | 'label'>) => void
  onLogout: () => void
  onAdmin: () => void
  onTokens: () => void
  onTeams: () => void
  isAdmin: boolean
}) {
  const [computers, setComputers] = useState<Computer[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [code, setCode] = useState('print("Hello from CC:Tweaked")\nreturn os.getComputerID()')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [latestResult, setLatestResult] = useState<Run['result']>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [websocketState, setWebsocketState] = useState('connecting')
  const [copiedPosition, setCopiedPosition] = useState('')
  const [oidcProviders, setOidcProviders] = useState<string[]>([])

  const refreshComputers = useCallback(async () => {
    try {
      const data = await api<Computer[]>('/api/computers')
      setComputers(data)
      setSelectedId((current) => current && data.some((item) => item.id === current) ? current : data[0]?.id ?? null)
    } catch (reason) {
      if (reason instanceof Error && reason.message.includes('401')) onLogout()
      setError(reason instanceof Error ? reason.message : 'Could not load computers')
    } finally {
      setLoading(false)
    }
  }, [onLogout])

  const refreshRuns = useCallback(async (computerId: string) => {
    try { setRuns(await api<Run[]>(`/api/computers/${computerId}/runs`)) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load run history') }
  }, [])

  useEffect(() => { void refreshComputers() }, [refreshComputers])
  useEffect(() => {
    fetch('/api/auth/oidc/providers', { credentials: 'include' })
      .then((response) => response.ok ? response.json() : [])
      .then((providers: Array<{ name: string }>) => setOidcProviders(providers.map((provider) => provider.name)))
      .catch(() => setOidcProviders([]))
  }, [])
  useEffect(() => {
    if (selectedId) void refreshRuns(selectedId)
    else setRuns([])
  }, [refreshRuns, selectedId])

  useEffect(() => {
    const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${scheme}//${window.location.host}/ws/ui`)
    socket.onopen = () => setWebsocketState('live')
    socket.onclose = () => setWebsocketState('reconnecting')
    socket.onerror = () => setWebsocketState('offline')
    socket.onmessage = (event) => {
      try {
        const update = JSON.parse(event.data)
        if (update.type === 'ready') return
        void refreshComputers()
        if (update.type === 'exec_result' && update.computer_id) void refreshRuns(update.computer_id)
      } catch {
        setError('Received an invalid live update')
      }
    }
    const fallback = window.setInterval(() => void refreshComputers(), 10000)
    return () => { socket.close(); window.clearInterval(fallback) }
  }, [refreshComputers, refreshRuns])

  const selected = useMemo(() => computers.find((computer) => computer.id === selectedId) ?? null, [computers, selectedId])
  const selectedPosition = coordinateText(selected?.telemetry?.position)
  const onlineCount = computers.filter((computer) => computer.status === 'online').length

  async function copyPosition() {
    if (!selectedPosition) return
    try {
      await navigator.clipboard.writeText(selectedPosition)
      setCopiedPosition(selectedPosition)
    } catch {
      setError('Could not copy coordinates. Select and copy the displayed coordinate text instead.')
    }
  }

  async function runCode() {
    if (!selected) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const response = await api<{ run: Run; result: NonNullable<Run['result']> }>(`/api/computers/${selected.id}/exec`, {
        method: 'POST',
        body: JSON.stringify({ code, name: 'web-editor', timeout_ms: 30000 }),
      })
      setRuns((current) => [response.run, ...current.filter((run) => run.id !== response.run.id)])
      setLatestResult(response.result)
      setNotice(response.result.output || (response.result.ok ? 'Program finished successfully.' : 'Program finished with an error.'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not run code')
    } finally {
      setBusy(false)
      if (selected) void refreshRuns(selected.id)
    }
  }

  async function interrupt(emergency = false) {
    if (!selected) return
    try {
      await api(`/api/computers/${selected.id}/${emergency ? 'emergency-stop' : 'interrupt'}`, { method: 'POST' })
      setNotice(emergency ? 'Emergency stop sent; queued executions are being cancelled.' : 'Interrupt sent. An in-flight turtle API operation may finish before stopping.')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not interrupt') }
  }

  async function renameComputer() {
    if (!selected) return
    const label = window.prompt('New computer label', selected.label)?.trim()
    if (!label || label === selected.label) return
    try {
      await api(`/api/computers/${selected.id}`, { method: 'PATCH', body: JSON.stringify({ label }) })
      setNotice('Computer renamed.')
      await refreshComputers()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not rename computer') }
  }

  async function reboot() {
    if (!selected) return
    try {
      await api(`/api/computers/${selected.id}/reboot`, { method: 'POST' })
      setNotice('Reboot requested.')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not request reboot') }
  }

  async function logout() {
    try { await api('/api/auth/logout', { method: 'POST' }) }
    finally { onLogout() }
  }

  async function linkIdentity(provider: string) {
    if (!window.confirm(`Link the ${provider} identity to this signed-in account? It will not change account ownership.`)) return
    try {
      const response = await fetch(`/api/auth/oidc/${encodeURIComponent(provider)}/link`, {
        method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': csrfToken() },
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail ?? 'Could not start identity linking')
      window.location.assign(result.authorization_url)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not start identity linking') }
  }

  return (
    <div className="dashboard-page">
      <header className="topbar">
        <a className="brand" href="#" onClick={(event) => event.preventDefault()}><span className="brand-mark">⌘</span><span>AI Control</span></a>
        <span className={`connection ${websocketState === 'live' ? '' : 'dimmed'}`}><i /> {websocketState === 'live' ? 'Live connection' : websocketState}</span>
        <div className="topbar-actions">{isAdmin && <button className="text-button" onClick={onAdmin}>Admin</button>}<button className="text-button" onClick={onTeams}>Teams</button><button className="text-button" onClick={onTokens}>API tokens</button>{oidcProviders.map((provider) => <button className="text-button" key={provider} onClick={() => void linkIdentity(provider)}>Link {provider}</button>)}<button className="nav-action" onClick={onAddComputer}>＋ Add computer</button><button className="text-button" onClick={() => void logout()}>Sign out</button></div>
      </header>
      <main className="dashboard-content">
        <div className="dashboard-heading"><div><p className="eyebrow">YOUR CONTROL ROOM</p><h1 className="dashboard-title">Computer fleet</h1><p className="intro dashboard-intro">Devices connected to your account, ready when you are.</p></div><div className="fleet-count"><strong>{onlineCount}</strong><span>ONLINE <b>·</b> {computers.length} TOTAL</span></div></div>
        {error && <p className="error-banner">{error}</p>}
        {notice && <p className="notice-banner">{notice}</p>}
        {loading ? <p className="muted-text">Loading fleet…</p> : computers.length === 0 ? (
          <div className="empty-state dashboard-empty"><div className="terminal-icon">›_</div><div><h2>No computers registered</h2><p>Generate a pairing command to connect your first device.</p></div><button className="nav-action" onClick={onAddComputer}>Add computer</button></div>
        ) : (
          <div className="fleet-layout">
            <aside className="computer-list" aria-label="Computer fleet">
              {computers.map((computer) => <button key={computer.id} className={`computer-card ${selectedId === computer.id ? 'selected' : ''}`} onClick={() => setSelectedId(computer.id)}>
                <span className={`device-icon ${computer.kind}`}>{computer.kind === 'turtle' ? '◇' : computer.kind === 'pocket' ? '▣' : '▤'}</span>
                <span className="computer-card-copy"><strong>{computer.label}</strong><small>{computer.kind} · {computer.status}{computer.ownership === 'team' ? ' · TEAM' : ''}</small></span>
                <i className={`device-dot ${computer.status}`} />
                {computer.kind === 'turtle' && <small className="fuel-line">Fuel {pretty(computer.telemetry?.fuel)}</small>}
              </button>)}
            </aside>
            {selected && <section className="computer-detail">
              <div className="detail-header"><div><p className="eyebrow">{selected.kind.toUpperCase()} · {selected.status.toUpperCase()}</p><h2>{selected.label}</h2><p className="muted-text">Last seen {selected.last_seen ? new Date(selected.last_seen).toLocaleString() : 'never'}{selected.cc_version ? ` · CC ${selected.cc_version}` : ''}</p></div><div className="detail-actions"><button className="secondary-button" onClick={() => onRepairComputer(selected)}>Re-pair</button><button className="secondary-button" onClick={() => void renameComputer()}>Rename</button><button className="secondary-button" disabled={selected.status !== 'online'} onClick={() => void reboot()}>Reboot</button></div></div>
              <div className="telemetry-grid">
                <div className="telemetry-tile"><span>FUEL</span><strong>{pretty(selected.telemetry?.fuel)}</strong></div>
                <div className="telemetry-tile"><span>FUEL LIMIT</span><strong>{pretty(selected.telemetry?.fuel_limit)}</strong></div>
                <div className="telemetry-tile"><span>SELECTED SLOT</span><strong>{pretty(selected.telemetry?.selected_slot)}</strong></div>
                <div className="telemetry-tile position-tile"><span>POSITION · X Y Z</span><div className="position-value"><strong>{selectedPosition ?? '—'}</strong>{selectedPosition && <button className="copy-position" type="button" onClick={() => void copyPosition()} aria-label="Copy coordinates">{copiedPosition === selectedPosition ? 'Copied' : 'Copy'}</button>}</div></div>
              </div>
              {selected.kind === 'turtle' && Array.isArray(selected.telemetry?.inventory) && <details className="inventory-panel" open><summary>Inventory · {selected.telemetry.inventory.length} occupied slots</summary><div className="inventory-grid">{Array.from({ length: 16 }, (_, index) => {
                const slot = index + 1
                const item = (selected.telemetry?.inventory as Array<{ slot?: number; name?: string; displayName?: string; count?: number }>).find((entry) => entry.slot === slot)
                return <div className={`inventory-cell ${item ? 'occupied' : ''}`} key={slot} title={item ? `${item.displayName ?? item.name ?? 'Item'} ×${item.count ?? 1}` : `Empty slot ${slot}`}><small>{slot}</small>{item && <><span>{(item.displayName ?? item.name ?? '?').split(':').pop()?.slice(0, 9)}</span><b>{item.count ?? 1}</b></>}</div>
              })}</div></details>}
              {!!(selected.telemetry?.equipped_left || selected.telemetry?.equipped_right) && <div className="equipment-grid" aria-label="Equipped turtle tools">
                <div className="equipment-tile"><span>LEFT EQUIPMENT</span><strong>{equipmentLabel(selected.telemetry.equipped_left)}</strong></div>
                <div className="equipment-tile"><span>RIGHT EQUIPMENT</span><strong>{equipmentLabel(selected.telemetry.equipped_right)}</strong></div>
              </div>}
              {Array.isArray(selected.telemetry?.peripherals) && <details className="inventory-panel"><summary>Peripherals · {selected.telemetry.peripherals.length} attached</summary><pre>{JSON.stringify(selected.telemetry.peripherals, null, 2)}</pre></details>}
              <div className="editor-panel"><div className="editor-heading"><div><p className="eyebrow">REMOTE LUA</p><h3>Run a program</h3></div><div className="detail-actions"><button className="secondary-button" disabled={selected.status !== 'online'} onClick={() => void interrupt()}>Stop</button><button className="danger-button" disabled={selected.status !== 'online'} onClick={() => void interrupt(true)}>Emergency stop</button><button className="primary-button run-button" disabled={selected.status !== 'online' || busy || !code.trim()} onClick={() => void runCode()}>{busy ? 'Running…' : '▶ Run'}</button></div></div>
                <textarea className="lua-editor" aria-label="Lua code" value={code} onChange={(event) => setCode(event.target.value)} spellCheck={false} />
                {notice && <div className="run-result"><p className="result-heading">{latestResult?.ok ? 'EXECUTION COMPLETE' : latestResult?.error ? 'EXECUTION ERROR' : 'EXECUTION STATUS'}</p>{latestResult?.output && <pre className="output-pane">{latestResult.output}</pre>}{latestResult?.return_values && latestResult.return_values.length > 0 && <div className="return-values"><span>RETURN VALUES</span><pre>{JSON.stringify(latestResult.return_values, null, 2)}</pre></div>}{latestResult?.error && <div className="error-result"><strong>{latestResult.error}</strong>{latestResult.traceback && <pre>{latestResult.traceback}</pre>}</div>}{!latestResult?.output && !latestResult?.error && <pre className="output-pane">{notice}</pre>}</div>}
                {runs.length > 0 && <details className="run-history"><summary>Recent runs ({runs.length})</summary>{runs.map((run) => <article className="run-entry" key={run.id}><div className="run-meta"><span>{new Date(run.started_at).toLocaleString()}</span><span className={run.result?.ok ? 'result-ok' : 'result-error'}>{run.result?.ok ? 'OK' : run.result?.error ? 'ERROR' : 'RUNNING'}</span></div><pre>{run.result?.output || ''}{run.result?.return_values?.length ? `\nReturn: ${JSON.stringify(run.result.return_values)}` : ''}{run.result?.error ? `\n${run.result.error}\n${run.result.traceback ?? ''}` : ''}</pre></article>)}</details>}
              </div>
            </section>}
          </div>
        )}
      </main>
      <footer><span>AI CONTROL <b>·</b> EARLY ACCESS</span><span>Devices stay in your ownership.</span></footer>
    </div>
  )
}
