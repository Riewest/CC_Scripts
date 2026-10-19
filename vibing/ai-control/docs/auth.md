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

## Local authentication and administration

The initial `/setup` account is the administrator. Local signup remains controlled by `AIC_ALLOW_SIGNUP`; provider-created accounts receive the normal user role and never become administrators by email claim. Administrators can list users, change user/admin roles and disable accounts from the **Admin** page. A disabled account cannot sign in locally or through OIDC, its server-side sessions/tokens are revoked, and existing browser live sockets revalidate authorization every 15 seconds. The last active administrator cannot be disabled or demoted, and administrators cannot disable or demote their own account.

If no OIDC providers are configured, the login UI shows only local authentication. Do not expose the service over an untrusted network without HTTPS, a strong administrator password and protected provider credentials.
