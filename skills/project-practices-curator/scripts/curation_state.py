#!/usr/bin/env python3
"""Validate and update project-practices provenance and ingestion state."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Sequence


PRACTICE_ID = re.compile(r"^practice\.[a-z0-9.-]+$")
CLASSIFICATIONS = {"new", "supporting", "conflicting", "obsolete", "promotional"}
CONSEQUENTIAL_DOMAINS = frozenset({
    "application-security",
    "data-reliability",
    "infrastructure-deployment",
})


def today() -> str:
    return dt.date.today().isoformat()


def iso_date(value: str) -> str:
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected ISO date YYYY-MM-DD") from exc


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def parse_reference(value: str) -> dict:
    parts = value.split("|", 2)
    if len(parts) != 3 or not parts[1].startswith("https://"):
        raise argparse.ArgumentTypeError("reference must be TITLE|https://URL|SUPPORTED PROPOSITION")
    return {"title": parts[0], "url": parts[1], "supports": parts[2]}


def validate_catalog(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    practices = data.get("practices")
    if not isinstance(practices, list):
        return errors + ["practices must be an array"]
    seen: set[str] = set()
    required = {"id", "domain", "title", "statement", "enforcement_state", "applicability", "confidence", "source_video_ids", "authoritative_references", "verification_date", "revisions"}
    for index, practice in enumerate(practices):
        label = f"practices[{index}]"
        if not isinstance(practice, dict):
            errors.append(f"{label} must be an object")
            continue
        missing = sorted(required - set(practice))
        if missing:
            errors.append(f"{label} missing: {', '.join(missing)}")
        pid = practice.get("id")
        if not isinstance(pid, str) or not PRACTICE_ID.fullmatch(pid):
            errors.append(f"{label}.id is invalid")
        elif pid in seen:
            errors.append(f"duplicate practice id: {pid}")
        else:
            seen.add(pid)
        if practice.get("enforcement_state") not in {"candidate", "advisory", "enforceable"}:
            errors.append(f"{label}.enforcement_state is invalid")
        if practice.get("confidence") not in {"HIGH", "MEDIUM", "LOW"}:
            errors.append(f"{label}.confidence is invalid")
        if not isinstance(practice.get("revisions"), list) or not practice.get("revisions"):
            errors.append(f"{label}.revisions must be a non-empty array")
        refs = practice.get("authoritative_references", [])
        if not isinstance(refs, list) or any(not isinstance(ref, dict) or not str(ref.get("url", "")).startswith("https://") for ref in refs):
            errors.append(f"{label}.authoritative_references is invalid")
        if practice.get("enforcement_state") == "enforceable" and practice.get("domain") in CONSEQUENTIAL_DOMAINS:
            if not refs or not practice.get("verification_date"):
                errors.append(f"{label} is consequential/enforceable but lacks current authoritative verification")
    return errors


def command_validate(args: argparse.Namespace) -> int:
    data = read_json(args.catalog)
    errors = validate_catalog(data)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"valid catalog: {len(data['practices'])} practices")
    return 0


def command_init_state(args: argparse.Namespace) -> int:
    if args.state.exists() and not args.force:
        print(f"error: state already exists: {args.state}", file=sys.stderr)
        return 2
    atomic_write(args.state, {"schema_version": 1, "updated_at": today(), "processed_sources": {}})
    print(f"initialized state: {args.state}")
    return 0


def command_record_source(args: argparse.Namespace) -> int:
    data = read_json(args.state) if args.state.exists() else {"schema_version": 1, "updated_at": today(), "processed_sources": {}}
    records = data.setdefault("processed_sources", {})
    previous = records.get(args.source_id, {})
    records[args.source_id] = {
        "url": args.url,
        "status": args.status,
        "processed_at": args.processed_at,
        "attempts": int(previous.get("attempts", 0)) + 1,
        "claim_ids": sorted(set(previous.get("claim_ids", [])) | set(args.claim_id)),
        "creator": args.creator,
        "published_date": args.published_date,
        "duration_seconds": args.duration_seconds,
        "evidence_type": args.evidence_type,
    }
    data["updated_at"] = today()
    atomic_write(args.state, data)
    print(f"recorded source: {args.source_id} ({args.status})")
    return 0


def command_source_id(args: argparse.Namespace) -> int:
    digest = hashlib.sha256()
    with args.media.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    print(f"local-sha256:{digest.hexdigest()}")
    return 0


def revision(classification: str, reason: str, source_ids: list[str], references: list[dict], date: str) -> dict:
    return {
        "date": date,
        "change": f"video-claim-{classification}",
        "reason": reason,
        "source_video_ids": sorted(set(source_ids)),
        "authoritative_urls": sorted({ref["url"] for ref in references}),
    }


def command_propose(args: argparse.Namespace) -> int:
    catalog = read_json(args.catalog)
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid before update: " + "; ".join(errors))
    practices = catalog["practices"]
    existing = next((p for p in practices if p["id"] == args.practice_id), None)
    refs = args.authoritative_ref
    proposal_domain = existing["domain"] if existing else args.domain
    if proposal_domain in CONSEQUENTIAL_DOMAINS and args.classification in {"new", "supporting"}:
        if not refs or not args.verified_on:
            raise ValueError("security, infrastructure, and reliability proposals require --authoritative-ref and --verified-on")
    if args.classification == "promotional" and args.enforcement_state != "advisory":
        raise ValueError("promotional claims must use --enforcement-state advisory")
    new_revision = revision(args.classification, args.reason, args.source_id, refs, args.verified_on or today())
    if existing:
        existing["source_video_ids"] = sorted(set(existing["source_video_ids"] + args.source_id))
        existing["revisions"].append(new_revision)
        # A video proposal never changes an existing enforcement state or statement.
        action = "appended provenance to"
    else:
        if args.classification not in {"new", "promotional"}:
            raise ValueError(f"classification {args.classification} requires an existing practice")
        practice = {
            "id": args.practice_id,
            "domain": args.domain,
            "title": args.title,
            "statement": args.statement,
            "enforcement_state": args.enforcement_state,
            "applicability": {"description": args.applicability, "signals": sorted(set(args.signal))},
            "confidence": args.confidence,
            "source_video_ids": sorted(set(args.source_id)),
            "authoritative_references": refs,
            "verification_date": args.verified_on,
            "revisions": [new_revision],
        }
        practices.append(practice)
        practices.sort(key=lambda item: item["id"])
        action = "created candidate/advisory"
    catalog["updated_at"] = today()
    atomic_write(args.catalog, catalog)
    print(f"{action}: {args.practice_id}")
    return 0


def command_promote(args: argparse.Namespace) -> int:
    catalog = read_json(args.catalog)
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid before promotion: " + "; ".join(errors))
    practice = next((p for p in catalog["practices"] if p["id"] == args.practice_id), None)
    if not practice:
        raise ValueError(f"unknown practice: {args.practice_id}")
    if not args.reviewed:
        raise ValueError("promotion requires --reviewed")
    if len(args.test_evidence) < 3:
        raise ValueError("promotion requires at least three --test-evidence entries covering pass, fail/partial, and non-applicable behavior")
    refs = args.authoritative_ref
    if practice["domain"] in CONSEQUENTIAL_DOMAINS and not refs:
        raise ValueError("consequential promotion requires at least one current --authoritative-ref")
    practice["enforcement_state"] = "enforceable"
    practice["authoritative_references"] = refs or practice["authoritative_references"]
    practice["verification_date"] = args.verified_on
    practice["revisions"].append({
        "date": args.verified_on,
        "change": "promoted-to-enforceable-after-review",
        "reason": args.reason + " Test evidence: " + "; ".join(args.test_evidence),
        "source_video_ids": [],
        "authoritative_urls": sorted({ref["url"] for ref in practice["authoritative_references"]}),
    })
    catalog["updated_at"] = today()
    atomic_write(args.catalog, catalog)
    print(f"promoted after separate review: {args.practice_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)

    validate = subs.add_parser("validate", help="Validate a practices catalog")
    validate.add_argument("catalog", type=Path)
    validate.set_defaults(func=command_validate)

    init_state = subs.add_parser("init-state", help="Create local incremental-ingestion state")
    init_state.add_argument("state", type=Path)
    init_state.add_argument("--force", action="store_true")
    init_state.set_defaults(func=command_init_state)

    record = subs.add_parser("record-source", help="Record a processed/failed source without media")
    record.add_argument("state", type=Path)
    record.add_argument("--source-id", required=True)
    record.add_argument("--url", required=True)
    record.add_argument("--status", choices=("processed", "failed", "skipped"), required=True)
    record.add_argument("--processed-at", type=iso_date, default=today())
    record.add_argument("--claim-id", action="append", default=[])
    record.add_argument("--creator")
    record.add_argument("--published-date", type=iso_date)
    record.add_argument("--duration-seconds", type=float)
    record.add_argument("--evidence-type", choices=("transcript", "frames", "transcript-and-frames", "metadata-only"), required=True)
    record.set_defaults(func=command_record_source)

    source_id = subs.add_parser("source-id", help="Compute a stable ID for local media without retaining it")
    source_id.add_argument("media", type=Path)
    source_id.set_defaults(func=command_source_id)

    propose = subs.add_parser("propose", help="Add a video claim as candidate/advisory or append provenance")
    propose.add_argument("catalog", type=Path)
    propose.add_argument("--practice-id", required=True)
    propose.add_argument("--domain", required=True)
    propose.add_argument("--title", required=True)
    propose.add_argument("--statement", required=True)
    propose.add_argument("--classification", choices=sorted(CLASSIFICATIONS), required=True)
    propose.add_argument("--enforcement-state", choices=("candidate", "advisory"), default="candidate")
    propose.add_argument("--applicability", required=True)
    propose.add_argument("--signal", action="append", default=[])
    propose.add_argument("--confidence", choices=("HIGH", "MEDIUM", "LOW"), default="LOW")
    propose.add_argument("--source-id", action="append", required=True)
    propose.add_argument("--authoritative-ref", type=parse_reference, action="append", default=[])
    propose.add_argument("--verified-on", type=iso_date)
    propose.add_argument("--reason", required=True)
    propose.set_defaults(func=command_propose)

    promote = subs.add_parser("promote", help="Separate reviewed gate from candidate to enforceable")
    promote.add_argument("catalog", type=Path)
    promote.add_argument("--practice-id", required=True)
    promote.add_argument("--reviewed", action="store_true")
    promote.add_argument("--authoritative-ref", type=parse_reference, action="append", default=[])
    promote.add_argument("--verified-on", type=iso_date, required=True)
    promote.add_argument("--test-evidence", action="append", default=[])
    promote.add_argument("--reason", required=True)
    promote.set_defaults(func=command_promote)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv or sys.argv[1:])
    if hasattr(args, "practice_id") and not PRACTICE_ID.fullmatch(args.practice_id):
        print("error: --practice-id must match practice.[a-z0-9.-]+", file=sys.stderr)
        return 2
    try:
        return args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
