# Mixed SaaS fixture

This is inert negative analyzer data, not an application. Files ending in `.fixture` are never installed, started, built, tested as application code, or deployed. When this directory is passed directly to the audit engine, the marker file makes those artifacts appear under their logical names solely for stack detection and evidence tests.

The virtual package and lockfile remain realistic analyzer inputs. `container-negative-fixture.json` records unsafe container claims as data rather than exposing a runnable Dockerfile.

## Fixture API contracts

- `POST /login` accepts an unspecified JSON body and returns `{ "ok": true }`. Missing validation/authentication and unspecified errors are intentional negative evidence.
- `POST /webhook` accepts an unspecified body and returns `{ "received": true }`. Missing signature verification, idempotency, and a stable error envelope are intentional negative evidence.
- `GET /projects?tenant_id=...` returns a JSON array. Trusting the caller-supplied tenant ID, unbounded results, and unspecified errors are intentional negative evidence.

These routes describe virtual static-analyzer inputs, not supported external APIs.
