# Mixed SaaS fixture

This is a non-production negative audit fixture. It is never started, built, or deployed; its package has no start script, its Express app neither listens nor exports, and root contract tests enforce those boundaries. Unit tests exercise the handler contracts without opening a network listener. The fixture intentionally preserves missing tenant authorization and webhook authenticity/idempotency controls as negative audit evidence. `container-negative-fixture.json` records unsafe container claims as data rather than exposing a runnable Dockerfile.

Dependency versions and the lockfile remain real and reviewable even though application behavior is intentionally incomplete.

## Fixture API contracts

- `POST /login` validates the credential shape and returns stable success, denial, and dependency-failure responses.
- `POST /webhook` validates the event shape and returns stable success/failure responses. Missing signature verification and idempotency remain intentional negative evidence.
- `GET /projects?tenant_id=...&limit=...&cursor=...` returns a bounded `{ "items": [...], "next_cursor": "..." }` page. Trusting the caller-supplied tenant ID remains intentional negative evidence.

These routes describe static analyzer inputs, not supported external APIs.
