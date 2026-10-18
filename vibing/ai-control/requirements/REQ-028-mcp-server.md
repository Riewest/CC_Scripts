# REQ-028 MCP server
Status: todo | Milestone: M5 | Depends: REQ-010, REQ-022

## Goal
Expose computers as Model Context Protocol tools so external agents (e.g. GitHub Copilot in VS Code, Claude Desktop) can control them.

## Design notes
- Use the official Python MCP SDK; streamable HTTP transport mounted at `/mcp`, authenticated with API tokens (REQ-010) so permissions, scopes, audit and safety all apply.
- Tools mirror the agent tools: list_computers, get_telemetry, run_lua, run_script, list_peripherals, call_peripheral, files, get_events, interrupt. Resources: computer telemetry, scripts. Optionally a stdio shim for local clients.
- Autonomy rules apply: in `propose` mode a tool call returns "pending approval" with an approval link, or waits (configurable).
- docs/mcp.md with a VS Code `mcp.json` example.

## Acceptance criteria
- [ ] MCP client can list and call tools with a token; unauthenticated calls rejected.
- [ ] Same permission, audit and safety paths as the web UI.
- [ ] Verified with the MCP inspector or a pytest MCP client.
- [ ] Docs with VS Code configuration.

## Test plan
pytest using the MCP client SDK against the app: auth, tool listing, calls, permission denial.

## Files touched
`server/aicontrol/mcp/**`, `docs/mcp.md`.
