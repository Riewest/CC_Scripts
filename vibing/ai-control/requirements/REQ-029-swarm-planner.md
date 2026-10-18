# REQ-029 Swarm coordination
Status: todo | Milestone: M5 | Depends: REQ-025, REQ-027

## Goal
An AI planner that splits a goal across multiple turtles and coordinates them.

## Design notes
- A `swarm` goal has a coordinator agent and worker assignments over a group of turtles.
- Planner decomposes the goal into regions/jobs (e.g. excavate area sliced per turtle using INS coordinates), assigns jobs by position, fuel and tools, and tracks per-turtle progress via normal goals (REQ-025).
- Collision avoidance: server-side reservation of regions and altitude lanes; turtles told their bounding boxes (enforced by REQ-024 guards).
- Rebalancing: failed/low-fuel/offline turtles' jobs are reassigned; refuel/unload logistics jobs supported through chests at known coordinates.
- UI: swarm overview on the map with assignments and progress.

## Acceptance criteria
- [ ] Coordinator creates jobs and per-turtle goals with non-overlapping regions.
- [ ] Failed or offline turtle's job is reassigned.
- [ ] Two-turtle test task completes (manual) and a scripted simulation test passes.
- [ ] All safety, autonomy and budget rules apply per worker.

## Test plan
pytest: region partitioning, assignment, reassignment on failure, using multiple fake clients and MockProvider.

## Files touched
`server/aicontrol/ai/swarm/**`, `web/src/pages/Swarm.tsx`.
