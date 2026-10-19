# Authentication and account administration

AI Control retains username/password authentication and can additionally use one or more generic OpenID Connect providers. Local sessions remain opaque, server-side, HttpOnly cookies; cookie-authenticated mutations still require the existing CSRF token. Configure `AIC_PUBLIC_URL` to the browser-facing HTTPS origin when deployed behind a TLS proxy.

## Configure an OIDC provider

Set `AIC_OIDC_PROVIDERS` to a JSON array in the server environment (or protected `.env`). The setting is passed through Docker Compose. Never commit real client secrets or include them in support logs.

```json
[
  {
    "name": "company",
    "issuer_url": "https://login.example.com/realms/control",
    "client_id": "ai-control",
    "client_secret": "replace-with-secret-from-secret-manager",
    "scopes": ["openid", "profile", "email"],
    "allowed_email_domains": ["example.com"],
    "auto_create_users": true
  }
]
```

- `issuer_url` must be HTTPS and must exactly match the issuer returned by `/.well-known/openid-configuration`.
- Register this exact redirect URI with the provider: `https://YOUR-AIC-HOST/api/auth/oidc/company/callback` (replace `company` with the configured provider name).
- Authorization code flow uses PKCE S256, browser-bound one-use state, nonce, a confidential-client token exchange, and an ID token signature verified against the provider's HTTPS JWKS. Only RS256 and ES256 ID tokens are accepted. Issuer, audience, timestamps, subject and nonce are checked.
- `allowed_email_domains` is optional. When set, the provider must assert a verified email in one of those domains; the restriction is applied on every login.
- `auto_create_users` controls first-time account creation. Existing provider identities can still sign in when this is false.
- Provider names can contain letters, numbers, hyphens and underscores. Provider client secrets are masked from settings representations.

There is no automatic account merge by email. To link an identity, sign in to the account that should own it, choose **Link _provider_**, confirm the action, then complete the provider flow. The callback links the provider subject only to that authenticated account; an identity already linked elsewhere is rejected. An OIDC-only account should retain another sign-in method before changing provider access.

## Authentik setup

Authentik acts as the OpenID Provider (OP); AI Control is the relying party. Use Authentik's default **per-provider issuer** mode. Authentik's global issuer mode serves discovery at an application-specific path that does not match AI Control's generic `issuer_url + /.well-known/openid-configuration` discovery request.

1. Choose an externally reachable HTTPS origin for AI Control, for example `https://control.example.com`. Configure TLS at the reverse proxy and set `AIC_PUBLIC_URL` to that exact origin (no path or trailing slash). Authentik must be able to reach the callback, and the AI Control server must be able to reach Authentik's discovery, token and JWKS endpoints. Avoid interactive proxy/WAF challenges on those Authentik endpoints.
2. In Authentik's Admin interface, go to **Applications → Applications → New Application**. Create an application such as **AI Control** with a stable slug such as `ai-control`.
3. Select **OAuth2/OIDC** as the provider type. Configure a **Confidential** client, use **Authorization Code** (AI Control also sends PKCE S256), and set a strict redirect URI to the exact callback below. Do not enable implicit or password grants.

  ```text
  https://control.example.com/api/auth/oidc/authentik/callback
  ```

  Select an asymmetric RSA signing key (RS256); Authentik needs a signing key so the public key is published in JWKS. Keep the default per-provider issuer. Ensure the provider includes the `openid`, `profile`, and `email` scope mappings. Assign the application to the users/group intended for the manual test.
4. Copy the provider's **Client ID** and **Client Secret** into the protected AI Control deployment environment. Use its exact per-provider issuer, based on the application slug, as `issuer_url`:

  ```text
  https://authentik.example.com/application/o/ai-control/
  ```

  Authentik serves discovery at `https://authentik.example.com/application/o/ai-control/.well-known/openid-configuration`. Verify that the discovery document's `issuer` matches the configured issuer (a trailing slash is normalized by AI Control).
5. Add this provider entry to `AIC_OIDC_PROVIDERS` (replace every example value; never commit the real secret):

  ```json
  [{"name":"authentik","issuer_url":"https://authentik.example.com/application/o/ai-control/","client_id":"AUTHENTIK_CLIENT_ID","client_secret":"LOAD_FROM_SECRET_STORE","scopes":["openid","profile","email"],"auto_create_users":true}]
  ```

  For a local Docker Compose deployment, put the JSON value in the protected `vibing/ai-control/.env` file as `AIC_OIDC_PROVIDERS='[...]'`; keep that file out of git and restrict access to it. Also set `AIC_PUBLIC_URL='https://control.example.com'`. Recreate the container to apply changed environment values (a plain restart does not update its environment): run `docker compose up -d --force-recreate ai-control` from `vibing/ai-control`. Never use `docker compose down -v`; retain the persistent data volume. If `allowed_email_domains` is configured, ensure the selected Authentik email scope mapping asserts `email_verified: true`; otherwise leave the domain allowlist empty for the isolated manual test.
6. From a signed-out browser, choose **Continue with authentik**. Authentik should authenticate the test user and redirect to AI Control, which should establish its normal session. For a new account, AI Control uses the signed `preferred_username` claim (normalized to lowercase) when valid and unused; otherwise it falls back to a stable generated username. Confirm Authentik's `profile` scope mapping emits that claim. If the preferred username is already used by a local account, AI Control returns a conflict and does **not** silently attach the Authentik identity. Sign in to that local account, then use **Link authentik** and confirm. This explicit step prevents a matching, user-controlled username or email from taking over an existing account. If that identity was already attached to a legacy generated account, explicit linking can reclaim it only if it has no password, computers, memberships, shares, tokens, or authored run/script/goal/audit history; the empty shadow account is disabled. Accounts with data/resources are never transferred this way. Verify `/api/auth/me` and repeat login to confirm the same user ID.

Official Authentik references: [Create an OAuth2 provider](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/create-oauth2-provider/) and [OAuth 2.0 provider endpoints, issuer mode, redirect URIs and signing](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/).

**Credential response:** if a client secret has ever been pasted into a shared transcript, committed, or otherwise disclosed, rotate it in Authentik before continuing. Moving a disclosed value into `.env` does not make that old secret safe again.

## Local authentication and administration

The initial `/setup` account is the administrator. Local signup remains controlled by `AIC_ALLOW_SIGNUP`; provider-created accounts receive the normal user role and never become administrators by email claim. Administrators can list users, change user/admin roles and disable accounts from the **Admin** page. A disabled account cannot sign in locally or through OIDC, its server-side sessions/tokens are revoked, and existing browser live sockets revalidate authorization every 15 seconds. The last active administrator cannot be disabled or demoted, and administrators cannot disable or demote their own account.

If no OIDC providers are configured, the login UI shows only local authentication. Do not expose the service over an untrusted network without HTTPS, a strong administrator password and protected provider credentials.
