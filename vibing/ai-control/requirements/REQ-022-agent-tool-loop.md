# REQ-022 Agent tool loop
Status: todo | Milestone: M4 | Depends: REQ-021, REQ-015

## Goal
The AI observes and acts iteratively through tools until the task is done.

## Design notes
- Loop: model call, tool calls executed, results appended, repeat until final answer or limits (max steps, max tokens, wall time, per-step timeout).
- Tools (JSON Schema): `run_lua(code, timeout)`, `get_telemetry()`, `list_peripherals()`, `call_peripheral(name, method, args)`, `read_file(path)`, `write_file(path, content)`, `list_files(path)`, `get_events(filter)`, `get_position()` (INS), `list_scripts()`, `run_script(name, params)`, `save_script(name, code, description)`, `ask_user(question)` (pauses for the user), `stop()`.
- Every tool call is permission-checked as the invoking user, audited with AI session id, and shown in the chat as an expandable step.
- Tool errors are returned to the model as structured results so it can recover; repeated identical failures abort the loop.
- Interrupt/stop from the user cancels the loop and any running program.
- Tool registry is extensible; tools can be disabled per computer.

## Acceptance criteria
- [ ] Loop runs multi-step tasks against the fake client using MockProvider scripted tool calls.
- [ ] Limits enforced and reported.
- [ ] All tool calls audited and permission-checked.
- [ ] Cancel stops loop and running Lua.
- [ ] Loop detection aborts repeated failures.

## Test plan
pytest: scripted multi-step runs, each tool, limit breaches, cancellation, permission denial.

## Files touched
`server/aicontrol/ai/agent/**`, tests.
