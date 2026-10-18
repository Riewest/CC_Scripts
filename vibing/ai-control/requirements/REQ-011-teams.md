# REQ-011 Teams
Status: todo | Milestone: M2 | Depends: REQ-006, REQ-007

## Goal
Teams own computers; every team member sees all team computers. Registration supports registering a computer to a team.

## Design notes
- Team roles: `owner` (manage members, delete team, full control), `member` (control per team default role), configurable `default_member_role` for team computers: viewer or operator.
- Invites by username or invite link with expiry; leave team; transfer ownership; cannot remove the last owner.
- Team computers: owner_team_id set at registration (REQ-007 owner selector now enabled) or by transferring a personal computer into a team (by its owner).
- Central permission function `effective_role(user, computer)` combines: direct owner, team membership, shares, group shares (REQ-012). Put it in one module with exhaustive tests; all endpoints use it.

## Acceptance criteria
- [ ] Create team, invite, accept, remove member, leave, transfer ownership.
- [ ] Team members see team computers on the dashboard with a team badge.
- [ ] Registration wizard can target a team the user belongs to; others rejected.
- [ ] `effective_role` unit-tested for all combinations.

## Test plan
pytest: team lifecycle, last-owner protection, permission matrix, registration to team.

## Files touched
`server/aicontrol/teams/**`, `server/aicontrol/permissions.py`, `web/src/pages/Teams.tsx`, tests.
