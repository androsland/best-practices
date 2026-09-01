#!/usr/bin/env python3
"""Snapshot or compare Git worktree state without writing inside the repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def git(root: Path, *args: str) -> bytes:
    completed = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    return completed.stdout


def untracked_digest(root: Path) -> tuple[str, int]:
    paths = [
        item.decode()
        for item in git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
        if item
    ]
    digest = hashlib.sha256()
    for rel in sorted(paths):
        path = root / rel
        digest.update(rel.encode())
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"symlink:")
            digest.update(path.readlink().as_posix().encode())
        elif path.is_file():
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        else:
            digest.update(b"non-regular")
        digest.update(b"\0")
    return digest.hexdigest(), len(paths)


def snapshot(root: Path) -> dict:
    try:
        top = Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    except (subprocess.CalledProcessError, OSError) as exc:
        raise ValueError("workspace guard requires a Git repository") from exc
    if top != root.resolve():
        raise ValueError(f"target must be the Git root: {top}")
    status = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    diff = git(root, "diff", "--binary", "HEAD")
    untracked_sha256, untracked_files = untracked_digest(root)
    return {
        "schema_version": 1,
        "root": str(top),
        "head": git(root, "rev-parse", "HEAD").decode().strip(),
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "diff_sha256": hashlib.sha256(diff).hexdigest(),
        "status_entries": len([item for item in status.split(b"\0") if item]),
        "untracked_sha256": untracked_sha256,
        "untracked_files": untracked_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    make = subs.add_parser("snapshot")
    make.add_argument("root", type=Path)
    check = subs.add_parser("check")
    check.add_argument("root", type=Path)
    check.add_argument("snapshot_file", type=Path)
    args = parser.parse_args()
    try:
        current = snapshot(args.root.resolve())
        if args.command == "snapshot":
            print(json.dumps(current, indent=2))
            return 0
        before = json.loads(args.snapshot_file.read_text())
        changed = [
            key for key in (
                "root", "head", "status_sha256", "diff_sha256", "status_entries",
                "untracked_sha256", "untracked_files",
            )
            if before.get(key) != current.get(key)
        ]
        result = {"unchanged": not changed, "changed_fields": changed, "before": before, "after": current}
        print(json.dumps(result, indent=2))
        return 0 if not changed else 3
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
