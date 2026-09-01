---
name: best-practices-catalog
description: Inspect and account for the accumulated best-practices knowledge catalog. Use when the user asks what knowledge exists, which domains or sources it covers, its maturity and provenance, or whether an audit accounted for every practice; not for analyzing videos or reviewing a repository.
---

# Best Practices Catalog

Resolve `<plugin-root>` from this file at `<plugin-root>/skills/best-practices-catalog/SKILL.md`. The canonical catalog is `<plugin-root>/knowledge/practices.json`.

Use `scripts/catalog_query.py` for deterministic inventory and filtering:

```bash
python3 scripts/catalog_query.py <plugin-root>/knowledge/practices.json summary
python3 scripts/catalog_query.py <plugin-root>/knowledge/practices.json list --domain application-security
python3 scripts/catalog_query.py <plugin-root>/knowledge/practices.json packet --reviewer application-security
```

Report the catalog schema version, content SHA-256, update date, counts by domain and maturity, and the requested practice provenance. Do not interpret repetition as truth or silently promote candidate/advisory knowledge.

For whole-audit coverage validation, compare the unique reported practice IDs with the catalog IDs. Every catalog practice must be present exactly once; unknown, duplicate, and structurally incomplete results are errors. To validate a single reviewer handoff before consolidation, run `coverage <results.json> --reviewer <reviewer-name>` against that reviewer's packet. Coverage accounting does not decide whether the project's conclusion is correct.

Do not modify the catalog. Use `$best-practices-curator` for reviewed catalog changes and `$best-practices-ingest` for new video material.
