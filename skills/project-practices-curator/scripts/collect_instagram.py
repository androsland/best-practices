#!/usr/bin/env python3
"""Enumerate Instagram reels with gallery-dl without downloading media."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Sequence


REEL_RE = re.compile(r"https?://(?:www\.)?instagram\.com/reels?/([A-Za-z0-9_-]+)", re.I)
GALLERY_DL_VERSION = "1.32.9"
OVERSAMPLING_FACTOR = 3
MAX_SELECTION_LIMIT = 500
MAX_OFFLINE_ENUMERATION_BYTES = 5_000_000
MAX_LIVE_ENUMERATION_BYTES = 10_000_000
MAX_ERROR_CHARACTERS = 2_000
VERSION_TIMEOUT_SECONDS = 5.0
ENUMERATION_TIMEOUT_SECONDS = 120.0
PROCESS_TERMINATION_GRACE_SECONDS = 2.0
READ_CHUNK_BYTES = 64 * 1024


class BoundedProcessError(RuntimeError):
    """A child process exceeded an explicit time or output boundary."""


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=PROCESS_TERMINATION_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=PROCESS_TERMINATION_GRACE_SECONDS)


def run_bounded(
    command: Sequence[str],
    *,
    stdout_limit: int,
    stderr_limit: int,
    timeout_seconds: float,
) -> tuple[int, bytes, bytes]:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None and process.stderr is not None
    events: queue.Queue[tuple[str, bytes | None]] = queue.Queue(maxsize=32)

    def pump(name: str, stream: Any) -> None:
        try:
            while chunk := stream.read(READ_CHUNK_BYTES):
                events.put((name, chunk))
        finally:
            stream.close()
            events.put((name, None))

    for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
        threading.Thread(target=pump, args=(name, stream), daemon=True).start()

    stdout = bytearray()
    stderr_tail = bytearray()
    open_streams = {"stdout", "stderr"}
    deadline = time.monotonic() + timeout_seconds
    try:
        while open_streams:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BoundedProcessError(
                    f"process exceeded the {timeout_seconds:g}-second timeout"
                )
            try:
                name, chunk = events.get(timeout=min(remaining, 0.25))
            except queue.Empty:
                continue
            if chunk is None:
                open_streams.discard(name)
                continue
            if name == "stdout":
                if len(stdout) + len(chunk) > stdout_limit:
                    raise BoundedProcessError(
                        f"process stdout exceeded {stdout_limit} bytes"
                    )
                stdout.extend(chunk)
            else:
                stderr_tail.extend(chunk)
                if len(stderr_tail) > stderr_limit:
                    del stderr_tail[:-stderr_limit]
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BoundedProcessError(
                f"process exceeded the {timeout_seconds:g}-second timeout"
            )
        return_code = process.wait(timeout=remaining)
    except (BoundedProcessError, subprocess.TimeoutExpired):
        stop_process(process)
        raise BoundedProcessError(
            f"process exceeded the {timeout_seconds:g}-second timeout or output limit"
        ) from None
    return return_code, bytes(stdout), bytes(stderr_tail)


def gallery_dl_status() -> dict:
    executable = shutil.which("gallery-dl")
    version = None
    if executable:
        try:
            return_code, stdout, stderr = run_bounded(
                [executable, "--version"],
                stdout_limit=1_024,
                stderr_limit=1_024,
                timeout_seconds=VERSION_TIMEOUT_SECONDS,
            )
        except (OSError, BoundedProcessError):
            return_code, stdout, stderr = 1, b"", b""
        if return_code == 0:
            version = stdout.decode("utf-8", errors="replace").strip() or stderr.decode(
                "utf-8", errors="replace"
            ).strip() or None

    options: list[dict] = []

    def offer(label: str, argv: list[str], reason: str) -> None:
        options.append({
            "label": label,
            "argv": argv,
            "command": shlex.join(argv),
            "reason": reason,
            "requires_explicit_approval": True,
            "requires_network": True,
        })

    if shutil.which("pipx"):
        offer("pipx", ["pipx", "install", "--force", f"gallery-dl=={GALLERY_DL_VERSION}"], "Installs the reviewed gallery-dl release in an isolated tool environment.")
    if shutil.which("uv"):
        offer("uv tool", ["uv", "tool", "install", "--force", f"gallery-dl=={GALLERY_DL_VERSION}"], "Installs the reviewed gallery-dl release as an isolated uv-managed tool.")
    offer(
        "Python user install",
        [sys.executable, "-m", "pip", "install", "--user", "--upgrade", f"gallery-dl=={GALLERY_DL_VERSION}"],
        "Pinned fallback; may be unavailable in externally managed Python environments.",
    )
    for index, option in enumerate(options):
        option["recommended"] = index == 0
    return {
        "name": "gallery-dl",
        "installed": bool(executable),
        "ready": bool(executable and version == GALLERY_DL_VERSION),
        "executable": executable,
        "version": version,
        "reviewed_version": GALLERY_DL_VERSION,
        "install_options": [] if executable and version == GALLERY_DL_VERSION else options,
    }


def parse_date(value: str) -> str:
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected ISO date YYYY-MM-DD") from exc


def load_json(path: Path) -> Any:
    if path.stat().st_size > MAX_OFFLINE_ENUMERATION_BYTES:
        raise ValueError(
            f"offline enumeration exceeds {MAX_OFFLINE_ENUMERATION_BYTES} bytes; "
            "split it into a smaller JSON/JSON-lines batch"
        )
    with path.open("r", encoding="utf-8") as handle:
        text = handle.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        values = []
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                values.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {number} of {path}") from exc
        return values


def iter_dicts(value: Any) -> Iterable[dict]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def first(record: dict, keys: Sequence[str]) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def normalize_date(value: Any) -> str | None:
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc).date().isoformat()
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, str):
        match = re.match(r"(\d{4}-\d{2}-\d{2})", value)
        return match.group(1) if match else None
    return None


def canonical_reel_url(record: dict) -> tuple[str, str] | None:
    possible_urls: list[str] = []
    for key in ("post_url", "webpage_url", "url", "source", "_extractor_url"):
        value = record.get(key)
        if isinstance(value, str):
            possible_urls.append(value)
    shortcode = first(record, ("shortcode", "code"))
    if isinstance(shortcode, str) and re.fullmatch(r"[A-Za-z0-9_-]+", shortcode):
        possible_urls.insert(0, f"https://www.instagram.com/reel/{shortcode}/")
    for url in possible_urls:
        match = REEL_RE.search(url)
        if match:
            code = match.group(1)
            return f"instagram:{code}", f"https://www.instagram.com/reel/{code}/"
    typename = str(first(record, ("typename", "type", "subcategory")) or "").lower()
    media_id = first(record, ("media_id", "post_id", "id"))
    if media_id is not None and any(word in typename for word in ("reel", "video", "igtv")):
        return f"instagram:{media_id}", str(first(record, ("post_url", "webpage_url")) or "")
    return None


def extract_reels(raw: Any) -> list[dict]:
    reels: dict[str, dict] = {}
    for record in iter_dicts(raw):
        identity = canonical_reel_url(record)
        if not identity:
            continue
        source_id, url = identity
        item = reels.setdefault(source_id, {
            "source_id": source_id,
            "url": url,
            "published_date": None,
            "creator": None,
            "duration_seconds": None,
        })
        item["published_date"] = item["published_date"] or normalize_date(first(record, ("date", "timestamp", "taken_at", "created_at")))
        item["creator"] = item["creator"] or first(record, ("username", "owner_username", "user"))
        duration = first(record, ("duration", "video_duration"))
        if item["duration_seconds"] is None and isinstance(duration, (int, float)):
            item["duration_seconds"] = duration
    return sorted(reels.values(), key=lambda item: (item["published_date"] or "", item["source_id"]), reverse=True)


def load_processed(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    data = load_json(path)
    records = data.get("processed_sources", {}) if isinstance(data, dict) else {}
    if isinstance(records, dict):
        return {key for key, value in records.items() if isinstance(value, dict) and value.get("status") == "processed"}
    return set()


def gallery_command(args: argparse.Namespace) -> list[str]:
    # Ignore default config so a pre-existing cookies/browser setting cannot
    # bypass this wrapper's invocation-local consent boundary.
    command = ["gallery-dl", "--config-ignore", "--simulate", "--dump-json", "--no-input", "-o", "extractor.instagram.include=reels"]
    if args.limit:
        command.extend(["--post-range", f"1-{args.limit * OVERSAMPLING_FACTOR}"])
    if args.after:
        command.extend(["--date-after", args.after])
    if args.before:
        command.extend(["--date-before", args.before])
    if args.cookies:
        command.extend(["--cookies", str(args.cookies)])
    if args.cookies_from_browser:
        command.extend(["--cookies-from-browser", args.cookies_from_browser])
    command.append(args.profile_url)
    return command


def safe_command(command: Sequence[str]) -> list[str]:
    safe = list(command)
    if "--cookies" in safe:
        safe[safe.index("--cookies") + 1] = "<redacted-cookie-file>"
    if "--cookies-from-browser" in safe:
        safe[safe.index("--cookies-from-browser") + 1] = "<consented-browser-profile>"
    return safe


def enumerate_raw(args: argparse.Namespace) -> tuple[Any, list[str]]:
    if args.enumeration_file:
        planned = gallery_command(args)
        planned[0] = "<offline-enumeration>"
        return load_json(args.enumeration_file), safe_command(planned)
    if not shutil.which("gallery-dl"):
        raise RuntimeError("gallery-dl is not installed; install it or use --enumeration-file for saved metadata")
    command = gallery_command(args)
    return_code, stdout, stderr = run_bounded(
        command,
        stdout_limit=MAX_LIVE_ENUMERATION_BYTES,
        stderr_limit=MAX_ERROR_CHARACTERS,
        timeout_seconds=ENUMERATION_TIMEOUT_SECONDS,
    )
    if return_code != 0:
        detail = stderr.decode("utf-8", errors="replace").strip().splitlines()
        last_line = detail[-1] if detail else "unknown gallery-dl error"
        if args.cookies:
            last_line = last_line.replace(str(args.cookies), "<redacted-cookie-file>")
        if args.cookies_from_browser:
            last_line = last_line.replace(
                args.cookies_from_browser,
                "<consented-browser-profile>",
            )
        raise RuntimeError(f"gallery-dl enumeration failed: {last_line}")
    try:
        text = stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("gallery-dl output is not valid UTF-8") from exc
    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError:
        raw = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                raw.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid gallery-dl JSON on output line {line_number}"
                ) from exc
    return raw, safe_command(command)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile_url", nargs="?", help="Instagram profile URL")
    parser.add_argument("--check-dependencies", action="store_true", help="Report gallery-dl availability and installation choices as JSON")
    parser.add_argument("--state", type=Path, help="Local curator state used by --new-only")
    parser.add_argument("--limit", type=int, default=20, help="Maximum reels selected after filtering (default: 20)")
    parser.add_argument("--after", type=parse_date, help="Only posts after this ISO date")
    parser.add_argument("--before", type=parse_date, help="Only posts before this ISO date")
    parser.add_argument("--new-only", action="store_true", help="Exclude sources already marked processed")
    auth = parser.add_mutually_exclusive_group()
    auth.add_argument("--cookies", type=Path, help="User-supplied Netscape cookie file")
    auth.add_argument("--cookies-from-browser", help="gallery-dl browser specification")
    parser.add_argument("--consent-browser-cookies", action="store_true", help="Explicit consent for this invocation to read browser cookies")
    parser.add_argument("--enumeration-file", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.check_dependencies:
        return args
    if not args.profile_url:
        parser.error("profile_url is required unless --check-dependencies is used")
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.limit > MAX_SELECTION_LIMIT:
        parser.error(f"--limit must not exceed {MAX_SELECTION_LIMIT}")
    if args.after and args.before and args.after > args.before:
        parser.error("--after must not be later than --before")
    if args.cookies_from_browser and not args.consent_browser_cookies:
        parser.error("--cookies-from-browser requires --consent-browser-cookies in the same invocation")
    if args.consent_browser_cookies and not args.cookies_from_browser:
        parser.error("--consent-browser-cookies is valid only with --cookies-from-browser")
    if not re.match(r"^https?://(?:www\.)?instagram\.com/", args.profile_url, re.I):
        parser.error("profile_url must be an instagram.com HTTP(S) URL")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    dependency = gallery_dl_status()
    if args.check_dependencies:
        print(json.dumps({
            "schema_version": 1,
            "dependencies": {"gallery-dl": dependency},
            "next_step": "Proceed when ready is true; otherwise ask the user to approve one offered pinned install command.",
        }, indent=2, sort_keys=True))
        return 0
    if not args.enumeration_file and not dependency["ready"]:
        error_code = (
            "DEPENDENCY_VERSION_MISMATCH"
            if dependency["installed"]
            else "DEPENDENCY_MISSING"
        )
        print(json.dumps({
            "schema_version": 1,
            "error": {
                "code": error_code,
                "message": (
                    f"gallery-dl {GALLERY_DL_VERSION} is required for live Instagram profile enumeration."
                ),
            },
            "dependency": dependency,
            "next_step": "Ask the user to approve one offered install command; do not install automatically.",
        }, indent=2, sort_keys=True))
        return 3
    try:
        raw, command = enumerate_raw(args)
        reels = extract_reels(raw)
        processed = load_processed(args.state) if args.new_only else set()
        selected = []
        for item in reels:
            date = item["published_date"]
            if (args.after or args.before) and not date:
                continue
            if args.after and date and date <= args.after:
                continue
            if args.before and date and date >= args.before:
                continue
            if item["source_id"] in processed:
                continue
            selected.append(item)
            if len(selected) >= args.limit:
                break
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    result = {
        "schema_version": 1,
        "profile_url": args.profile_url,
        "enumeration_command": command,
        "browser_cookie_consent": bool(args.cookies_from_browser and args.consent_browser_cookies),
        "new_only": args.new_only,
        "selected_count": len(selected),
        "selected": selected,
        "retention": "enumeration metadata only; media must be processed in temporary storage by Moviola",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
