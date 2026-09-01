#!/usr/bin/env python3
"""Build a bounded repository inventory without assigning practice outcomes."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path


EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", ".next", ".nuxt", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".venv", "venv", "node_modules", "dist", "build",
    "coverage", "target", "vendor", "__pycache__", ".temp",
}
TEXT_SUFFIXES = {
    ".c", ".cc", ".conf", ".cpp", ".cs", ".css", ".env", ".go", ".graphql",
    ".h", ".html", ".java", ".js", ".json", ".jsx", ".kt", ".kts", ".md",
    ".mjs", ".php", ".properties", ".py", ".rb", ".rs", ".scss", ".sh",
    ".sql", ".svelte", ".swift", ".tf", ".toml", ".ts", ".tsx", ".txt",
    ".vue", ".xml", ".yaml", ".yml",
}
MANIFEST_NAMES = {
    "package.json", "pyproject.toml", "requirements.txt", "Pipfile", "go.mod",
    "Cargo.toml", "Gemfile", "composer.json", "pom.xml", "build.gradle",
    "build.gradle.kts", "Package.swift", "Dockerfile", "docker-compose.yml",
    "docker-compose.yaml", "vercel.json", "netlify.toml", "config.toml",
}
LOCK_NAMES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb",
    "uv.lock", "poetry.lock", "Pipfile.lock", "go.sum", "Cargo.lock",
    "Gemfile.lock", "composer.lock", "packages.lock.json",
}
CODE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cs", ".go", ".java", ".js", ".jsx", ".kt",
    ".kts", ".mjs", ".php", ".py", ".rb", ".rs", ".sql", ".svelte",
    ".swift", ".ts", ".tsx", ".vue",
}


def classify_path(rel: str, suffix: str) -> list[str]:
    lower = rel.lower()
    labels: list[str] = []
    if suffix in CODE_SUFFIXES:
        labels.append("code")
    if any(part in lower for part in ("test", "spec", "__tests__", "pg_tap")):
        labels.append("tests")
    if "migration" in lower or suffix == ".sql":
        labels.append("data-schema")
    if lower.startswith(".github/workflows/") or any(token in lower for token in ("dockerfile", "terraform/", "infra/", "k8s/", "deploy")):
        labels.append("delivery-infrastructure")
    if any(token in lower for token in ("auth", "session", "policy", "permission", "rls")):
        labels.append("identity-access-candidate")
    if any(token in lower for token in ("route", "api/", "controller", "handler", "actions.")):
        labels.append("request-boundary-candidate")
    if any(token in lower for token in ("worker", "queue", "job", "cron")):
        labels.append("background-work-candidate")
    if any(token in lower for token in ("openai", "anthropic", "prompt", "eval", ".mcp", "skill.md", "claude.md", "agents.md")):
        labels.append("ai-agent-candidate")
    if any(token in lower for token in ("onboarding", "signup", "analytics", "billing", "checkout")):
        labels.append("product-flow-candidate")
    return labels


def collect(root: Path, max_file_bytes: int, max_total_bytes: int) -> dict:
    files: list[dict] = []
    skipped: list[dict] = []
    total_text_bytes = 0
    discovered = 0
    category_counts: Counter[str] = Counter()
    extension_counts: Counter[str] = Counter()

    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
        base = Path(current)
        for name in sorted(names):
            path = base / name
            if not path.is_file() or path.is_symlink():
                continue
            discovered += 1
            rel = path.relative_to(root).as_posix()
            suffix = path.suffix.lower()
            if suffix not in TEXT_SUFFIXES and name not in MANIFEST_NAMES and name not in LOCK_NAMES:
                continue
            try:
                size = path.stat().st_size
            except OSError as exc:
                skipped.append({"path": rel, "reason": f"stat-error:{type(exc).__name__}"})
                continue
            if size > max_file_bytes:
                skipped.append({"path": rel, "reason": "file-byte-limit", "bytes": size})
                continue
            if total_text_bytes + size > max_total_bytes:
                skipped.append({"path": rel, "reason": "total-byte-limit", "bytes": size})
                continue
            total_text_bytes += size
            categories = classify_path(rel, suffix)
            category_counts.update(categories)
            extension_counts.update([suffix or "<none>"])
            files.append({
                "path": rel,
                "bytes": size,
                "categories": categories,
                "manifest": name in MANIFEST_NAMES,
                "lockfile": name in LOCK_NAMES,
            })

    return {
        "schema_version": 1,
        "target": str(root),
        "purpose": "candidate repository inventory; no applicability or adherence conclusions",
        "budget": {
            "discovered_files": discovered,
            "candidate_files": len(files),
            "candidate_text_bytes": total_text_bytes,
            "max_file_bytes": max_file_bytes,
            "max_total_bytes": max_total_bytes,
            "skipped_files": len(skipped),
        },
        "category_counts": dict(sorted(category_counts.items())),
        "extension_counts": dict(sorted(extension_counts.items())),
        "manifests": [item["path"] for item in files if item["manifest"]],
        "lockfiles": [item["path"] for item in files if item["lockfile"]],
        "candidate_files": files,
        "skipped": skipped,
        "outcomes": None,
        "verdict": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--format", choices=("json",), default="json")
    parser.add_argument("--max-file-bytes", type=int, default=1_000_000)
    parser.add_argument("--max-total-bytes", type=int, default=25_000_000)
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    if args.max_file_bytes <= 0 or args.max_total_bytes <= 0:
        parser.error("byte limits must be positive")
    print(json.dumps(collect(root, args.max_file_bytes, args.max_total_bytes), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
