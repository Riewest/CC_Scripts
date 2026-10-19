# M2 Manual Validation Checklist

Status: complete — user accepted M2 manual validation as sufficient for STOP POINT 2 on 2026-10-19. Trial notes and Authentik follow-up fixes remain below for traceability; future bugs may be handled separately.

## Setup

- Build/deploy the current AI Control revision using the existing persistent Docker volume. Do not remove or recreate the data volume.
- Configure a real HTTPS OIDC provider using the instructions in [auth.md](../../docs/auth.md). Keep provider secrets in the protected deployment environment; do not paste secrets into the UI, logs, chat or git.
- Use two enabled test accounts and a harmless, online ComputerCraft computer. Do not transfer existing personal computers unless intentionally testing the explicit transfer flow.

## Two-user team and sharing permissions

- Sign in as User A; create a team with default member role `viewer`; invite User B and accept the invitation while authenticated as B.
- Register a fresh disposable computer directly to the team. Verify it appears for both A and B with a TEAM badge, and that neither account's existing personal devices changed owners.
- Verify B can view telemetry and run history but cannot execute code, interrupt, reboot, rename or re-pair while the team role is viewer.
- As the team owner, change the default role to `operator`; verify B can now run and interrupt but still cannot rename/re-pair or change team ownership.
- Verify the team owner can perform owner operations, transfer ownership, and that removing/leaving the final owner is rejected.
- Create a group, add the team computer, share the group to the other user/team at viewer and operator roles, then verify the effective highest grant and access boundaries.
- While the recipient has an open dashboard WebSocket, revoke the direct/group grant. Verify the socket disconnects within 15 seconds and the next API request is denied; reconnect only after fresh authorization.
- If testing personal-to-team transfer, use an offline test computer and explicitly invoke the transfer flow. Confirm personal ownership never changes merely because of a team membership/invite.

### Trial Notes:
Good enough for first pass

## Real OIDC provider

- Configure the existing Authentik instance using [the Authentik setup steps](../../docs/auth.md#authentik-setup): create an OAuth2/OIDC application/provider, use the default per-provider issuer, configure a confidential authorization-code client with an RSA signing key, register the exact HTTPS callback, assign a test user/group, set `AIC_PUBLIC_URL` and `AIC_OIDC_PROVIDERS`, then recreate the app container without deleting its volume.
- Rotate the Authentik client secret used during the initial trial before relying on it; it was disclosed while being configured. Store only the replacement in the ignored `.env`/secret manager, never Compose YAML or git.
- Before login, verify Authentik's discovery document for the configured issuer is reachable from AI Control and returns the same issuer plus HTTPS authorization, token and JWKS endpoints. Do not share the client secret or callback authorization code.
- From a signed-out browser, choose **Continue with authentik** and confirm the test account is authenticated as a normal `user`. A new account should use Authentik's `preferred_username` if valid and unused. Verify `/api/auth/me` reports that username and subsequent login returns the same user ID.
- For `riewest14`, because the first trial already created an empty generated OIDC-only shadow account, sign in to the existing local account and use **Link authentik**. The link flow should transfer the Authentik identity from that generated account, disable the empty shadow account, revoke its browser sessions and preserve the local account ID. Verify the old shadow session receives 401 and subsequent Authentik login resolves to the existing local user. This narrowly scoped recovery refuses accounts with a password, devices, teams, groups, shares, API tokens, history or other resources; do not delete/reassign accounts manually.
- Confirm the installed Authentik `profile` scope mapping emits `preferred_username` in the signed ID token; `testuser` should now appear as `testuser` instead of a generated `oidc-...` name.
- While signed into the intended destination account, test **Link authentik** with explicit confirmation; verify the provider identity is linked only to that account. Do not expect email matching to link accounts.
- Reject an unknown email as an account-link shortcut: an identity is only linked after signing in to the destination account and using the explicit confirmation flow.
- Confirm a disabled test account is denied by both local and OIDC login.
- Do not use or link a production identity unless intended.

### Trial Notes:
I logged in with my authentik account (username riewest14) and it made a new user in the web server but the username is `oidc-authentik-0ac89f5ef37f9e383917aa2a` I want it to have my authentik username. But I do already have a local user in the ai-control with the same username so it should just automap.

I also used an authentik user called `testuser` and it also ended up with an oidc-authentick... username

### Follow-up implementation
- New OIDC-created accounts now use Authentik's signed `preferred_username` when valid and not already taken; after deploying the update, `testuser` should appear as `testuser`.
- `riewest14` must not automatically map to the existing local account based only on username/email. The callback reports a collision and requires local sign-in plus explicit **Link authentik** confirmation. It can reclaim only the legacy generated OIDC shadow account if it has no password, resources, or authored run/script/goal/audit history; it disables that empty shadow account. Verify a shadow account with a device/history is refused, preserving account takeover boundaries and computer ownership.
- While User A is signed in, verify a fresh Authentik `testuser` login creates a local account named `testuser` (if the signed `preferred_username` claim is enabled and unused).
- After linking `riewest14`, verify the old generated shadow account is disabled and had no devices/resources; verify the local account remains enabled and retains its original computer ownership.
- The provider secret was hard-coded in the Compose configuration during the trial. It has been removed from the YAML; rotate that client secret in Authentik, place the replacement in the ignored `.env`/secret store as `AIC_OIDC_PROVIDERS`, and recreate the app container. Never commit or share the replacement secret.

## Audit log

- As owner/admin, inspect audit entries for login, team/invite, pairing, execution, share/revoke and admin changes; verify timestamp, actor, computer, action and outcome.
- As an operator, verify only own activity is visible; as a viewer, verify execution details are not visible.
- Exercise action/computer/time filters, next/previous pagination, and JSON/CSV exports. Confirm CSV opens safely and output contains redacted values only.
- Confirm no normal-user update/delete operation exists; if testing retention, use an admin and a cutoff older than one day, then confirm the pruning event remains visible.

### Trial notes:
This looked all good

## Record results

User accepted the team/sharing trial as good enough for this milestone; audit review looked good. Authentik login succeeded; preferred-username handling and the existing `riewest14` account collision were then addressed in code, and generated OIDC test users were removed. No passwords, provider secrets, tokens, pairing codes or device secrets are recorded here. Any later M2 regression should be appended as a dated follow-up, not treated as permission to start M3.
