# Stack and applicability detection

Use deterministic output as an index, then confirm important signals in source/configuration.

## Signals

- JavaScript/TypeScript: `package.json`, lockfiles, `tsconfig.json`; distinguish Next.js, React, Express/Fastify/Nest, test and migration tools from dependencies and scripts.
- Python: `pyproject.toml`, requirements/lock files; distinguish Django, Flask, FastAPI, Celery, Alembic, pytest.
- Go/Rust/Java/.NET/Ruby/PHP: language manifests plus source extensions and framework configuration.
- Data: ORM/migration directories, SQL, PostgreSQL/Supabase clients, backup/IaC configuration.
- Infrastructure/deployment: Dockerfiles, Compose, Kubernetes, Terraform/OpenTofu, Pulumi, cloud/platform manifests, CI deployment workflows.
- Product UI/onboarding: web/mobile application frameworks, signup/onboarding routes, analytics/experiment/notification dependencies.
- AI use: model SDKs, MCP configuration, agent/skill instructions, prompt/eval directories, AI CI workflows.
- Multitenancy: tenant/workspace/organization identifiers in schema, access policy, request context, or product routes. A generic `organization` word is not enough by itself.

## Activation rules

- Always assess coding/AI-agent workflow and AI usage, but individual checks may be `NOT_APPLICABLE`.
- Activate application security for any service, web/mobile application, auth integration, webhook, public API, or infrastructure exposing a network surface.
- Activate data reliability when durable application data, a database, queue, object store, or stateful infrastructure is present.
- Activate multitenancy only after at least one direct data/request-model signal; otherwise mark its checks `NOT_APPLICABLE`, not `MISSING`.
- Activate infrastructure/deployment when deployment artifacts exist. If production is claimed but provider config is outside the repo, use `NOT_VERIFIABLE` for runtime controls.
- Activate product onboarding when the repository contains an end-user product/signup experience. Libraries, CLIs, internal tools, and infrastructure repositories are normally non-applicable.

Do not equate a dependency with a configured control or an example/template with production behavior.
