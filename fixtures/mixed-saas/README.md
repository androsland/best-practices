# Mixed SaaS fixture

This is a non-production negative audit fixture. It is never started, built, or deployed; its incomplete handlers intentionally exercise missing authentication, tenant authorization, webhook verification, and test evidence. `container-negative-fixture.json` records unsafe container claims as data rather than exposing a runnable Dockerfile.

Dependency versions and the lockfile remain real and reviewable even though application behavior is intentionally incomplete.

## Fixture API contracts

- `POST /login` accepts an unspecified JSON body and returns `{ "ok": true }`. Missing validation/authentication and unspecified errors are intentional negative evidence.
- `POST /webhook` accepts an unspecified body and returns `{ "received": true }`. Missing signature verification, idempotency, and a stable error envelope are intentional negative evidence.
- `GET /projects?tenant_id=...` returns a JSON array. Trusting the caller-supplied tenant ID, unbounded results, and unspecified errors are intentional negative evidence.

These routes describe static analyzer inputs, not supported external APIs.
