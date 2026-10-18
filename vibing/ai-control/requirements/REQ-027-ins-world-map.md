# REQ-027 INS integration and world map
Status: todo | Milestone: M5 | Depends: REQ-005, REQ-008

## Goal
Use `../../squid/INS.lua` as the position source for turtles and show them on a live map.

## Design notes
- Client: if `/squid/INS.lua` present, telemetry includes INS position and facing (`current_coord`, `direction`, home); otherwise GPS fix; otherwise unknown. Server can install INS to the computer from the repo copy (served from `client/vendor/squid`).
- Server tools/endpoints: `set_position(x,y,z,facing)` for user-supplied positions, `go_to(x,y,z)` helper script using `INS:goTo`, `go_home`.
- Map: 2D top-down with Y slice selector plus simple 3D view (three.js optional); shows turtles, home points, trails (recent path), and blocks discovered through an optional `scan` script (turtle `inspect` results reported as `block_seen` events with position).
- Persist block observations per world/dimension key (user-named "world") in the DB with bounded size.
- Click a turtle to open its detail; right-click map point to send `go_to` (operator role, respects safety bounds).

## Acceptance criteria
- [ ] Position and facing updated live for INS and GPS turtles.
- [ ] Positions set manually are respected and persisted by INS.
- [ ] Map renders turtles, trails, observations and Y slices.
- [ ] `go_to` from the map works via INS and is audited and guarded.
- [ ] Dimension/world separation supported.

## Test plan
pytest: position telemetry parsing, observation storage and bounds, go_to endpoint permission. Manual: INS turtle moving on map.

## Files touched
`server/aicontrol/world/**`, `client/ins_bridge.lua`, `web/src/pages/Map.tsx`.
