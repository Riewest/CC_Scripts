# REQ-019 Fleet runs
Status: todo | Milestone: M3 | Depends: REQ-012, REQ-014

## Goal
Run a script or snippet on many computers at once (a group, a selection, or a team) and see per-computer results.

## Design notes
- `fleet_runs` with target set resolved at start, concurrency limit, timeout, failure policy (continue/stop on first failure), and per-computer result rows.
- Only computers where the user has operator or higher are targeted; others are listed as skipped.
- Offline computers: skipped or queued until online (option, default skipped).
- Live progress view; cancel interrupts all running members.
- Fleet runs are audited as one parent event plus per-computer children.

## Acceptance criteria
- [ ] Run on group/selection with parameters; per-computer status, output and errors.
- [ ] Concurrency and timeout enforced; cancel works.
- [ ] Permission filtering shows skipped computers with reasons.
- [ ] Audit parent/child events written.

## Test plan
pytest: multiple fake clients, partial failures, cancellation, permissions.

## Files touched
`server/aicontrol/fleet/**`, `web/src/pages/Fleet.tsx`.
