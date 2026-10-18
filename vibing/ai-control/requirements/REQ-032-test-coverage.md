# REQ-032 Test coverage and fake CC client
Status: todo | Milestone: M6 | Depends: all

## Goal
Make the pytest suite robust and fast, with a reusable fake CC client that exercises the whole protocol.

## Design notes
- `tests/fakecc.py` (started in REQ-004) grows to simulate: pairing, hello, telemetry, exec with errors, interrupt, fs, peripherals, events, terminal frames, chunking, turtle moves with an INS-like position.
- Fixtures for users/teams/computers/shares to test the permission matrix in one parametrised suite.
- Coverage target 85% on server code, enforced in CI config (GitHub Actions workflow running pytest and ruff; frontend lint and build).
- Contract test: protocol doc examples are parsed and validated by the Pydantic models.
- End-to-end test: start the app on a random port, connect fake client and a test UI websocket, run full flows.

## Acceptance criteria
- [ ] Fake client covers every client-side message type.
- [ ] Coverage >= 85% and enforced.
- [ ] Permission matrix test covers all endpoint categories.
- [ ] CI workflow added and passing locally via `act` or equivalent dry check.

## Test plan
This REQ is the test plan; the suite itself is the deliverable.

## Files touched
`server/tests/**`, `.github/workflows/ai-control.yml` (repo root), `pyproject.toml`.
