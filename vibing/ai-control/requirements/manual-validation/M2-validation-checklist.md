# M2 Manual Validation Checklist

Status: pending — M2 implementation and automated validation are complete; STOP POINT 2 remains open until these integrated checks are confirmed.

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

## Real OIDC provider

- From a signed-out browser, sign in via a configured provider and confirm the expected account is authenticated.
- Reject an unknown email as an account-link shortcut: an identity is only linked after signing in to the destination account and using the explicit confirmation flow.
- Confirm a disabled test account is denied by both local and OIDC login.
- Do not use or link a production identity unless intended.

## Audit log

- As owner/admin, inspect audit entries for login, team/invite, pairing, execution, share/revoke and admin changes; verify timestamp, actor, computer, action and outcome.
- As an operator, verify only own activity is visible; as a viewer, verify execution details are not visible.
- Exercise action/computer/time filters, next/previous pagination, and JSON/CSV exports. Confirm CSV opens safely and output contains redacted values only.
- Confirm no normal-user update/delete operation exists; if testing retention, use an admin and a cutoff older than one day, then confirm the pruning event remains visible.

## Record results

Add a dated follow-up entry here or in PROGRESS.md with pass/fail and non-secret evidence only. Never record passwords, provider secrets, tokens, pairing codes or device secrets.
