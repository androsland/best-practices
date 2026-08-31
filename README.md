# Project Practices

`project-practices` is a dual Claude Code and Codex plugin for evidence-backed engineering-practices work. It ships two cooperating skills:

- `project-practices-audit` performs a read-only, whole-project audit and activates only checks supported by the detected stack and product shape.
- `project-practices-curator` analyzes new videos with Moviola, verifies consequential claims, and maintains the versioned practice catalog without promoting raw video claims directly into enforced checks.

## Development

Install the Python test dependency once, then run the single deterministic root check:

```bash
python3 -m pip install pytest==9.0.3
./scripts/validate.sh
```

The root command runs the repository unittests, minimal-CLI pytest suite, virtual-fixture audit smoke test, and catalog validation. SaaS examples are inert `*.fixture` analyzer artifacts: the audit engine maps their logical names only when testing those fixture directories, and this repository never installs or deploys them. The root GitHub workflow runs the same validation command.

External tool and CI provenance is recorded in [docs/supply-chain.md](docs/supply-chain.md).

Claude Code can load the repository during development with `claude --plugin-dir .`. Codex validates the same shared skills through `.codex-plugin/plugin.json`.

The audit never edits the target project. Curator media belongs in a temporary directory and must be deleted after extraction; only knowledge, provenance, and ingestion state are retained.

Direct video analysis requires an installed Moviola skill. Live Instagram-profile enumeration additionally requires `gallery-dl` on `PATH`. Check it with `python3 skills/project-practices-curator/scripts/collect_instagram.py --check-dependencies`; when missing, the curator offers detected installation options and waits for explicit approval before running one. The collector can be tested offline with saved enumeration metadata.
