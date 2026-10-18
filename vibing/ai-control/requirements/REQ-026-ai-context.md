# REQ-026 AI context and CC:Tweaked knowledge
Status: todo | Milestone: M4 | Depends: REQ-022

## Goal
Make the AI good at ComputerCraft by giving it accurate API knowledge, the environment facts, and this repo's idioms.

## Design notes
- System prompt composed from templates: CC:Tweaked 1.120.0 specifics (Cobalt Lua 5.2 semantics, no `goto` issues, `parallel`, `os.pullEvent`, `textutils`, `fs`, `turtle` API, `peripheral` API, `http`), limits (message size, yield-too-long, output truncation), safety rules, and tool descriptions.
- Computer-specific context block: kind, advanced, fuel, tools equipped, peripherals and their methods, position (INS), installed client version, relevant saved scripts.
- INS usage guide (from `../../squid/INS.lua`: `INS:new`, `forward/up/down`, `turnDir`, `goTo`, `goHome`, `gpsFix`) so coordinate tasks use it; client exposes INS if installed, and `install_ins` helper installs `/squid` from the server.
- Reference snippets from this repo (inventory transfer, machines, AE2, Advanced Peripherals) retrievable by a `search_examples(query)` tool using simple keyword search over imported scripts (REQ-014); no vector DB needed.
- Prompt templates are files editable by admins, versioned, with per-team additions.

## Acceptance criteria
- [ ] System prompt builder with unit tests for each computer kind.
- [ ] `search_examples` tool returns relevant imported scripts.
- [ ] INS guide and installer helper included; turtle prompts prefer INS for coordinates.
- [ ] Prompt size is budgeted and truncated deterministically.

## Test plan
pytest: prompt snapshot tests per kind, budget truncation, example search ranking.

## Files touched
`server/aicontrol/ai/prompts/**`, `server/aicontrol/ai/agent/tools_examples.py`, tests.
