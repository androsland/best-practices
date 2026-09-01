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

The audit is not a filename-compliance scanner. Its deterministic tools only inventory candidate evidence and catalog coverage. Before repository content reaches a mapper or reviewer, the operator discloses the provider/model and known or unknown retention/training posture, obtains invocation-specific confirmation, excludes credentials and sensitive records, and creates a minimum-necessary evidence allowlist. Specialist reviewers inspect actual project flows within that scope and assign evidence-backed outcomes for all catalog practices. The report foregrounds observed gaps and observed alignment; unverifiable and non-applicable practices remain explicit coverage accounting. It never writes a Forgeward marker or ships code.

## Installation

Only install plugins from sources you trust. A normal installation does not require cloning this
repository.

### Codex

Add the GitHub marketplace and install the plugin directly:

```bash
codex plugin marketplace add androsland/best-practices
codex plugin add best-practices@best-practices
```

Start a new Codex session so the bundled skills become available, then invoke a workflow explicitly,
for example `$best-practices-audit`. You can also browse, install, enable, or remove plugins
interactively with `/plugins`.

Codex plugins are supported in Codex CLI and Codex in the ChatGPT desktop app, but not
in the Codex IDE extension. See the official OpenAI documentation for
[using plugins](https://learn.chatgpt.com/docs/plugins) and
[building plugins](https://learn.chatgpt.com/docs/build-plugins).

### Claude Code

Add the same GitHub marketplace and install the plugin directly:

```bash
claude plugin marketplace add androsland/best-practices
claude plugin install best-practices@best-practices
```

Start a new Claude Code session, then invoke a workflow explicitly, for example
`/best-practices:best-practices-audit`. See Anthropic's documentation for
[discovering and installing plugins](https://code.claude.com/docs/en/discover-plugins).

### Local development

Clone the repository only when developing or testing local changes:

```bash
git clone https://github.com/androsland/best-practices.git
cd best-practices
```

Load the clone for one Claude Code session:

```bash
claude --plugin-dir /absolute/path/to/best-practices
```

For Codex, register the clone as a local marketplace and install from it:

```bash
codex plugin marketplace add /absolute/path/to/best-practices
codex plugin add best-practices@best-practices
```

## Development

Install the Python test dependency once, then run the single root check:

```bash
python3 -m pip install pytest==9.0.3
./scripts/validate.sh
```

Codex and Claude Code discover the same shared skills through their respective plugin manifests.

Direct media understanding remains Moviola's responsibility. Live Instagram enumeration additionally uses a reviewed, pinned `gallery-dl` version after explicit installation and cookie-consent boundaries. Source media and transcripts stay temporary; only normalized knowledge, provenance, and ingestion state are durable.

The installed plugin is a versioned artifact, not the writable canonical knowledge store. Add and curate knowledge in this source repository, commit it, validate it, then reinstall or release the plugin. Every audit records the plugin version and catalog SHA-256 so results remain reproducible as knowledge evolves.
