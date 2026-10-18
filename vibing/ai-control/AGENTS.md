# Agent Operating Rules

You are implementing the plan in [PLAN.md](PLAN.md). You may be stopped and restarted at any time; all state lives in files.

## Start of every session
1. Read [PLAN.md](PLAN.md) and the tail of [PROGRESS.md](PROGRESS.md).
2. If a REQ is `in-progress`, resume it. Otherwise pick the first `todo` REQ in milestone order whose dependencies are all `done`.
3. Read that REQ file fully, plus the REQs it depends on.

## While working
- Set the REQ to `in-progress` in both PLAN.md and its file before coding.
- Tick acceptance-criteria checkboxes in the REQ file as each is verified, not in bulk at the end.
- Append to PROGRESS.md after each meaningful step (date, REQ, what changed, decisions, next step), so a restart loses nothing.
- Commit after each completed REQ with message `REQ-NNN: title`.
- Do not modify `../../ccc` or other repo scripts; read them for reference only.
- Keep scope to the REQ. Record out-of-scope ideas in PROGRESS.md under "Ideas", not in code.

## Definition of done for a REQ
- All acceptance criteria ticked.
- Tests listed in the REQ's test plan exist and pass (`pytest` from `server/`); ruff clean; `web/` builds if touched.
- Manual in-game checks that cannot be automated are written into the milestone checklist in PLAN.md.
- Status set to `done` in PLAN.md and the REQ file.

## Milestones
- Stop at each STOP POINT in PLAN.md, summarise to the user, and wait. Do not start the next milestone without approval.
- If blocked or a decision is needed, set status `blocked`, log why in PROGRESS.md, and ask the user.

## Engineering standards
- Python 3.12, type hints, async-first, FastAPI dependency injection, SQLAlchemy 2 style.
- Security: follow OWASP Top 10; hash secrets, parameterised queries only, validate all WS and HTTP input, never log secrets.
- Lua targets CC:Tweaked 1.120.0 (Lua 5.2-compatible Cobalt); no external deps; keep WS messages under the configured size limit.
- Comments only where code cannot explain itself.
