# Best Practices

`best-practices` is the evolving knowledge-and-review layer in a three-plugin workflow:

```text
Moviola observes → Best Practices learns and evaluates → Forgeward enforces
```

It is a dual Claude Code and Codex plugin with four cooperating skills:

- `best-practices-ingest` uses Moviola output to create provenance-preserving candidate knowledge.
- `best-practices-curator` reviews, reconciles, revises, merges, and promotes existing knowledge.
- `best-practices-catalog` reports catalog contents, maturity, provenance, hashes, and audit coverage.
- `best-practices-audit` maps a whole repository, conditionally launches contextual specialist agents, verifies their conclusions, and reports where the project aligns or diverges.

The audit is not a filename-compliance scanner. Its deterministic tools only inventory candidate evidence and catalog coverage. Specialist reviewers inspect actual project flows and assign evidence-backed outcomes for all catalog practices. The report foregrounds observed gaps and observed alignment; unverifiable and non-applicable practices remain explicit coverage accounting. It never writes a Forgeward marker or ships code.

## Development

Install the Python test dependency once, then run the single root check:

```bash
python3 -m pip install pytest==9.0.3
./scripts/validate.sh
```

Claude Code can load the repository during development with `claude --plugin-dir .`. Codex validates the same shared skills through `.codex-plugin/plugin.json`.

Direct media understanding remains Moviola's responsibility. Live Instagram enumeration additionally uses a reviewed, pinned `gallery-dl` version after explicit installation and cookie-consent boundaries. Source media and transcripts stay temporary; only normalized knowledge, provenance, and ingestion state are durable.

The installed plugin is a versioned artifact, not the writable canonical knowledge store. Add and curate knowledge in this source repository, commit it, validate it, then reinstall or release the plugin. Every audit records the plugin version and catalog SHA-256 so results remain reproducible as knowledge evolves.
