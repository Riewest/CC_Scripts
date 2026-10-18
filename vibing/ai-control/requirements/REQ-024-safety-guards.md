# REQ-024 Safety guards and kill switch
Status: todo | Milestone: M4 | Depends: REQ-022

## Goal
Limit damage from AI mistakes: guards on turtle behaviour, rate limits, and a global stop.

## Design notes
- Per-computer policy (owner-editable): max commands per minute, max concurrent runs, max run duration, allowed/blocked APIs (default warn-block `fs.delete` on `/`, `/rom`, `/aicontrol`, `startup.lua`, `os.shutdown`/`reboot` in AI code unless allowed), max fuel use per task, min fuel reserve for return trip.
- Turtle movement guards installed by the client wrapper when running AI code: wrap `turtle.forward/up/down/back` to refuse moving into lava or void (`inspect` first; configurable, default on for AI runs), refuse digging blocks on a protected list (chests, spawners, other turtles/computers by tag), enforce a bounding box (optional) relative to INS home.
- Guards are enforced in the client-side environment wrapper AND the server policy check; client wrapper is best effort since arbitrary Lua can bypass it, so docs state the limit honestly.
- Global kill switch (per user and per computer, plus admin global): interrupts running program, cancels AI loops, sets AI to propose mode until re-enabled.
- Automatic stop on repeated errors or abnormal fuel drop.

## Acceptance criteria
- [ ] Rate limits and duration caps enforced with clear errors to the AI and the user.
- [ ] Blocked-API static check on AI code, with owner override.
- [ ] Movement guards work in game (manual) for lava/void/bounding box.
- [ ] Kill switch stops everything within seconds and is audited.
- [ ] Policy editable per computer, with sane defaults.

## Test plan
pytest: policy evaluation, static blocklist, kill switch propagation, rate limiting. Manual: movement guards.

## Files touched
`server/aicontrol/ai/safety/**`, `client/guards.lua`, `web` policy page.
