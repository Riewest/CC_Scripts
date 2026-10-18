# REQ-016 Live terminal mirror
Status: todo | Milestone: M3 | Depends: REQ-008

## Goal
See the computer's screen in the browser and send keyboard/mouse input.

## Design notes
- Client mirrors the current terminal via a wrapper over `term` (redirect target that duplicates to the real terminal) sending diffed frames: size, cursor, text rows, fg/bg colour strings, palette; throttled (e.g. 5-10 fps) and coalesced.
- Browser renders with a canvas/DOM grid using the CC palette; supports advanced/colour and monochrome; pocket and turtle sizes.
- Input: `term_input` messages become `os.queueEvent` events (`key`, `key_up`, `char`, `mouse_click`, `mouse_scroll`, `paste`, `terminate`).
- Mirror only active while a UI subscriber exists (client told to start/stop).
- Viewer role is read-only; operator can type.

## Acceptance criteria
- [ ] Screen renders correctly with colours and cursor.
- [ ] Typing and mouse clicks reach the program (e.g. `lua` REPL, `edit`).
- [ ] Frame rate limited and bandwidth bounded; no mirroring when nobody watches.
- [ ] Ctrl+T terminate works.
- [ ] Viewer cannot send input.

## Test plan
pytest: frame diff encode/decode, subscription start/stop, role check. Manual in game.

## Files touched
`server/aicontrol/terminal/**`, `client/terminal.lua`, `web/src/components/Terminal.tsx`.
