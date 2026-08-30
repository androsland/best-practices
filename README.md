# Project Practices

`project-practices` is a dual Claude Code and Codex plugin for evidence-backed engineering-practices work. It ships two cooperating skills:

- `project-practices-audit` performs a read-only, whole-project audit and activates only checks supported by the detected stack and product shape.
- `project-practices-curator` analyzes new videos with Moviola, verifies consequential claims, and maintains the versioned practice catalog without promoting raw video claims directly into enforced checks.

## Development

Install the fixture test dependencies once, then run the single deterministic root check:

```bash
python3 -m pip install pytest==9.0.3
npm --prefix fixtures/secure-saas ci
./scripts/validate.sh
```

The root command runs the repository unittests, minimal-CLI pytest suite, secure-SaaS Vitest and TypeScript checks, an audit smoke test, and catalog validation. The root GitHub workflow runs the same command. The nested secure-SaaS workflow is a pinned standalone-fixture template; the root workflow is what validates it in this repository.

External tool and CI provenance is recorded in [docs/supply-chain.md](docs/supply-chain.md).

Claude Code can load the repository during development with `claude --plugin-dir .`. Codex validates the same shared skills through `.codex-plugin/plugin.json`.

The audit never edits the target project. Curator media belongs in a temporary directory and must be deleted after extraction; only knowledge, provenance, and ingestion state are retained.

Direct video analysis requires an installed Moviola skill. Live Instagram-profile enumeration additionally requires `gallery-dl` on `PATH`. Check it with `python3 skills/project-practices-curator/scripts/collect_instagram.py --check-dependencies`; when missing, the curator offers detected installation options and waits for explicit approval before running one. The collector can be tested offline with saved enumeration metadata.
