# Audit log

The audit log records security-relevant control-plane actions as append-only events. It is intended for accountability and operational review; execution runs remain the detailed program/output history, while audit records contain a redacted action summary and link to the run ID.

## What is recorded

- Local setup, registration, successful/failed login, logout, password change, OIDC login/identity linking outcomes, user role/disable changes.
- API token creation, use and revocation. Only token ID/prefix/scopes are recorded; bearer credentials are never stored in the audit event.
- Pairing/re-pair request and successful device pairing; never the one-time pairing code or device secret.
- Computer rename, execution request/result, interrupt, emergency stop, reboot, and device-reported errors.
- Team creation/role changes/member invites and lifecycle, computer ownership transfers, group membership and sharing grants/revocations.

Every event includes UTC creation time, actor kind and user/token identity where available, action, outcome, target/computer, source IP where available, and structured redacted details. Recursive field-name filtering and inline bearer/token/password scrubbing happens before persistence.

## Visibility and use

Open **Audit** from the dashboard for account-level activity, or choose **Activity** on a computer for a filtered view. Computer owners and administrators can see events for computers they own/manage. Operators can see only actions they performed (including their own API-token actions); viewers do not see execution details. Account-level authentication/security events are visible to the actor and administrators.

Filters include computer, action, actor user ID, outcome, and time range. Results are ordered newest first and paginated. **Export JSON** and **Export CSV** honor the same visibility and filters and are capped at 10,000 rows per export.

Audit rows cannot be edited or deleted through application CRUD. An administrator may explicitly prune events older than a supplied UTC timestamp using the protected retention endpoint; it refuses cutoffs newer than one day and records the pruning operation after deletion. There is no automatic retention task. Back up the database according to your deployment retention policy.
