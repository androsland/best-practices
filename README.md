# Project Practices

`project-practices` is a dual Claude Code and Codex plugin for evidence-backed engineering-practices work. It ships two cooperating skills:

- `project-practices-audit` performs a read-only, whole-project audit and activates only checks supported by the detected stack and product shape.
- `project-practices-curator` analyzes new videos with Moviola, verifies consequential claims, and maintains the versioned practice catalog without promoting raw video claims directly into enforced checks.

## Development

Run the deterministic checks from the repository root:

```bash
python3 -m unittest discover -s tests -v
python3 skills/project-practices-audit/scripts/audit_evidence.py fixtures/secure-saas --format json
python3 skills/project-practices-curator/scripts/curation_state.py validate knowledge/practices.json
```

Claude Code can load the repository during development with `claude --plugin-dir .`. Codex validates the same shared skills through `.codex-plugin/plugin.json`.

The audit never edits the target project. Curator media belongs in a temporary directory and must be deleted after extraction; only knowledge, provenance, and ingestion state are retained.

Direct video analysis requires an installed Moviola skill. Live Instagram-profile enumeration additionally requires `gallery-dl` on `PATH`. Check it with `python3 skills/project-practices-curator/scripts/collect_instagram.py --check-dependencies`; when missing, the curator offers detected installation options and waits for explicit approval before running one. The collector can be tested offline with saved enumeration metadata.
