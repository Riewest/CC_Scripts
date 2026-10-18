# REQ-025 Long-running resumable goals
Status: todo | Milestone: M4 | Depends: REQ-023, REQ-024

## Goal
Give the AI a high-level goal (e.g. "build a quarry") that runs over a long time and survives restarts of the server, client, or agent.

## Design notes
- `goals`: description, status (planning, running, paused, waiting_approval, blocked, done, failed, cancelled), computer(s), autonomy mode, budget (steps, tokens, time), created by.
- `goal_steps`: ordered plan items with status and results; the AI maintains a plan via tools `update_plan`, `record_note`, `complete_goal`, `fail_goal`.
- Checkpointing: after every tool call the state (plan, notes, last messages summary) is persisted; on restart, runner resumes by rebuilding context from the plan, notes and recent steps (not full history).
- Client side: long tasks written to disk by AI scripts should be resumable; provide a helper library on the client (`aicontrol.task`) to persist progress in `/aicontrol/tasks/` and resume on reboot via startup hook.
- Controls: pause, resume, cancel, edit plan, adjust budget; progress timeline UI; notifications on completion or block.
- Offline computer: goal waits and resumes on reconnect.

## Acceptance criteria
- [ ] Goal survives server restart and resumes from checkpoint.
- [ ] Pause/resume/cancel stop and restart cleanly including running Lua.
- [ ] Budgets enforced; exceeding them blocks the goal.
- [ ] Plan and notes visible and editable in the UI.
- [ ] Client task helper persists and resumes after computer reboot (manual).

## Test plan
pytest: simulate server restart mid-goal with MockProvider, budgets, pause/cancel, offline wait.

## Files touched
`server/aicontrol/ai/goals/**`, `client/task.lua`, `web/src/pages/Goals.tsx`.
