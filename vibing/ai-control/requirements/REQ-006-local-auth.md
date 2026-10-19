# REQ-006 Local auth and sessions
Status: done | Milestone: M1 | Depends: REQ-002

## Goal
Username/password login with secure sessions protecting the API and UI.

## Design notes
- argon2id hashing; password policy (min length 12, no max below 128).
- First run: if no users exist, `/setup` lets the creator make the admin (or env bootstrap vars).
- Session cookies: HttpOnly, Secure when HTTPS, SameSite=Lax; server-side session table or signed tokens with rotation; CSRF protection for cookie-authenticated state-changing requests.
- Endpoints: register (toggle via setting `AIC_ALLOW_SIGNUP`), login, logout, me, change password.
- Login rate limiting and lockout backoff.
- A FastAPI dependency `current_user` that later accepts API tokens (REQ-010) and OIDC sessions (REQ-009).
- WebSocket auth for the browser: same session cookie validated on connect, with origin check.

## Acceptance criteria
- [x] Signup toggle respected; first-user bootstrap works once only.
- [x] Wrong password and unknown user give identical responses.
- [x] Rate limiting blocks brute force.
- [x] Unauthenticated access to protected routes returns 401.
- [x] CSRF check enforced on mutating cookie-auth requests.
- [x] Logout invalidates the session server-side.

## Test plan
pytest: hashing, login/logout, bootstrap, rate limit, CSRF, protected routes.

## Files touched
`server/aicontrol/auth/**`, `server/tests/test_auth.py`.
