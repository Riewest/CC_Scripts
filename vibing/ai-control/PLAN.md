# AI Control for CC:Tweaked - Master Plan

Goal: a web platform where users and AI agents control ComputerCraft computers, turtles and pocket computers over WebSocket.

Target versions: CC:Tweaked 1.120.0 (jar `cc-tweaked-26.1.2-forge-1.120.0.jar`), Minecraft 26.1.2. Source: https://github.com/cc-tweaked/CC-Tweaked/tree/v26.1.2-1.120.0

## How to use this plan (agents read this first)
- Rules for coding agents are in [AGENTS.md](AGENTS.md). Session history is in [PROGRESS.md](PROGRESS.md).
- Status values: `todo`, `in-progress`, `blocked`, `done`. This table is the single source of truth; keep each REQ file's `Status:` header in sync with it.
- Work milestones in order. STOP at every STOP POINT and wait for the user.

## Locked decisions
| Area | Decision |
|---|---|
| Backend | Python 3.12, FastAPI + uvicorn, native WebSockets |
| Frontend | React + Vite + TypeScript, built and served by FastAPI |
| DB | SQLite via SQLAlchemy 2 + Alembic (must stay Postgres-compatible) |
| Tests | pytest only (plus a Python fake-CC client); Lua verified by manual in-game checklists |
| Deploy | Docker + docker-compose |
| Legacy | `../../ccc` is reference only; do not modify. Greenfield here |
| Auth | Local password (argon2) + sessions, OIDC (generic), API tokens, roles admin/user |
| Ownership | Personal, team, groups (shareable), per-computer shares (viewer/operator/owner) |
| AI | Provider interface; adapters: GitHub Models, OpenAI-compatible, Anthropic. Autonomy per computer |
| Transport | Client-initiated WS only. Document LAN/localhost and public TLS (wss) |
| Position | Turtles use `../../squid/INS.lua` for coordinates |

## Target layout
```
vibing/ai-control/
  PLAN.md  PROGRESS.md  AGENTS.md  ideas.md
  requirements/REQ-NNN-*.md
  server/   (FastAPI app, alembic, tests)
  web/      (React + Vite)
  client/   (Lua client served by the server)
  docs/
  docker-compose.yml
```

## Milestones and requirements

### M0 Foundation
| ID | Title | Depends | Status |
|---|---|---|---|
| [REQ-001](requirements/REQ-001-project-scaffold.md) | Project scaffold | - | done |
| [REQ-002](requirements/REQ-002-data-model.md) | Data model and migrations | 001 | todo |
| [REQ-003](requirements/REQ-003-wire-protocol.md) | Wire protocol spec | 001 | todo |

### M1 MVP: basic computer control
| ID | Title | Depends | Status |
|---|---|---|---|
| [REQ-004](requirements/REQ-004-ws-gateway.md) | WebSocket gateway | 002, 003 | todo |
| [REQ-005](requirements/REQ-005-lua-client.md) | Lua client and installer | 003, 004 | todo |
| [REQ-006](requirements/REQ-006-local-auth.md) | Local auth and sessions | 002 | todo |
| [REQ-007](requirements/REQ-007-registration-flow.md) | Computer registration flow | 004, 005, 006 | todo |
| [REQ-008](requirements/REQ-008-mvp-ui.md) | MVP web UI | 006, 007 | todo |

**STOP POINT 1 (MVP checklist):** install on a fresh computer via the pasted command; pair with code; see it online; run Lua and see output; trigger an error and see traceback; interrupt a `while true do end` loop; restart the server and see the client reconnect; test on a turtle and a pocket computer.

### M2 Multi-user and sharing
| ID | Title | Depends | Status |
|---|---|---|---|
| [REQ-009](requirements/REQ-009-oidc-roles.md) | OIDC login and roles | 006 | todo |
| [REQ-010](requirements/REQ-010-api-tokens.md) | API tokens | 006 | todo |
| [REQ-011](requirements/REQ-011-teams.md) | Teams | 006, 007 | todo |
| [REQ-012](requirements/REQ-012-groups-sharing.md) | Groups and sharing | 011 | todo |
| [REQ-013](requirements/REQ-013-audit-log.md) | Audit log | 008 | todo |

**STOP POINT 2:** two users, one team, a shared group; verify permissions across viewer/operator/owner; OIDC login with a real provider; audit entries visible.

### M3 Operator tooling
| ID | Title | Depends | Status |
|---|---|---|---|
| [REQ-014](requirements/REQ-014-script-library.md) | Script library and repo import | 008 | todo |
| [REQ-015](requirements/REQ-015-peripheral-explorer.md) | Peripheral explorer | 008 | todo |
| [REQ-016](requirements/REQ-016-terminal-mirror.md) | Live terminal mirror | 008 | todo |
| [REQ-017](requirements/REQ-017-file-manager.md) | File manager and editor | 008 | todo |
| [REQ-018](requirements/REQ-018-event-streaming.md) | Event streaming | 008 | todo |
| [REQ-019](requirements/REQ-019-fleet-runs.md) | Fleet runs | 012, 014 | todo |

**STOP POINT 3:** exercise each tool in game.

### M4 AI core
| ID | Title | Depends | Status |
|---|---|---|---|
| [REQ-020](requirements/REQ-020-ai-providers.md) | Provider abstraction and adapters | 002 | todo |
| [REQ-021](requirements/REQ-021-ai-chat.md) | Per-computer AI chat | 020, 008 | todo |
| [REQ-022](requirements/REQ-022-agent-tool-loop.md) | Agent tool loop | 021, 015 | todo |
| [REQ-023](requirements/REQ-023-autonomy-review.md) | Autonomy modes and review | 022, 014 | todo |
| [REQ-024](requirements/REQ-024-safety-guards.md) | Safety guards and kill switch | 022 | todo |
| [REQ-025](requirements/REQ-025-long-running-goals.md) | Long-running resumable goals | 023, 024 | todo |
| [REQ-026](requirements/REQ-026-ai-context.md) | AI context and CC knowledge | 022 | todo |

**STOP POINT 4:** ask the AI to do small tasks on a turtle in all three autonomy modes; verify approval, guards, and resume after restart.

### M5 Advanced
| ID | Title | Depends | Status |
|---|---|---|---|
| [REQ-027](requirements/REQ-027-ins-world-map.md) | INS integration and world map | 005, 008 | todo |
| [REQ-028](requirements/REQ-028-mcp-server.md) | MCP server | 010, 022 | todo |
| [REQ-029](requirements/REQ-029-swarm-planner.md) | Swarm coordination | 025, 027 | todo |
| [REQ-030](requirements/REQ-030-metadata-notifications.md) | Labels, tags, notifications | 008 | todo |

**STOP POINT 5:** map view with live turtles; MCP tools used from VS Code; two-turtle swarm task.

### M6 Hardening
| ID | Title | Depends | Status |
|---|---|---|---|
| [REQ-031](requirements/REQ-031-deployment-docs.md) | Deployment and transport docs | all | todo |
| [REQ-032](requirements/REQ-032-test-coverage.md) | Test coverage and fake CC client | all | todo |
| [REQ-033](requirements/REQ-033-security-review.md) | Security review | all | todo |

**STOP POINT 6:** release readiness review.

## Open questions (resolve with user when reached)
- Exact MVP port/hostname defaults for the dev server.
- Whether the Lua client should be a single bundled file or a small package.
