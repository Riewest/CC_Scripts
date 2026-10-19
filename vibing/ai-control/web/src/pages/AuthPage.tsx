import { FormEvent, useEffect, useState } from 'react'

export function AuthPage({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [setupRequired, setSetupRequired] = useState(false)
  const [providers, setProviders] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      fetch('/api/auth/setup-state', { credentials: 'include' }),
      fetch('/api/auth/oidc/providers', { credentials: 'include' }),
    ])
      .then(async ([setupResponse, providerResponse]) => {
        if (!setupResponse.ok || !providerResponse.ok) throw new Error('Could not load authentication setup state')
        const state = await setupResponse.json()
        const configuredProviders: Array<{ name: string }> = await providerResponse.json()
        setSetupRequired(state.setup_required)
        setProviders(configuredProviders.map((provider) => provider.name))
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Could not connect'))
      .finally(() => setLoading(false))
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const response = await fetch(setupRequired ? '/api/auth/setup' : '/api/auth/login', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(result.detail ?? 'Sign-in failed')
      onAuthenticated()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Sign-in failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div className="auth-loading">Loading account setup…</div>

  return (
    <section className="auth-page">
      <p className="eyebrow">COMPUTERCRAFT · CONTROL PLANE</p>
      <h1>{setupRequired ? <>Claim your<br /><em>control room.</em></> : <>Welcome<br /><em>back.</em></>}</h1>
      <p className="intro">{setupRequired ? 'Create the first administrator account to secure this control plane.' : 'Sign in to reach your connected computers.'}</p>
      <form className="pairing-card auth-card" onSubmit={submit}>
        <label className="field-label" htmlFor="auth-username">USERNAME</label>
        <input id="auth-username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} maxLength={80} required />
        <label className="field-label password-label" htmlFor="auth-password">PASSWORD</label>
        <input id="auth-password" type="password" autoComplete={setupRequired ? 'new-password' : 'current-password'} value={password} onChange={(event) => setPassword(event.target.value)} maxLength={1024} minLength={setupRequired ? 12 : 1} required />
        {error && <p className="error-banner">{error}</p>}
        <button className="primary-button" disabled={submitting}>{submitting ? 'Please wait…' : setupRequired ? 'Create administrator' : 'Sign in'}<span>→</span></button>
        {setupRequired && <p className="pairing-footnote">Use a unique password with at least 12 characters. This first account becomes the administrator. If you paired devices before setting up login, use the same owner username to keep those devices on your account.</p>}
      </form>
      {providers.length > 0 && <div className="oidc-options"><p className="field-label">OR CONTINUE WITH</p>{providers.map((provider) => <a className="secondary-button oidc-button" key={provider} href={`/api/auth/oidc/${encodeURIComponent(provider)}/login`}>Continue with {provider}<span>→</span></a>)}</div>}
    </section>
  )
}
