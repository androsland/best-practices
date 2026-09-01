#!/usr/bin/env python3
"""Query the versioned practice catalog and produce reviewer knowledge packets."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


REVIEWER_DOMAINS = {
    "application-security": {"application-security", "multitenancy"},
    "reliability": {"data-reliability", "database-performance"},
    "infrastructure": {"infrastructure-deployment"},
    "engineering": {"coding-ai", "coding-workflow", "api-design"},
    "ai": {"ai-engineering", "ai-usage"},
    "product": {
        "product-analytics", "product-architecture", "product-learning",
        "product-marketing", "product-onboarding", "product-strategy", "promotional",
    },
    "governance": {"governance"},
}
OUTCOMES = {"ALIGNED", "GAP", "PARTIAL", "UNVERIFIED", "NOT_APPLICABLE"}
PRIORITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
CONFIDENCES = {"HIGH", "MEDIUM", "LOW"}
REQUIRED_STRING_FIELDS = {
    "practice_id", "title", "domain", "knowledge_state", "outcome", "priority",
    "confidence", "applicable_scope", "project_behavior", "reasoning", "coverage",
    "remediation",
}
REQUIRED_LIST_FIELDS = {"evidence_paths", "source_video_ids", "authoritative_urls"}


def load(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    data = json.loads(raw)
    practices = data.get("practices")
    if not isinstance(practices, list):
        raise ValueError("catalog.practices must be an array")
    ids = [item.get("id") for item in practices]
    if any(not isinstance(item, str) for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("catalog practice IDs must be unique strings")
    return data, hashlib.sha256(raw).hexdigest()


def compact(practice: dict) -> dict:
    return {
        key: practice.get(key)
        for key in (
            "id", "domain", "title", "statement", "enforcement_state", "applicability",
            "confidence", "source_video_ids", "authoritative_references", "verification_date",
            "revisions",
        )
    }


def coverage_items(document: object) -> list[dict]:
    if isinstance(document, list):
        return [item for item in document if isinstance(item, dict)]
    if not isinstance(document, dict):
        raise ValueError("results must be an object or array")
    direct = document.get("practice_results")
    if isinstance(direct, list):
        return [item for item in direct if isinstance(item, dict)]
    reviewers = document.get("reviewers")
    if isinstance(reviewers, list):
        items: list[dict] = []
        for reviewer in reviewers:
            items.extend(coverage_items(reviewer))
        return items
    raise ValueError("results must contain practice_results or reviewers")


def complete_result(item: dict) -> bool:
    if any(not isinstance(item.get(field), str) or not item[field].strip()
           for field in REQUIRED_STRING_FIELDS):
        return False
    if any(not isinstance(item.get(field), list) for field in REQUIRED_LIST_FIELDS):
        return False
    return item["outcome"] in OUTCOMES and item["priority"] in PRIORITIES \
        and item["confidence"] in CONFIDENCES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("summary")
    listing = subs.add_parser("list")
    listing.add_argument("--domain", action="append", default=[])
    listing.add_argument("--state", action="append", default=[])
    packet = subs.add_parser("packet")
    packet.add_argument("--reviewer", choices=sorted(REVIEWER_DOMAINS), required=True)
    coverage = subs.add_parser("coverage")
    coverage.add_argument("results", type=Path)
    coverage.add_argument("--reviewer", choices=sorted(REVIEWER_DOMAINS))
    args = parser.parse_args()
    try:
        data, digest = load(args.catalog)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    practices = data["practices"]
    base = {
        "schema_version": data.get("schema_version"),
        "updated_at": data.get("updated_at"),
        "catalog_sha256": digest,
        "practice_count": len(practices),
    }
    exit_code = 0
    if args.command == "summary":
        base.update({
            "domains": dict(sorted(Counter(item["domain"] for item in practices).items())),
            "knowledge_states": dict(sorted(Counter(item["enforcement_state"] for item in practices).items())),
            "reviewer_packets": {
                reviewer: sum(item["domain"] in domains for item in practices)
                for reviewer, domains in REVIEWER_DOMAINS.items()
            },
        })
    elif args.command == "list":
        selected = [
            compact(item) for item in practices
            if (not args.domain or item["domain"] in args.domain)
            and (not args.state or item["enforcement_state"] in args.state)
        ]
        base.update({"filters": {"domains": args.domain, "states": args.state}, "practices": selected})
    elif args.command == "packet":
        domains = REVIEWER_DOMAINS[args.reviewer]
        selected = [compact(item) for item in practices if item["domain"] in domains]
        base.update({"reviewer": args.reviewer, "domains": sorted(domains), "practices": selected})
    else:
        try:
            items = coverage_items(json.loads(args.results.read_text()))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        expected_practices = practices
        if args.reviewer:
            domains = REVIEWER_DOMAINS[args.reviewer]
            expected_practices = [item for item in practices if item["domain"] in domains]
        expected = {item["id"] for item in expected_practices}
        ids = [item.get("practice_id") for item in items]
        counts = Counter(item for item in ids if isinstance(item, str))
        duplicates = sorted(item for item, count in counts.items() if count > 1)
        unknown = sorted(set(counts) - expected)
        missing = sorted(expected - set(counts))
        invalid_outcomes = sorted({
            str(item.get("practice_id")) for item in items
            if item.get("outcome") not in OUTCOMES
        })
        invalid_results = sorted({
            str(item.get("practice_id")) for item in items if not complete_result(item)
        })
        complete = not (duplicates or unknown or missing or invalid_outcomes or invalid_results) \
            and len(items) == len(expected)
        base.update({
            "coverage_scope": args.reviewer or "catalog",
            "expected_results": len(expected),
            "complete": complete,
            "reported_results": len(items),
            "missing_practice_ids": missing,
            "duplicate_practice_ids": duplicates,
            "unknown_practice_ids": unknown,
            "invalid_outcome_practice_ids": invalid_outcomes,
            "invalid_result_practice_ids": invalid_results,
            "outcomes": dict(sorted(Counter(str(item.get("outcome")) for item in items).items())),
        })
        exit_code = 0 if complete else 3
    print(json.dumps(base, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
