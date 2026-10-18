# REQ-023 Autonomy modes and review
Status: todo | Milestone: M4 | Depends: REQ-022, REQ-014

## Goal
Per-computer configurable AI autonomy with a review UI, and saving AI scripts to the library.

## Design notes
- Modes per computer (set by owner; operators may only choose equal or stricter):
  1. `propose`: every side-effecting tool call (run_lua, write_file, call_peripheral not marked read-only) waits for approval.
  2. `supervised`: auto-run within safety limits (REQ-024); risky actions (see classification) still need approval.
  3. `autonomous`: runs everything within hard safety limits.
- Review UI: shows code with syntax highlighting, static analysis warnings (e.g. `fs.delete`, `os.shutdown`, `turtle.dig` loops, `shell.run`, `http`), approve, edit-then-approve, reject with feedback to the AI.
- Dry-run: a lint/analysis pass only (parse with a Lua parser such as luaparse or a server-side check) before send; syntax errors are returned to the model without touching the computer.
- Read-only classification list for peripheral methods (e.g. `list`, `getItemDetail`, `size`) so approval isn't needed for observation.
- Approvals have a timeout; pending approvals visible in a global inbox and via notifications (REQ-030 when available).
- One-click "Save to library" for any AI script, tagged `ai-generated` with session link.

## Acceptance criteria
- [ ] All three modes enforced server-side (not just UI).
- [ ] Approve/edit/reject flows work and feed back to the loop.
- [ ] Syntax errors caught before sending.
- [ ] Risky-pattern warnings shown.
- [ ] Mode changes audited; operators cannot loosen the owner's setting.

## Test plan
pytest: mode matrix against scripted tool calls, approval timeout, syntax check, permission on mode change.

## Files touched
`server/aicontrol/ai/autonomy/**`, `web/src/components/ApprovalDialog.tsx`.
