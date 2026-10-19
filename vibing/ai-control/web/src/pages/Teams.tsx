import { FormEvent, useCallback, useEffect, useState } from 'react'

type Team = { id: string; name: string; slug: string; default_member_role: 'viewer' | 'operator'; role: 'owner' | 'member'; member_count: number }
type Member = { user_id: string; username: string; role: 'owner' | 'member' }
type Invite = { id: string; team_id: string; team_name: string; expires_at: string }

function csrfToken() { return document.cookie.split('; ').find((part) => part.startsWith('aic_csrf='))?.slice('aic_csrf='.length) ?? '' }
async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init, credentials: 'include',
    headers: { ...(init.body ? { 'Content-Type': 'application/json' } : {}), 'X-CSRF-Token': csrfToken(), ...init.headers },
  })
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail ?? `Request failed (${response.status})`) }
  return response.status === 204 ? (undefined as T) : response.json()
}

export function Teams({ onBack }: { onBack: () => void }) {
  const [teams, setTeams] = useState<Team[]>([])
  const [invites, setInvites] = useState<Invite[]>([])
  const [members, setMembers] = useState<Record<string, Member[]>>({})
  const [teamName, setTeamName] = useState('')
  const [inviteNames, setInviteNames] = useState<Record<string, string>>({})
  const [createdInvite, setCreatedInvite] = useState('')
  const [defaultRole, setDefaultRole] = useState<'viewer' | 'operator'>('operator')
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const [teamList, inviteList] = await Promise.all([api<Team[]>('/api/teams'), api<Invite[]>('/api/teams/invites')])
      setTeams(teamList)
      setInvites(inviteList)
      const rosters = await Promise.all(teamList.map(async (team) => [team.id, await api<Member[]>(`/api/teams/${encodeURIComponent(team.id)}/members`)] as const))
      setMembers(Object.fromEntries(rosters))
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load teams') }
  }, [])
  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    const inviteToken = new URLSearchParams(window.location.hash.slice(1)).get('team_invite')
    if (!inviteToken) return
    window.history.replaceState({}, '', window.location.pathname + window.location.search)
    void api(`/api/teams/invites/${encodeURIComponent(inviteToken)}/accept`, { method: 'POST' })
      .then(refresh)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Could not accept invitation'))
  }, [refresh])

  async function createTeam(event: FormEvent) {
    event.preventDefault(); setError('')
    try { await api('/api/teams', { method: 'POST', body: JSON.stringify({ name: teamName, default_member_role: defaultRole }) }); setTeamName(''); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not create team') }
  }
  async function invite(team: Team) {
    setError('')
    try {
      const result = await api<{ invite_token: string; expires_at: string }>(`/api/teams/${encodeURIComponent(team.id)}/invites`, { method: 'POST', body: JSON.stringify({ username: inviteNames[team.id] ?? '' }) })
      setCreatedInvite(result.invite_token)
      setInviteNames((current) => ({ ...current, [team.id]: '' }))
      await navigator.clipboard.writeText(`${window.location.origin}/#team_invite=${encodeURIComponent(result.invite_token)}`).catch(() => undefined)
      await refresh()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not invite user') }
  }
  async function accept(token: string) {
    try { await api(`/api/teams/invites/${encodeURIComponent(token)}/accept`, { method: 'POST' }); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not accept invitation') }
  }
  async function removeMember(team: Team, member: Member) {
    if (!window.confirm(`Remove ${member.username} from ${team.name}?`)) return
    try { await api(`/api/teams/${encodeURIComponent(team.id)}/members/${encodeURIComponent(member.user_id)}`, { method: 'DELETE' }); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not remove member') }
  }
  async function transfer(team: Team, member: Member) {
    if (!window.confirm(`Transfer ownership of ${team.name} to ${member.username}?`)) return
    try { await api(`/api/teams/${encodeURIComponent(team.id)}/transfer-ownership`, { method: 'POST', body: JSON.stringify({ user_id: member.user_id }) }); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not transfer ownership') }
  }
  async function leave(team: Team) {
    if (!window.confirm(`Leave ${team.name}? You may need another owner to transfer ownership first.`)) return
    try { await api(`/api/teams/${encodeURIComponent(team.id)}/leave`, { method: 'POST' }); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not leave team') }
  }
  async function changeRole(team: Team, role: 'viewer' | 'operator') {
    try { await api(`/api/teams/${encodeURIComponent(team.id)}`, { method: 'PATCH', body: JSON.stringify({ default_member_role: role }) }); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not change default role') }
  }
  async function deleteTeam(team: Team) {
    if (!window.confirm(`Permanently delete ${team.name}? Team computers must be transferred or deleted first.`)) return
    try { await api(`/api/teams/${encodeURIComponent(team.id)}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm: true }) }); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not delete team') }
  }

  return <div className="dashboard-page">
    <header className="topbar"><a className="brand" href="#" onClick={(event) => event.preventDefault()}><span className="brand-mark">⌘</span><span>AI Control</span></a><button className="text-button" onClick={onBack}>← Back to fleet</button></header>
    <main className="dashboard-content admin-content">
      <p className="eyebrow">COLLABORATION</p><h1 className="dashboard-title">Teams</h1><p className="intro dashboard-intro">Teams own devices together. Team members can see every team computer; the default member role controls their capabilities.</p>
      {error && <p className="error-banner">{error}</p>}
      {createdInvite && <section className="token-once"><strong>Invitation link copied. Share only with the invited username.</strong><code>{window.location.origin}/#team_invite={encodeURIComponent(createdInvite)}</code><button className="text-button" onClick={() => setCreatedInvite('')}>Dismiss</button></section>}
      <form className="pairing-card team-create" onSubmit={(event) => void createTeam(event)}><label className="field-label" htmlFor="team-name">TEAM NAME</label><input id="team-name" value={teamName} onChange={(event) => setTeamName(event.target.value)} maxLength={120} required /><label className="field-label" htmlFor="team-default-role">DEFAULT MEMBER ROLE</label><select id="team-default-role" value={defaultRole} onChange={(event) => setDefaultRole(event.target.value as 'viewer' | 'operator')}><option value="viewer">Viewer · telemetry and runs</option><option value="operator">Operator · viewer plus execution</option></select><button className="primary-button">Create team<span>→</span></button></form>
      {invites.length > 0 && <section className="team-section"><p className="field-label">PENDING INVITATIONS</p>{invites.map((inviteItem) => <article className="admin-user" key={inviteItem.id}><div><strong>{inviteItem.team_name}</strong><small>Expires {new Date(inviteItem.expires_at).toLocaleString()}</small></div><button className="primary-button team-action" onClick={() => void accept(inviteItem.id)}>Accept</button></article>)}</section>}
      <section className="team-section"><p className="field-label">YOUR TEAMS</p>{teams.length === 0 && <p className="muted-text">You are not a member of any teams yet.</p>}{teams.map((team) => <article className="team-card" key={team.id}>
        <div className="team-heading"><div><h2>{team.name}</h2><small>{team.role} · {team.member_count} members</small></div><span className="owner-badge">TEAM</span></div>
        {team.role === 'owner' && <div className="team-controls"><label className="admin-field">Member access<select value={team.default_member_role} onChange={(event) => void changeRole(team, event.target.value as 'viewer' | 'operator')}><option value="viewer">Viewer</option><option value="operator">Operator</option></select></label><label className="admin-field">Invite username<input value={inviteNames[team.id] ?? ''} onChange={(event) => setInviteNames((current) => ({ ...current, [team.id]: event.target.value }))} maxLength={80} placeholder="existing account username" /></label><button className="secondary-button" disabled={!(inviteNames[team.id] ?? '').trim()} onClick={() => void invite(team)}>Create invite link</button></div>}
        <div className="member-list">{(members[team.id] ?? []).map((member) => <div className="member-row" key={member.user_id}><span>{member.username}<small>{member.role}</small></span>{team.role === 'owner' && member.user_id !== undefined && <div>{member.role !== 'owner' && <button className="secondary-button" onClick={() => void transfer(team, member)}>Transfer ownership</button>}{(members[team.id] ?? []).length > 1 && <button className="text-button" onClick={() => void removeMember(team, member)}>Remove</button>}</div>}</div>)}</div>
        <button className="text-button team-leave" onClick={() => void leave(team)}>Leave team</button>
        {team.role === 'owner' && <button className="text-button team-delete" onClick={() => void deleteTeam(team)}>Delete team</button>}
      </article>)}</section>
    </main>
  </div>
}
