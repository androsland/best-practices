#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python3 -m unittest discover -s tests -v
python3 -m pytest fixtures/minimal-cli/tests
python3 skills/project-practices-audit/scripts/audit_evidence.py fixtures/secure-saas --format json >/dev/null
python3 skills/project-practices-curator/scripts/curation_state.py validate knowledge/practices.json
