# Application security rubric

| ID | Criterion | Applicability | Key evidence | Default severity |
|---|---|---|---|---|
| `SEC-AUTHZ-001` | Protected operations enforce server/data-layer authorization, including object scope. | Authenticated APIs/apps. | Route/policy code and negative cross-user tests. Client-only role checks are `MISSING`; inconsistent server coverage is `PARTIAL`. | CRITICAL |
| `SEC-SESS-001` | Browser/mobile sessions avoid script-readable or embedded long-lived secrets. | Browser/mobile auth. | Cookie attributes, BFF/session setup, Keychain/Keystore integration. Runtime cookie flags may be `NOT_VERIFIABLE`. | HIGH |
| `SEC-AUTHN-001` | Sensitive auth/recovery endpoints have server-side abuse controls and safe recovery behavior. | Apps with login/signup/reset. | Rate-limit middleware/config and auth tests. Edge-only unknowns are `NOT_VERIFIABLE`, not assumed. | HIGH |
| `SEC-RLS-001` | Exposed Supabase tables use tested RLS/grants; elevated keys stay server-side. | Supabase/PostgREST exposed schema. | Migrations, policies, grants, role tests, environment-variable use. Never print key values. | CRITICAL |
| `SEC-WEBHOOK-001` | Webhooks verify authentic raw-body signatures before effects and are retry/idempotency safe. | Webhook handlers. | Handler ordering, official verification API, event ledger/unique key/transaction, tests. | CRITICAL |
| `SEC-API-001` | Public APIs have authentication where needed, object authorization, validation, bounded resources, and abuse controls. | Network APIs. | Middleware/schema/route tests. Do not require universal HMAC for browser/mobile clients. | HIGH |
| `SEC-EDGE-001` | Origin exposure and edge controls follow the deployed threat model. | Public production services. | IaC/provider config; otherwise `NOT_VERIFIABLE`. WAF absence alone is not automatically a failure. | MEDIUM |
| `SEC-MOBILE-001` | Native wrappers use platform storage, safe deep links, and OAuth PKCE where applicable. | Native/hybrid mobile apps. | Entitlements/manifests/auth code. Do not require blanket certificate pinning. | HIGH |
| `SEC-SECRETS-001` | No committed credential material; examples use placeholders and server-side secret injection. | All projects. | Repository search, ignore rules, CI secret references. Redact matches. | CRITICAL |

Do not run invasive scanners or access live services. Promotional security products, popularity, and “install this stack” claims are advisory only.

Primary provenance: OWASP Session/Authentication guidance, Supabase RLS/API-key docs, Stripe webhooks, RFC 9421/8252, Android network security, NIST SP 800-207; videos S01, S07, S11, S18, S19, S21, S24.
