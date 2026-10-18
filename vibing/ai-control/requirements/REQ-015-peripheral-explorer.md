# REQ-015 Peripheral explorer
Status: todo | Milestone: M3 | Depends: REQ-008

## Goal
Discover attached peripherals and their methods, and call them from the UI (and later AI).

## Design notes
- Protocol: `peripheral_list` (names, types, sides, networked remote names), `peripheral_methods` (via `peripheral.getMethods`, plus `peripheral.getType`, `hasType`), `peripheral_call` (name, method, args) returning results or error.
- Handle wired-modem networks (`peripheral.getNamesRemote`) and `getMethods` returning nil.
- For `inventory` peripherals offer helpers: list, getItemDetail, size.
- UI: tree of peripherals, method list, generic argument form (JSON args), result viewer, favourites. Mod peripherals (Advanced Peripherals, AE2 etc.) work generically; no special casing required.
- Calls are interruptible and time-limited; results serialised safely (functions and cycles replaced with markers).

## Acceptance criteria
- [ ] Lists peripherals and methods for local and networked peripherals.
- [ ] Call returns results or errors with message.
- [ ] Serialisation handles cycles, functions, large results (truncate with marker).
- [ ] Requires operator role; viewer can list only.

## Test plan
pytest with fake client for each message; serialization helper tests in Python. Manual: inventory and a modded peripheral.

## Files touched
`server/aicontrol/peripherals/**`, `client/` handlers, `web/src/pages/Peripherals.tsx`.
