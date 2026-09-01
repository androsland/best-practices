#!/usr/bin/env python3
"""Validate and update best-practices provenance and ingestion state."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Sequence
from urllib.parse import urlsplit


PRACTICE_ID = re.compile(r"^practice\.[a-z0-9.-]+$")
SCHEMA_VERSION = 1
CLASSIFICATIONS = {"new", "supporting", "conflicting", "obsolete", "promotional"}
CONSEQUENTIAL_DOMAINS = frozenset({
    "application-security",
    "data-reliability",
    "infrastructure-deployment",
})
TEXT_LIMITS = {
    "domain": 100,
    "title": 200,
    "statement": 2_000,
    "applicability": 1_000,
    "signal": 200,
    "source_id": 200,
    "reference_title": 300,
    "reference_supports": 1_000,
    "reference_url": 2_048,
    "reason": 2_000,
    "test_evidence": 500,
}
MAX_PROPOSAL_TEXT_CHARACTERS = 12_000
MAX_PRACTICE_TEXT_CHARACTERS = 50_000
CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x1f\x7f]")
PROHIBITED_TEXT = (
    (re.compile(r"<\s*/?\s*(?:script|iframe|object|embed|svg|style|link|meta)\b", re.I), "executable markup"),
    (re.compile(r"\b(?:javascript|vbscript|data\s*:\s*text/html)\s*:", re.I), "an unsafe URL scheme"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private-key material"),
    (re.compile(r"\b(?:api[_ -]?key|password|secret|access[_ -]?token)\s*[:=]\s*\S+", re.I), "credential-like material"),
    (re.compile(r"\b(?:ignore|disregard|override)\s+(?:all\s+)?(?:previous|prior|system|developer)\s+instructions?\b", re.I), "instruction-like prompt injection"),
)


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


def validate_text(label: str, value: object, limit: int, *, allow_empty: bool = False) -> str | None:
    if not isinstance(value, str):
        return f"{label} must be a string"
    if not allow_empty and not value.strip():
        return f"{label} must not be empty"
    if len(value) > limit:
        return f"{label} exceeds {limit} characters"
    if CONTROL_CHARACTER_RE.search(value):
        return f"{label} contains a control character"
    for pattern, description in PROHIBITED_TEXT:
        if pattern.search(value):
            return f"{label} contains {description}"
    return None


def validate_https_url(label: str, value: object) -> str | None:
    error = validate_text(label, value, TEXT_LIMITS["reference_url"])
    if error:
        return error
    assert isinstance(value, str)
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        return f"{label} must be an HTTPS URL with a hostname"
    if parsed.username or parsed.password:
        return f"{label} must not contain URL credentials"
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        return f"{label} must not target a local hostname"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return None
    if not address.is_global:
        return f"{label} must not target a non-public IP address"
    return None


def parse_reference(value: str) -> dict:
    parts = value.split("|", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("reference must be TITLE|https://URL|SUPPORTED PROPOSITION")
    for label, text, limit in (
        ("reference title", parts[0], TEXT_LIMITS["reference_title"]),
        ("reference proposition", parts[2], TEXT_LIMITS["reference_supports"]),
    ):
        if error := validate_text(label, text, limit):
            raise argparse.ArgumentTypeError(error)
    if error := validate_https_url("reference URL", parts[1]):
        raise argparse.ArgumentTypeError(error)
    return {"title": parts[0], "url": parts[1], "supports": parts[2]}


def proposal_input_errors(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    fields = (
        ("domain", args.domain, TEXT_LIMITS["domain"]),
        ("title", args.title, TEXT_LIMITS["title"]),
        ("statement", args.statement, TEXT_LIMITS["statement"]),
        ("applicability", args.applicability, TEXT_LIMITS["applicability"]),
        ("reason", args.reason, TEXT_LIMITS["reason"]),
        *(("signal", value, TEXT_LIMITS["signal"]) for value in args.signal),
        *(("source ID", value, TEXT_LIMITS["source_id"]) for value in args.source_id),
    )
    total = 0
    for label, value, limit in fields:
        total += len(value) if isinstance(value, str) else 0
        if error := validate_text(label, value, limit):
            errors.append(error)
    for reference in args.authoritative_ref:
        for label, key, limit in (
            ("reference title", "title", TEXT_LIMITS["reference_title"]),
            ("reference proposition", "supports", TEXT_LIMITS["reference_supports"]),
        ):
            value = reference.get(key)
            total += len(value) if isinstance(value, str) else 0
            if error := validate_text(label, value, limit):
                errors.append(error)
        url = reference.get("url")
        total += len(url) if isinstance(url, str) else 0
        if error := validate_https_url("reference URL", url):
            errors.append(error)
    if total > MAX_PROPOSAL_TEXT_CHARACTERS:
        errors.append(
            f"proposal text exceeds the aggregate limit of {MAX_PROPOSAL_TEXT_CHARACTERS} characters"
        )
    return errors


def total_text_characters(value: object) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, list):
        return sum(total_text_characters(item) for item in value)
    if isinstance(value, dict):
        return sum(total_text_characters(item) for item in value.values())
    return 0


def validate_catalog(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must equal {SCHEMA_VERSION}")
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
        if total_text_characters(practice) > MAX_PRACTICE_TEXT_CHARACTERS:
            errors.append(
                f"{label} exceeds the aggregate limit of {MAX_PRACTICE_TEXT_CHARACTERS} text characters"
            )
        if practice.get("enforcement_state") not in {"candidate", "advisory", "enforceable"}:
            errors.append(f"{label}.enforcement_state is invalid")
        if practice.get("confidence") not in {"HIGH", "MEDIUM", "LOW"}:
            errors.append(f"{label}.confidence is invalid")
        for key, limit in (
            ("domain", TEXT_LIMITS["domain"]),
            ("title", TEXT_LIMITS["title"]),
            ("statement", TEXT_LIMITS["statement"]),
        ):
            if error := validate_text(f"{label}.{key}", practice.get(key), limit):
                errors.append(error)
        applicability = practice.get("applicability")
        if not isinstance(applicability, dict):
            errors.append(f"{label}.applicability must be an object")
        else:
            if error := validate_text(
                f"{label}.applicability.description",
                applicability.get("description"),
                TEXT_LIMITS["applicability"],
            ):
                errors.append(error)
            signals = applicability.get("signals")
            if not isinstance(signals, list):
                errors.append(f"{label}.applicability.signals must be an array")
            else:
                for signal_index, signal in enumerate(signals):
                    if error := validate_text(
                        f"{label}.applicability.signals[{signal_index}]",
                        signal,
                        TEXT_LIMITS["signal"],
                    ):
                        errors.append(error)
        source_ids = practice.get("source_video_ids")
        if not isinstance(source_ids, list):
            errors.append(f"{label}.source_video_ids must be an array")
        else:
            for source_index, source_id in enumerate(source_ids):
                if error := validate_text(
                    f"{label}.source_video_ids[{source_index}]",
                    source_id,
                    TEXT_LIMITS["source_id"],
                ):
                    errors.append(error)
        revisions = practice.get("revisions")
        if not isinstance(revisions, list) or not revisions:
            errors.append(f"{label}.revisions must be a non-empty array")
        else:
            for revision_index, item in enumerate(revisions):
                revision_label = f"{label}.revisions[{revision_index}]"
                if not isinstance(item, dict):
                    errors.append(f"{revision_label} must be an object")
                    continue
                if error := validate_text(
                    f"{revision_label}.reason",
                    item.get("reason"),
                    TEXT_LIMITS["reason"],
                ):
                    errors.append(error)
                authoritative_urls = item.get("authoritative_urls")
                if not isinstance(authoritative_urls, list):
                    errors.append(f"{revision_label}.authoritative_urls must be an array")
                else:
                    for url_index, url in enumerate(authoritative_urls):
                        if error := validate_https_url(
                            f"{revision_label}.authoritative_urls[{url_index}]", url
                        ):
                            errors.append(error)
        refs = practice.get("authoritative_references", [])
        if not isinstance(refs, list) or any(not isinstance(ref, dict) for ref in refs):
            errors.append(f"{label}.authoritative_references is invalid")
            refs = []
        for reference_index, reference in enumerate(refs):
            for key, limit in (
                ("title", TEXT_LIMITS["reference_title"]),
                ("supports", TEXT_LIMITS["reference_supports"]),
            ):
                if error := validate_text(
                    f"{label}.authoritative_references[{reference_index}].{key}",
                    reference.get(key),
                    limit,
                ):
                    errors.append(error)
            if error := validate_https_url(
                f"{label}.authoritative_references[{reference_index}].url",
                reference.get("url"),
            ):
                errors.append(error)
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
    atomic_write(
        args.state,
        {
            "schema_version": SCHEMA_VERSION,
            "updated_at": today(),
            "processed_sources": {},
        },
    )
    print(f"initialized state: {args.state}")
    return 0


def command_record_source(args: argparse.Namespace) -> int:
    data = (
        read_json(args.state)
        if args.state.exists()
        else {
            "schema_version": SCHEMA_VERSION,
            "updated_at": today(),
            "processed_sources": {},
        }
    )
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


def source_catalog_references(catalog: dict, source_id: str) -> list[dict]:
    references = []
    for practice in catalog["practices"]:
        revision_indexes = [
            index
            for index, item in enumerate(practice["revisions"])
            if source_id in item.get("source_video_ids", [])
        ]
        if source_id in practice["source_video_ids"] or revision_indexes:
            references.append({
                "practice_id": practice["id"],
                "current_source": source_id in practice["source_video_ids"],
                "revision_indexes": revision_indexes,
            })
    return references


def command_export_source(args: argparse.Namespace) -> int:
    if error := validate_text("source ID", args.source_id, TEXT_LIMITS["source_id"]):
        raise ValueError(f"source export rejected: {error}")
    state = read_json(args.state)
    records = state.get("processed_sources")
    if not isinstance(records, dict):
        raise ValueError("state.processed_sources must be an object")
    catalog = read_json(args.catalog)
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid before source export: " + "; ".join(errors))
    references = source_catalog_references(catalog, args.source_id)
    record = records.get(args.source_id)
    if record is None and not references:
        raise ValueError(f"unknown source: {args.source_id}")
    print(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "exported_at": today(),
        "source_id": args.source_id,
        "state_record": record,
        "catalog_references": references,
    }, indent=2, sort_keys=True))
    return 0


def command_delete_source(args: argparse.Namespace) -> int:
    fields = (
        ("source ID", args.source_id, TEXT_LIMITS["source_id"]),
        ("reason", args.reason, TEXT_LIMITS["reason"]),
    )
    errors = [
        error
        for label, value, limit in fields
        if (error := validate_text(label, value, limit))
    ]
    if errors:
        raise ValueError("source deletion rejected: " + "; ".join(errors))

    state = read_json(args.state)
    records = state.get("processed_sources")
    if not isinstance(records, dict):
        raise ValueError("state.processed_sources must be an object")
    state_changed = records.pop(args.source_id, None) is not None

    catalog = read_json(args.catalog)
    catalog_errors = validate_catalog(catalog)
    if catalog_errors:
        raise ValueError(
            "catalog is invalid before source deletion: " + "; ".join(catalog_errors)
        )
    changed_practices = []
    for practice in catalog["practices"]:
        changed = args.source_id in practice["source_video_ids"]
        practice["source_video_ids"] = [
            value for value in practice["source_video_ids"] if value != args.source_id
        ]
        for item in practice["revisions"]:
            source_ids = item.get("source_video_ids", [])
            if args.source_id in source_ids:
                item["source_video_ids"] = [
                    value for value in source_ids if value != args.source_id
                ]
                changed = True
        if changed:
            practice["revisions"].append({
                "date": args.deleted_on,
                "change": "removed-source-personal-data",
                "reason": args.reason,
                "source_video_ids": [],
                "authoritative_urls": sorted(
                    reference["url"]
                    for reference in practice["authoritative_references"]
                ),
            })
            changed_practices.append(practice["id"])

    if not state_changed and not changed_practices:
        raise ValueError(f"unknown source: {args.source_id}")
    state["updated_at"] = today()
    catalog["updated_at"] = today()
    catalog_errors = validate_catalog(catalog)
    if catalog_errors:
        raise ValueError(
            "catalog is invalid after source deletion: " + "; ".join(catalog_errors)
        )

    # State-first is retry-safe. If the catalog replace fails, a retry still finds
    # and removes every catalog reference even though the state record is gone.
    if state_changed:
        atomic_write(args.state, state)
    if changed_practices:
        atomic_write(args.catalog, catalog)
    print(
        f"deleted source personal data: {args.source_id} "
        f"({len(changed_practices)} practice references updated)"
    )
    return 0


def revision(classification: str, reason: str, source_ids: list[str], references: list[dict], date: str) -> dict:
    return {
        "date": date,
        "change": f"video-claim-{classification}",
        "reason": reason,
        "source_video_ids": sorted(set(source_ids)),
        "authoritative_urls": sorted({ref["url"] for ref in references}),
    }


def merge_references(*reference_groups: list[dict]) -> list[dict]:
    """Merge authoritative reference objects by URL, preferring later records."""
    references_by_url = {
        reference["url"]: reference
        for references in reference_groups
        for reference in references
    }
    return [references_by_url[url] for url in sorted(references_by_url)]


def definition_snapshot(practice: dict) -> dict:
    return {
        "domain": practice["domain"],
        "title": practice["title"],
        "statement": practice["statement"],
        "applicability": {
            "description": practice["applicability"]["description"],
            "signals": list(practice["applicability"]["signals"]),
        },
        "confidence": practice["confidence"],
    }


def command_propose(args: argparse.Namespace) -> int:
    input_errors = proposal_input_errors(args)
    if input_errors:
        raise ValueError("proposal rejected: " + "; ".join(input_errors))
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
        existing["authoritative_references"] = merge_references(
            existing["authoritative_references"], refs
        )
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
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid after proposed update: " + "; ".join(errors))
    atomic_write(args.catalog, catalog)
    print(f"{action}: {args.practice_id}")
    return 0


def command_repair_references(args: argparse.Namespace) -> int:
    """Recover missing top-level reference objects from identical URLs elsewhere."""
    catalog = read_json(args.catalog)
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid before reference repair: " + "; ".join(errors))

    reference_candidates: dict[str, dict[tuple[str, str], dict]] = {}
    for practice in catalog["practices"]:
        for reference in practice["authoritative_references"]:
            candidates = reference_candidates.setdefault(reference["url"], {})
            candidates[(reference["title"], reference["supports"])] = reference

    repaired_count = 0
    repaired_practices = 0
    unresolved: list[tuple[str, str, str]] = []
    for practice in catalog["practices"]:
        present_urls = {reference["url"] for reference in practice["authoritative_references"]}
        revision_urls = {
            url
            for item in practice["revisions"]
            for url in item.get("authoritative_urls", [])
        }
        recovered: list[dict] = []
        for url in sorted(revision_urls - present_urls):
            candidates = list(reference_candidates.get(url, {}).values())
            if len(candidates) == 1:
                recovered.append(candidates[0])
            else:
                disposition = "not found" if not candidates else "ambiguous"
                unresolved.append((practice["id"], url, disposition))
        if not recovered:
            continue
        practice["authoritative_references"] = merge_references(
            practice["authoritative_references"], recovered
        )
        recovered_urls = sorted(reference["url"] for reference in recovered)
        practice["revisions"].append({
            "date": args.repaired_on,
            "change": "repaired-authoritative-reference-index",
            "reason": (
                "Recovered authoritative reference metadata from matching URLs already "
                "present elsewhere in the catalog; no new source proposition was introduced."
            ),
            "source_video_ids": [],
            "authoritative_urls": recovered_urls,
        })
        repaired_count += len(recovered)
        repaired_practices += 1

    if repaired_count:
        catalog["updated_at"] = today()
        errors = validate_catalog(catalog)
        if errors:
            raise ValueError("catalog is invalid after reference repair: " + "; ".join(errors))
        atomic_write(args.catalog, catalog)

    print(
        f"repaired authoritative references: {repaired_count} across "
        f"{repaired_practices} practices"
    )
    for practice_id, url, disposition in unresolved:
        print(f"unresolved authoritative reference ({disposition}): {practice_id} | {url}")
    return 0


def command_reclassify_domain(args: argparse.Namespace) -> int:
    """Change a practice domain through a validated, append-only revision."""
    input_errors = [
        error
        for label, value, limit in (
            ("target domain", args.to_domain, TEXT_LIMITS["domain"]),
            ("reason", args.reason, TEXT_LIMITS["reason"]),
        )
        if (error := validate_text(label, value, limit))
    ]
    if input_errors:
        raise ValueError("domain reclassification rejected: " + "; ".join(input_errors))
    catalog = read_json(args.catalog)
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid before domain reclassification: " + "; ".join(errors))
    practice = next((item for item in catalog["practices"] if item["id"] == args.practice_id), None)
    if not practice:
        raise ValueError(f"unknown practice: {args.practice_id}")
    previous_domain = practice["domain"]
    if previous_domain == args.to_domain:
        raise ValueError(f"practice already uses domain: {args.to_domain}")
    practice["domain"] = args.to_domain
    practice["revisions"].append({
        "date": args.reclassified_on,
        "change": "reclassified-domain",
        "reason": args.reason,
        "source_video_ids": [],
        "authoritative_urls": sorted(
            reference["url"] for reference in practice["authoritative_references"]
        ),
        "domain_change": {"from": previous_domain, "to": args.to_domain},
    })
    catalog["updated_at"] = today()
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid after domain reclassification: " + "; ".join(errors))
    atomic_write(args.catalog, catalog)
    print(f"reclassified domain: {args.practice_id} ({previous_domain} -> {args.to_domain})")
    return 0


def command_revise_practice(args: argparse.Namespace) -> int:
    """Revise a candidate definition while retaining an append-only before/after record."""
    requested = {
        "domain": args.domain,
        "title": args.title,
        "statement": args.statement,
        "applicability": args.applicability,
        "confidence": args.confidence,
    }
    if not any(value is not None for value in requested.values()) and args.signal is None:
        raise ValueError("practice revision requires at least one changed definition field")
    fields = [
        ("reason", args.reason, TEXT_LIMITS["reason"]),
        *((key, value, TEXT_LIMITS[key]) for key, value in requested.items()
          if value is not None and key in TEXT_LIMITS),
        *(("signal", value, TEXT_LIMITS["signal"]) for value in (args.signal or [])),
    ]
    input_errors = [
        error for label, value, limit in fields if (error := validate_text(label, value, limit))
    ]
    if input_errors:
        raise ValueError("practice revision rejected: " + "; ".join(input_errors))

    catalog = read_json(args.catalog)
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid before practice revision: " + "; ".join(errors))
    practice = next((item for item in catalog["practices"] if item["id"] == args.practice_id), None)
    if not practice:
        raise ValueError(f"unknown practice: {args.practice_id}")
    before = definition_snapshot(practice)
    if args.domain is not None:
        practice["domain"] = args.domain
    if args.title is not None:
        practice["title"] = args.title
    if args.statement is not None:
        practice["statement"] = args.statement
    if args.applicability is not None:
        practice["applicability"]["description"] = args.applicability
    if args.signal is not None:
        practice["applicability"]["signals"] = sorted(set(args.signal))
    if args.confidence is not None:
        practice["confidence"] = args.confidence
    if args.authoritative_ref:
        practice["authoritative_references"] = merge_references(
            practice["authoritative_references"], args.authoritative_ref
        )
    if args.verified_on:
        practice["verification_date"] = args.verified_on
    if practice["domain"] in CONSEQUENTIAL_DOMAINS and (
        not practice["authoritative_references"] or not practice["verification_date"]
    ):
        raise ValueError("consequential practice revision requires authoritative references and verification")
    after = definition_snapshot(practice)
    if before == after and not args.authoritative_ref and not args.verified_on:
        raise ValueError("requested practice revision makes no change")
    practice["revisions"].append({
        "date": args.revised_on,
        "change": "revised-candidate-definition",
        "reason": args.reason,
        "source_video_ids": [],
        "authoritative_urls": sorted(
            reference["url"] for reference in practice["authoritative_references"]
        ),
        "definition_change": {"before": before, "after": after},
    })
    catalog["updated_at"] = today()
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid after practice revision: " + "; ".join(errors))
    atomic_write(args.catalog, catalog)
    print(f"revised candidate definition: {args.practice_id}")
    return 0


def command_merge_practice(args: argparse.Namespace) -> int:
    """Merge a duplicate practice into a canonical practice and repair state links."""
    if args.from_id == args.into_id:
        raise ValueError("--from-id and --into-id must differ")
    if error := validate_text("reason", args.reason, TEXT_LIMITS["reason"]):
        raise ValueError(f"merge rejected: {error}")

    catalog = read_json(args.catalog)
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid before merge: " + "; ".join(errors))
    practices = catalog["practices"]
    source = next((p for p in practices if p["id"] == args.from_id), None)
    target = next((p for p in practices if p["id"] == args.into_id), None)
    if not source:
        raise ValueError(f"unknown source practice: {args.from_id}")
    if not target:
        raise ValueError(f"unknown target practice: {args.into_id}")

    source_ids = sorted(set(source["source_video_ids"]))
    target["source_video_ids"] = sorted(set(target["source_video_ids"] + source_ids))
    combined_references = {
        (reference["url"], reference["title"], reference["supports"]): reference
        for reference in target["authoritative_references"] + source["authoritative_references"]
    }
    target["authoritative_references"] = [
        combined_references[key] for key in sorted(combined_references)
    ]
    verified_dates = [
        date for date in (target.get("verification_date"), source.get("verification_date")) if date
    ]
    target["verification_date"] = max(verified_dates) if verified_dates else None
    target["revisions"].extend(source["revisions"])
    target["revisions"].append({
        "date": args.merged_on,
        "change": "merged-duplicate-practice",
        "reason": args.reason,
        "source_video_ids": source_ids,
        "authoritative_urls": sorted({reference["url"] for reference in combined_references.values()}),
        "merged_from": {
            key: source[key]
            for key in (
                "id",
                "domain",
                "title",
                "statement",
                "enforcement_state",
                "applicability",
                "confidence",
                "verification_date",
                "authoritative_references",
            )
        },
    })
    practices.remove(source)
    practices.sort(key=lambda item: item["id"])
    catalog["updated_at"] = today()
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid after merge: " + "; ".join(errors))

    state = read_json(args.state)
    records = state.get("processed_sources")
    if not isinstance(records, dict):
        raise ValueError("state.processed_sources must be an object")
    for record in records.values():
        claim_ids = record.get("claim_ids", [])
        if not isinstance(claim_ids, list):
            raise ValueError("state claim_ids must be arrays")
        if args.from_id in claim_ids:
            record["claim_ids"] = sorted(
                {args.into_id if claim_id == args.from_id else claim_id for claim_id in claim_ids}
            )
    state["updated_at"] = today()

    # State-first is retry-safe: the canonical target already exists. Catalog-first
    # could leave state pointing at a removed practice if the second replace failed.
    atomic_write(args.state, state)
    atomic_write(args.catalog, catalog)
    print(f"merged practice: {args.from_id} -> {args.into_id}")
    return 0


def command_annotate_merge(args: argparse.Namespace) -> int:
    """Backfill the source definition for merge history created by an older tool."""
    fields = (
        ("source domain", args.from_domain, TEXT_LIMITS["domain"]),
        ("source title", args.from_title, TEXT_LIMITS["title"]),
        ("source statement", args.from_statement, TEXT_LIMITS["statement"]),
        ("source applicability", args.from_applicability, TEXT_LIMITS["applicability"]),
        *(("source signal", value, TEXT_LIMITS["signal"]) for value in args.from_signal),
    )
    errors = [
        error for label, value, limit in fields if (error := validate_text(label, value, limit))
    ]
    if errors:
        raise ValueError("merge annotation rejected: " + "; ".join(errors))
    catalog = read_json(args.catalog)
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid before merge annotation: " + "; ".join(errors))
    target = next((p for p in catalog["practices"] if p["id"] == args.practice_id), None)
    if not target:
        raise ValueError(f"unknown target practice: {args.practice_id}")
    merge_revision = next(
        (
            item
            for item in reversed(target["revisions"])
            if item.get("change") == "merged-duplicate-practice"
            and (
                "merged_from" not in item
                or "authoritative_references" not in item["merged_from"]
            )
        ),
        None,
    )
    if not merge_revision:
        raise ValueError(f"no unannotated merge revision found for: {args.practice_id}")
    merge_revision["merged_from"] = {
        "id": args.from_id,
        "domain": args.from_domain,
        "title": args.from_title,
        "statement": args.from_statement,
        "enforcement_state": args.from_enforcement_state,
        "applicability": {
            "description": args.from_applicability,
            "signals": sorted(set(args.from_signal)),
        },
        "confidence": args.from_confidence,
        "verification_date": args.from_verified_on,
        "authoritative_references": args.from_authoritative_ref,
    }
    catalog["updated_at"] = today()
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid after merge annotation: " + "; ".join(errors))
    atomic_write(args.catalog, catalog)
    print(f"annotated merge history: {args.from_id} -> {args.practice_id}")
    return 0


def command_promote(args: argparse.Namespace) -> int:
    promotion_fields = [
        ("reason", args.reason, TEXT_LIMITS["reason"]),
        *(("test evidence", item, TEXT_LIMITS["test_evidence"]) for item in args.test_evidence),
    ]
    promotion_errors = [
        error
        for label, value, limit in promotion_fields
        if (error := validate_text(label, value, limit))
    ]
    if promotion_errors:
        raise ValueError("promotion rejected: " + "; ".join(promotion_errors))
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
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog is invalid after promotion: " + "; ".join(errors))
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

    export_source = subs.add_parser(
        "export-source", help="Export retained state and catalog references for one source"
    )
    export_source.add_argument("state", type=Path)
    export_source.add_argument("catalog", type=Path)
    export_source.add_argument("--source-id", required=True)
    export_source.set_defaults(func=command_export_source)

    delete_source = subs.add_parser(
        "delete-source", help="Remove one source's personal data and provenance identifiers"
    )
    delete_source.add_argument("state", type=Path)
    delete_source.add_argument("catalog", type=Path)
    delete_source.add_argument("--source-id", required=True)
    delete_source.add_argument("--deleted-on", type=iso_date, default=today())
    delete_source.add_argument("--reason", required=True)
    delete_source.set_defaults(func=command_delete_source)

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

    repair_references = subs.add_parser(
        "repair-references",
        help="Recover revision reference metadata from matching catalog URLs",
    )
    repair_references.add_argument("catalog", type=Path)
    repair_references.add_argument("--repaired-on", type=iso_date, default=today())
    repair_references.set_defaults(func=command_repair_references)

    reclassify_domain = subs.add_parser(
        "reclassify-domain", help="Change a practice domain with revision history"
    )
    reclassify_domain.add_argument("catalog", type=Path)
    reclassify_domain.add_argument("--practice-id", required=True)
    reclassify_domain.add_argument("--to-domain", required=True)
    reclassify_domain.add_argument("--reclassified-on", type=iso_date, default=today())
    reclassify_domain.add_argument("--reason", required=True)
    reclassify_domain.set_defaults(func=command_reclassify_domain)

    revise = subs.add_parser(
        "revise-practice", help="Revise a candidate definition with before/after history"
    )
    revise.add_argument("catalog", type=Path)
    revise.add_argument("--practice-id", required=True)
    revise.add_argument("--domain")
    revise.add_argument("--title")
    revise.add_argument("--statement")
    revise.add_argument("--applicability")
    revise.add_argument("--signal", action="append", default=None)
    revise.add_argument("--confidence", choices=("HIGH", "MEDIUM", "LOW"))
    revise.add_argument("--authoritative-ref", type=parse_reference, action="append", default=[])
    revise.add_argument("--verified-on", type=iso_date)
    revise.add_argument("--revised-on", type=iso_date, default=today())
    revise.add_argument("--reason", required=True)
    revise.set_defaults(func=command_revise_practice)

    merge = subs.add_parser("merge-practice", help="Merge a duplicate practice and repair state links")
    merge.add_argument("catalog", type=Path)
    merge.add_argument("state", type=Path)
    merge.add_argument("--from-id", required=True)
    merge.add_argument("--into-id", required=True)
    merge.add_argument("--merged-on", type=iso_date, default=today())
    merge.add_argument("--reason", required=True)
    merge.set_defaults(func=command_merge_practice)

    annotate_merge = subs.add_parser(
        "annotate-merge", help="Backfill a source definition on older merge history"
    )
    annotate_merge.add_argument("catalog", type=Path)
    annotate_merge.add_argument("--practice-id", required=True)
    annotate_merge.add_argument("--from-id", required=True)
    annotate_merge.add_argument("--from-domain", required=True)
    annotate_merge.add_argument("--from-title", required=True)
    annotate_merge.add_argument("--from-statement", required=True)
    annotate_merge.add_argument(
        "--from-enforcement-state", choices=("candidate", "advisory", "enforceable"), required=True
    )
    annotate_merge.add_argument("--from-applicability", required=True)
    annotate_merge.add_argument("--from-signal", action="append", default=[])
    annotate_merge.add_argument("--from-confidence", choices=("HIGH", "MEDIUM", "LOW"), required=True)
    annotate_merge.add_argument("--from-verified-on", type=iso_date)
    annotate_merge.add_argument(
        "--from-authoritative-ref", type=parse_reference, action="append", default=[]
    )
    annotate_merge.set_defaults(func=command_annotate_merge)

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
    for attribute in ("from_id", "into_id"):
        value = getattr(args, attribute, None)
        if value is not None and not PRACTICE_ID.fullmatch(value):
            print(f"error: --{attribute.replace('_', '-')} must match practice.[a-z0-9.-]+", file=sys.stderr)
            return 2
    try:
        return args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
