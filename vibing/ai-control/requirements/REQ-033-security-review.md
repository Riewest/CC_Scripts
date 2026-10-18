# REQ-033 Security review
Status: todo | Milestone: M6 | Depends: all

## Goal
Systematic review and hardening against the OWASP Top 10, given the server may be public facing.

## Checklist (agent verifies each and records findings in PROGRESS.md)
- Broken access control: every route and WS message checked against `effective_role`; IDOR tests on all id-based endpoints.
- Cryptographic failures: argon2 params, encrypted provider keys, secrets only in env, TLS guidance, secure cookies.
- Injection: parameterised queries only; Lua string escaping for script parameters; no shell calls with user input; template and log injection.
- Insecure design: pairing code brute force, rate limits on login, pairing, token auth, WS connect.
- Misconfiguration: security headers (CSP, HSTS, X-Content-Type-Options, frame-ancestors), CORS locked down, debug off, docs endpoints configurable.
- Vulnerable components: dependency audit (`pip-audit`, `npm audit`) with pinned versions.
- Auth failures: session fixation/rotation, logout invalidation, CSRF, OIDC state/nonce/PKCE, WS origin checks.
- Integrity: client self-update integrity (manifest hashes served over TLS; optional signature), audit log append-only.
- Logging: no secrets in logs, audit coverage.
- SSRF: webhook and AI provider base URL validation (private IP allowlist controls).
- Resource abuse: message size limits, per-user quotas, connection caps.

## Acceptance criteria
- [ ] Every checklist item has a recorded result and any fix merged with a test.
- [ ] `pip-audit` and `npm audit` show no unaddressed high/critical issues.
- [ ] Security headers and CSP verified by tests.
- [ ] `docs/security.md` documents the threat model and the honest limits of client-side AI guards.

## Test plan
pytest security tests per item; dependency audit commands recorded in PROGRESS.md.

## Files touched
Across `server/**`, `web/**`, `docs/security.md`.
