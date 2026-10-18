# REQ-017 File manager and editor
Status: todo | Milestone: M3 | Depends: REQ-008

## Goal
Browse, view, edit, upload, download and delete files on a computer's filesystem from the web.

## Design notes
- Protocol `fs_op`: list, stat, read, write, mkdir, delete, move, copy, with `fs.getFreeSpace`/capacity reporting. Large files are chunked (REQ-003).
- Protect the client itself: deleting or overwriting `/aicontrol/*` and `startup.lua` requires an explicit force flag and owner role.
- Read-only filesystem paths (`rom`) shown but not writable.
- UI: tree view, editor for text, binary detection (download only), upload/download, free-space display.
- Operator can write; viewer can read.

## Acceptance criteria
- [ ] List/read/write/delete/move/copy work including large files via chunks.
- [ ] Protected client paths need force and owner role.
- [ ] Binary files handled without corruption.
- [ ] Errors from `fs` returned verbatim.

## Test plan
pytest: chunked read/write with fake client, protection rules, role checks.

## Files touched
`server/aicontrol/files/**`, `client/fs.lua`, `web/src/pages/Files.tsx`.
