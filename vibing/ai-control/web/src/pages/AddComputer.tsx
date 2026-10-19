import { useEffect, useMemo, useState } from 'react'
import '../style.css'

type PairingCode = {
  id: string
  code: string
  expires_at: string
  command: string
}

type PairingState = {
  used: boolean
  paired_computer: { id: string; label: string; kind: string; status: string } | null
}

function csrfToken(): string {
  return document.cookie
    .split('; ')
    .find((part) => part.startsWith('aic_csrf='))
    ?.slice('aic_csrf='.length) ?? ''
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
    throw new Error(body.detail ?? `Request failed (${response.status})`)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

export function AddComputer({
  onBack,
  repairComputerId,
  repairLabel,
}: {
  onBack: () => void
  repairComputerId?: string
  repairLabel?: string
}) {
  const [label, setLabel] = useState('')
  const [pairing, setPairing] = useState<PairingCode | null>(null)
  const [pairingUsed, setPairingUsed] = useState(false)
  const [paired, setPaired] = useState<PairingState['paired_computer']>(null)
  const [error, setError] = useState('')
  const [secondsLeft, setSecondsLeft] = useState(0)
  const expiresAt = useMemo(() => pairing ? Date.parse(pairing.expires_at) : 0, [pairing])

  useEffect(() => {
    if (!pairing || paired?.status === 'online') return
    let cancelled = false
    let timeout: number | undefined
    const poll = async () => {
      if (Date.now() >= Date.parse(pairing.expires_at)) return
      try {
        const state = await api<PairingState>(`/api/pairing-codes/${pairing.id}`)
        if (!cancelled) {
          setPairingUsed(state.used)
          if (state.paired_computer) setPaired(state.paired_computer)
        }
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : 'Could not check pairing status')
      } finally {
        if (!cancelled) timeout = window.setTimeout(() => void poll(), 1500)
      }
    }
    void poll()
    return () => {
      cancelled = true
      if (timeout !== undefined) window.clearTimeout(timeout)
    }
  }, [pairing, paired])

  useEffect(() => {
    if (!pairing || pairingUsed) return
    const update = () => setSecondsLeft(Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000)))
    update()
    const timer = window.setInterval(update, 1000)
    return () => window.clearInterval(timer)
  }, [expiresAt, pairing, pairingUsed])

  async function generate() {
    setError('')
    setPaired(null)
    setPairingUsed(false)
    try {
      const endpoint = repairComputerId
        ? `/api/computers/${repairComputerId}/pairing-code`
        : '/api/pairing-codes'
      const created = await api<PairingCode>(endpoint, {
        method: 'POST',
        ...(repairComputerId ? {} : { body: JSON.stringify({ owner: 'me', label: label.trim() || null }) }),
      })
      setPairing(created)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not create pairing code')
    }
  }

  async function copyCommand() {
    if (!pairing) return
    try {
      await navigator.clipboard.writeText(pairing.command)
    } catch {
      setError('Clipboard access was blocked; select and copy the command manually.')
    }
  }

  return (
    <section className="pairing-page">
      <button className="back-button" onClick={onBack}>← Back to fleet</button>
      <p className="eyebrow">DEVICE ONBOARDING</p>
      <h1 className="pairing-title">{repairComputerId ? 'Re-pair device' : 'Add a computer'}</h1>
      <p className="intro pairing-intro">{repairComputerId ? `Rotate the reconnect secret for ${repairLabel ?? 'this device'}. The old secret stops working after pairing.` : 'Generate a one-time code, paste the command into the CC:Tweaked shell, and this page will confirm when it comes online.'}</p>

      {!pairing ? (
        <div className="pairing-card">
          {!repairComputerId && <><label className="field-label" htmlFor="device-label">Device label <span>OPTIONAL</span></label>
          <input id="device-label" value={label} onChange={(event) => setLabel(event.target.value)} maxLength={120} placeholder="e.g. Quarry turtle" /></>}
          <div className="owner-note"><span className="owner-icon">◈</span><span>Personal device <small>Owned by your account</small></span><span className="owner-badge">YOU</span></div>
          {error && <p className="error-banner">{error}</p>}
          <button className="primary-button" onClick={() => void generate()}>Generate pairing command <span>↗</span></button>
        </div>
      ) : (
        <div className="pairing-card">
          <div className={`pairing-status ${paired?.status === 'online' ? 'is-online' : ''}`}><i />{paired ? paired.status === 'online' ? 'DEVICE ONLINE' : 'DEVICE PAIRED · WAITING FOR CONNECTION' : secondsLeft > 0 ? 'WAITING FOR DEVICE' : 'CODE EXPIRED'}</div>
          {paired ? (
            <div className="paired-device"><span className="terminal-icon">›_</span><div><strong>{paired.label}</strong><small>{paired.kind} · {paired.status}</small></div><span className="owner-badge">{paired.status.toUpperCase()}</span></div>
          ) : (
            <>
              <p className="field-label">RUN THIS COMMAND IN YOUR COMPUTERCRAFT SHELL</p>
              <div className="command-box"><code>{pairing.command}</code><button onClick={() => void copyCommand()} aria-label="Copy pairing command">Copy</button></div>
              {!pairingUsed && <div className="pair-code-row"><span>One-time code</span><code>{pairing.code}</code><span className="countdown">{Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, '0')} remaining</span></div>}
              {error && <p className="error-banner">{error}</p>}
              {secondsLeft === 0 && <button className="primary-button" onClick={() => void generate()}>Generate a new code <span>↻</span></button>}
            </>
          )}
          <button className="text-button" onClick={() => { setPairing(null); setPaired(null); setError('') }}>Cancel pairing</button>
        </div>
      )}
      <p className="pairing-footnote">Pairing codes expire after 15 minutes and can only be used once. Keep the device configuration private; it contains the device's reconnect secret.</p>
    </section>
  )
}
