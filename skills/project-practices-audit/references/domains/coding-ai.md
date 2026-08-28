# Coding and AI-agent workflow rubric

| ID | Criterion | Applicability | Typical status rule | Default severity |
|---|---|---|---|---|
| `DEV-SCOPE-001` | Project instructions define scope, verification, and consequential-action boundaries. | Projects using AI-agent instructions. | `PASS` for clear checked-in guidance; `PARTIAL` if vague or missing boundaries; `NOT_APPLICABLE` without agent files. | MEDIUM |
| `DEV-TEST-001` | Relevant automated tests and a runnable test command exist. | Code projects. | `PASS` with tests plus manifest/CI command; `PARTIAL` with only one; `MISSING` when neither exists in a nontrivial codebase. | HIGH |
| `DEV-CI-001` | CI runs applicable validation on changes. | Maintained code projects intended for collaboration/release. | `PASS` when workflow invokes tests/lint/type/build; `PARTIAL` for incomplete checks; `NOT_VERIFIABLE` if CI lives externally. | MEDIUM |
| `DEV-DEPS-001` | Dependency versions are reproducible through a lockfile/checksum. | Projects with external package dependencies. | `PASS` with ecosystem lock/checksum; `MISSING` when a dependency manifest exists without one; `NOT_APPLICABLE` without dependencies. | MEDIUM |
| `DEV-STATE-001` | Long-running agent work has concise state/acceptance criteria. | Only when repository evidence shows persistent agent orchestration. | Usually `NOT_VERIFIABLE`; never fail merely because a suggested state filename is absent. | LOW |

Inspect actual commands and workflow steps. A test folder containing placeholders is not a pass. Prefer the smallest sufficient design and flag unrelated/generated bulk only when the evidence is direct; style preferences are advisory.

Provenance: S04, S10, S22, S26; `practice.coding.surgical-changes`, `practice.coding.verify-done`.
