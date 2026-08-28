# Application security best practices

This is the highest-priority synthesis in the collection. It preserves useful warnings from the videos while correcting advice that was too broad.

## Launch checklist

### 1. Keep trust decisions on the server

- Enforce authorization for every protected operation on the server or at the data layer. A client-side `isAdmin` check is presentation logic, not a security boundary (`S18 00:22–00:26`).
- Apply least privilege to users, services, database roles, and API keys.
- Treat role-based access as a baseline. Add context-aware policy only where risk and operational maturity justify it.

### 2. Protect sessions and credentials

- Do not put session identifiers, refresh tokens, or credentials in browser `localStorage`; JavaScript can read them after an XSS compromise. OWASP recommends secure `HttpOnly` cookies or a backend-for-frontend pattern for browser sessions ([OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)).
- For native apps, store small secrets in [Apple Keychain](https://developer.apple.com/documentation/security/keychain-services/) or use keys protected by the [Android Keystore](https://developer.android.com/privacy-and-security/keystore) (`S21 00:34–01:00`). Do not embed service credentials in a mobile binary; a client app cannot keep a shared backend secret.
- Rotate exposed credentials and investigate how exposure occurred.

### 3. Harden authentication flows

- Offer MFA or passkeys, particularly for privileged or high-risk accounts.
- Throttle login, registration, and password-reset operations. Count by more than IP where possible: account, session, device signal, or risk score can reduce distributed attacks and collateral lockouts.
- Block common and breached passwords and enforce password requirements on the server, not only in client-side form validation.
- Avoid user-enumeration leaks and secure account recovery with the same care as login.

These points refine S18 (`00:16–00:50`) and align with [OWASP Authentication guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html).

### 4. Configure Supabase authorization deliberately

- Enable RLS on every table in an exposed schema.
- Review both grants and policies; a policy does not revoke an overly broad table grant.
- Test that `anon`/publishable and authenticated roles can access only intended rows and operations.
- Keep secret keys and the legacy `service_role` key server-side. They provide elevated access and bypass RLS.
- Review views and functions for privilege behavior, not just tables.

This validates the core warning in S24 (`00:21–01:08`) while incorporating current [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security) and [API-key](https://supabase.com/docs/guides/getting-started/api-keys) guidance.

### 5. Make webhook handlers authentic, replay-safe, and retry-safe

For Stripe (`S01 00:46–02:15`):

1. Verify the `Stripe-Signature` over the unmodified raw request body using the endpoint secret and an official library.
2. Reject invalid or stale signatures before producing side effects.
3. Record processed event IDs or use an equivalent idempotency boundary so duplicate delivery does not duplicate fulfillment.
4. Do not assume event order; retrieve current resource state when correctness depends on it.
5. Return quickly and process expensive work asynchronously when appropriate.
6. Use Stripe’s published webhook IP list only as defense in depth, and keep it updated.

Stripe explicitly documents [signature verification and delivery behavior](https://docs.stripe.com/webhooks) and publishes [webhook IP ranges](https://docs.stripe.com/ips). A secret-looking webhook URL is not an authentication control; assume the route can be discovered.

### 6. Secure APIs according to the client model

- Use TLS, strong authentication, object-level authorization, input validation, resource limits, logging, and abuse controls on every API.
- For browser/mobile first-party APIs, “HMAC on every mutation” is usually not viable because the client cannot safely hold a shared signing secret.
- For trusted server-to-server clients, message signing can add origin and integrity assurance. Include sufficient request components plus a creation time, expiry, and nonce to resist replay; [RFC 9421](https://datatracker.ietf.org/doc/html/rfc9421) defines a standard HTTP message-signature model.
- Version breaking contracts deliberately. Communicate retirement dates and usage; the [`Sunset` header](https://www.rfc-editor.org/info/rfc8594/) is one standardized signal (`S19 01:02–01:55`).

### 7. Use edge controls without abandoning application defenses

S07 recommends edge rate limits, bot management, and WAF rules (`00:36–01:58`). Use them, but retain origin protections:

- Rate-limit authentication and expensive routes at both the edge and application boundary.
- Tune thresholds from real traffic; start with challenge or observation where false positives matter.
- Prefer maintained managed rules, supplemented by narrow custom rules for application-specific patterns.
- Protect the origin so attackers cannot bypass the edge directly.
- Monitor rule matches, blocked traffic, origin load, and account-takeover signals.

Cloudflare documents [rate-limiting behavior and limits](https://developers.cloudflare.com/waf/rate-limiting-rules/) and recommends combining rate limiting with bot signals where available ([best practices](https://developers.cloudflare.com/waf/rate-limiting-rules/best-practices/)).

### 8. Treat mobile wrappers as native security surfaces

S21 correctly warns that wrapping a web app does not make client-side data secret. Refine its prescriptions as follows:

- Use platform secure storage for tokens or key material, while keeping backend service secrets off-device.
- Use system TLS validation. Do not apply certificate pinning indiscriminately: Android’s security guidance says pinning is not recommended for Android apps because certificate/CA changes can strand clients. If risk justifies pinning, ship backup pins and a rotation plan ([Android network security](https://developer.android.com/privacy-and-security/security-ssl)).
- Prefer claimed HTTPS app/universal links over private URI schemes when possible.
- For OAuth native-app flows, validate redirects and `state`, and use authorization code flow with PKCE. [RFC 8252](https://datatracker.ietf.org/doc/html/rfc8252) requires PKCE for public native clients and explains redirect interception risks.

### 9. Add risk-aware access where the threat warrants it

S11 proposes attributes such as device, location, time, IP reputation, resource sensitivity, and behavior (`00:25–02:01`). A mature implementation can:

- Re-evaluate authorization for sensitive resources and operations.
- Step up authentication when risk changes.
- Detect impossible travel, unusual access volume, or privilege-escalation behavior.
- Authenticate and authorize service identities, not merely trust an internal network.

This matches the principle—not every implementation detail—of [NIST SP 800-207](https://www.nist.gov/publications/zero-trust-architecture): network location alone must not create implicit trust. Apply privacy controls, false-positive handling, appeal/recovery paths, and measured rollout.

### 10. Establish a VPS security baseline

Before exposing a new server (`S03 00:29–02:05`):

- Create a non-root administrative account and use least privilege.
- Verify key-based SSH access in a second session before disabling passwords or root login.
- Validate SSH configuration before reload; changing port 22 reduces log noise but is not a meaningful substitute for strong authentication.
- Apply a default-deny firewall and expose only required ports. Confirm remote access before enabling it.
- Keep databases and internal services off the public Internet unless explicitly required and protected.
- Apply security updates with a tested maintenance/reboot strategy.
- Add monitoring, backups, secret management, and an incident-response path.

See Ubuntu’s primary guidance for [OpenSSH](https://ubuntu.com/server/docs/how-to/security/openssh-server/), [UFW](https://ubuntu.com/server/docs/security-firewall/), and [automatic updates](https://ubuntu.com/server/docs/how-to/software/automatic-updates/).

## Important corrections to reel-sized advice

| Video claim | Safer interpretation |
|---|---|
| “HMAC every POST/PUT/PATCH/DELETE.” | Appropriate for trusted clients that can protect signing keys; not a universal browser/mobile pattern. Always add replay protection. |
| “Certificate pinning on every API call.” | Use only after threat analysis and with rotation/backup pins; Android explicitly discourages blanket pinning. |
| “Use an unguessable webhook URL.” | Fine as minor defense in depth, never a replacement for signature verification. |
| “Rate-limit by IP.” | IP is one signal; distributed attacks and shared NATs require account/session/device-aware controls. |
| “Change the SSH port to stop attacks.” | It mainly reduces commodity scanning noise. Keys, least privilege, firewalling, patching, and monitoring provide the security. |
| “Two-factor means nobody can sign up as anybody.” | MFA helps account takeover; identity proofing and verified recovery channels address impersonation. |

## Source synthesis

S01, S03, S07, S11, S18, S19, S21, S24.
