import { FormEvent, useCallback, useEffect, useState } from 'react'

type Computer = { id: string; label: string; role: string; owner_team_id: string | null; kind: string; status: string }
type Group = { id: string; name: string; owner_user_id: string | null; owner_team_id: string | null; computer_ids: string[] }
type Share = { id: string; subject_user_id: string | null; subject_team_id: string | null; computer_id: string | null; group_id: string | null; role: 'viewer' | 'operator' | 'owner' }
type Recipient = { id: string; name: string }

function csrfToken() { return document.cookie.split('; ').find((part) => part.startsWith('aic_csrf='))?.slice('aic_csrf='.length) ?? '' }
async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init, credentials: 'include',
    headers: { ...(init.body ? { 'Content-Type': 'application/json' } : {}), 'X-CSRF-Token': csrfToken(), ...init.headers },
  })
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail ?? `Request failed (${response.status})`) }
  return response.status === 204 ? (undefined as T) : response.json()
}

export function Groups({ onBack }: { onBack: () => void }) {
  const [groups, setGroups] = useState<Group[]>([])
  const [computers, setComputers] = useState<Computer[]>([])
  const [users, setUsers] = useState<Recipient[]>([])
  const [teams, setTeams] = useState<Recipient[]>([])
  const [shares, setShares] = useState<Share[]>([])
  const [groupName, setGroupName] = useState('')
  const [groupTeam, setGroupTeam] = useState('')
  const [targetIds, setTargetIds] = useState<Record<string, string>>({})
  const [shareDraft, setShareDraft] = useState({ recipientType: 'user', recipientId: '', targetType: 'computer', targetId: '', role: 'viewer' as Share['role'] })
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const [groupList, computerList, recipientList, shareList] = await Promise.all([
        api<Group[]>('/api/groups'), api<Computer[]>('/api/sharing/computers'),
        api<{ users: Recipient[]; teams: Recipient[] }>('/api/sharing/recipients'), api<Share[]>('/api/shares'),
      ])
      setGroups(groupList); setComputers(computerList); setUsers(recipientList.users); setTeams(recipientList.teams); setShares(shareList)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load groups and shares') }
  }, [])
  useEffect(() => { void refresh() }, [refresh])

  async function createGroup(event: FormEvent) {
    event.preventDefault(); setError('')
    try { await api('/api/groups', { method: 'POST', body: JSON.stringify({ name: groupName, team_id: groupTeam || null }) }); setGroupName(''); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not create group') }
  }
  async function removeGroup(group: Group) {
    if (!window.confirm(`Delete group ${group.name}? Shares to this group will be revoked.`)) return
    try { await api(`/api/groups/${encodeURIComponent(group.id)}`, { method: 'DELETE' }); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not delete group') }
  }
  async function addComputer(group: Group) {
    const computerId = targetIds[group.id]
    if (!computerId) return
    try { await api(`/api/groups/${encodeURIComponent(group.id)}/computers`, { method: 'POST', body: JSON.stringify({ computer_id: computerId }) }); setTargetIds((current) => ({ ...current, [group.id]: '' })); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not add computer to group') }
  }
  async function removeComputer(group: Group, computerId: string) {
    try { await api(`/api/groups/${encodeURIComponent(group.id)}/computers/${encodeURIComponent(computerId)}`, { method: 'DELETE' }); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not remove computer from group') }
  }
  async function share(event: FormEvent) {
    event.preventDefault(); setError('')
    const recipientField = shareDraft.recipientType === 'user' ? { subject_user_id: shareDraft.recipientId } : { subject_team_id: shareDraft.recipientId }
    const targetField = shareDraft.targetType === 'computer' ? { computer_id: shareDraft.targetId } : { group_id: shareDraft.targetId }
    try { await api('/api/shares', { method: 'POST', body: JSON.stringify({ ...recipientField, ...targetField, role: shareDraft.role }) }); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not share resource') }
  }
  async function revoke(shareId: string) {
    if (!window.confirm('Revoke this share? Active UI sockets will disconnect within seconds.')) return
    try { await api(`/api/shares/${encodeURIComponent(shareId)}`, { method: 'DELETE' }); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not revoke share') }
  }
  const recipientOptions = shareDraft.recipientType === 'user' ? users : teams
  const targetOptions = shareDraft.targetType === 'computer'
    ? computers.map((computer) => ({ id: computer.id, name: `${computer.label} · ${computer.role}` }))
    : groups.map((group) => ({ id: group.id, name: group.name }))

  return <div className="dashboard-page">
    <header className="topbar"><a className="brand" href="#" onClick={(event) => event.preventDefault()}><span className="brand-mark">⌘</span><span>AI Control</span></a><button className="text-button" onClick={onBack}>← Back to fleet</button></header>
    <main className="dashboard-content admin-content">
      <p className="eyebrow">SHARING</p><h1 className="dashboard-title">Groups & sharing</h1><p className="intro dashboard-intro">Group computers, grant viewer/operator/owner access, and revoke access. Revocation closes affected live UI subscriptions within 15 seconds.</p>
      {error && <p className="error-banner">{error}</p>}
      <form className="pairing-card team-create" onSubmit={(event) => void createGroup(event)}><label className="field-label" htmlFor="group-name">GROUP NAME</label><input id="group-name" value={groupName} onChange={(event) => setGroupName(event.target.value)} maxLength={120} required /><label className="field-label" htmlFor="group-team">OWNER</label><select id="group-team" value={groupTeam} onChange={(event) => setGroupTeam(event.target.value)}><option value="">Personal group</option>{teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select><button className="primary-button">Create group<span>→</span></button></form>
      <section className="team-section"><p className="field-label">GROUPS</p>{groups.length === 0 && <p className="muted-text">No groups yet.</p>}{groups.map((group) => <article className="team-card" key={group.id}>
        <div className="team-heading"><div><h2>{group.name}</h2><small>{group.owner_team_id ? 'Team-owned' : 'Personal'} · {group.computer_ids.length} computers</small></div><button className="danger-button" onClick={() => void removeGroup(group)}>Delete</button></div>
        <div className="group-computers">{group.computer_ids.map((id) => { const computer = computers.find((item) => item.id === id); return <div className="member-row" key={id}><span>{computer?.label ?? id}</span><button className="text-button" onClick={() => void removeComputer(group, id)}>Remove</button></div> })}</div>
        <div className="team-controls"><label className="admin-field">Add an accessible computer<select value={targetIds[group.id] ?? ''} onChange={(event) => setTargetIds((current) => ({ ...current, [group.id]: event.target.value }))}><option value="">Select computer</option>{computers.map((computer) => <option key={computer.id} value={computer.id}>{computer.label} · {computer.role}</option>)}</select></label><button className="secondary-button" disabled={!targetIds[group.id]} onClick={() => void addComputer(group)}>Add to group</button></div>
      </article>)}</section>
      <form className="pairing-card share-form" onSubmit={(event) => void share(event)}><p className="field-label">SHARE A COMPUTER OR GROUP</p><div className="share-fields"><label className="admin-field">Recipient type<select value={shareDraft.recipientType} onChange={(event) => setShareDraft((current) => ({ ...current, recipientType: event.target.value, recipientId: '' }))}><option value="user">User</option><option value="team">Team</option></select></label><label className="admin-field">Recipient<select required value={shareDraft.recipientId} onChange={(event) => setShareDraft((current) => ({ ...current, recipientId: event.target.value }))}><option value="">Select recipient</option>{recipientOptions.map((recipient) => <option value={recipient.id} key={recipient.id}>{recipient.name}</option>)}</select></label><label className="admin-field">Resource<select value={shareDraft.targetType} onChange={(event) => setShareDraft((current) => ({ ...current, targetType: event.target.value, targetId: '' }))}><option value="computer">Computer</option><option value="group">Group</option></select></label><label className="admin-field">Computer / group<select required value={shareDraft.targetId} onChange={(event) => setShareDraft((current) => ({ ...current, targetId: event.target.value }))}><option value="">Select resource</option>{targetOptions.map((target) => <option value={target.id} key={target.id}>{target.name}</option>)}</select></label><label className="admin-field">Role<select value={shareDraft.role} onChange={(event) => setShareDraft((current) => ({ ...current, role: event.target.value as Share['role'] }))}><option value="viewer">Viewer</option><option value="operator">Operator</option><option value="owner">Owner</option></select></label></div><button className="primary-button" disabled={!shareDraft.recipientId || !shareDraft.targetId}>Grant access<span>→</span></button></form>
      <section className="team-section"><p className="field-label">SHARES</p>{shares.length === 0 && <p className="muted-text">No direct or group shares yet.</p>}{shares.map((shareItem) => { const recipient = users.find((user) => user.id === shareItem.subject_user_id)?.name ?? teams.find((team) => team.id === shareItem.subject_team_id)?.name ?? 'Unknown recipient'; const target = shareItem.computer_id ? computers.find((computer) => computer.id === shareItem.computer_id)?.label ?? shareItem.computer_id : groups.find((group) => group.id === shareItem.group_id)?.name ?? shareItem.group_id; return <article className="admin-user" key={shareItem.id}><div><strong>{recipient}</strong><small>{target} · {shareItem.role}</small></div><button className="danger-button" onClick={() => void revoke(shareItem.id)}>Revoke</button></article> })}</section>
    </main>
  </div>
}
