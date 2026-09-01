# Video curation workflow

## Direct URLs and local files

Use Moviola, following its installed `SKILL.md` rather than assuming a fixed installation path. Prefer native captions, then local Whisper when configured; API transcription may upload extracted audio and must follow Moviola's disclosed configuration/consent behavior. Read all frames Moviola returns and align visual claims with timestamped transcript evidence.

Create a temporary working directory outside the repository. After extracting claims and provenance, remove downloaded video, audio, frames, intermediate subtitles, and raw transcript. Never commit those artifacts. Keep a transcript excerpt only when essential to explain a claim, within copyright limits, and record its timestamp.

## Instagram profiles

Live profile enumeration requires `gallery-dl` on `PATH`. Check before collection:

```bash
python3 scripts/collect_instagram.py --check-dependencies
```

The JSON response reports the installed path/version, reviewed version, readiness, or host-appropriate pinned installation choices. If missing or mismatched, offer those choices to the user and request explicit approval for one exact command. Do not install silently, combine approval with cookie consent, or replace gallery-dl with an ad hoc scraper. After an approved installation, rerun the check and proceed only when `ready` is `true`. A failed install gets one reported attempt unless the user directs another approach.

Run the collector once; enumeration is itself the read-only planning operation:

```bash
python3 scripts/collect_instagram.py PROFILE_URL --state state.json --limit 10 --new-only
```

Add `--after YYYY-MM-DD` and/or `--before YYYY-MM-DD` as needed. Instagram enumeration normally requires authenticated cookies. Browser extraction is allowed only with both:

```bash
--cookies-from-browser firefox --consent-browser-cookies
```

The consent flag applies only to that invocation. Do not persist the browser/profile choice as implied future consent. `--cookies FILE` uses a user-supplied cookie file and must not copy its path or contents into durable state.

The collector invokes gallery-dl in simulate/JSON mode with default configuration disabled and enumerates reels; it does not download media. Disabling default configuration prevents a previously configured browser-cookie source from bypassing the wrapper's invocation-local consent flag. Moviola handles each selected reel separately in temporary storage. Respect platform terms, rate limits, access controls, and user authority.

## Limits and stopping

- `--limit` caps selected unique reels after date and new-only filtering and is bounded to 500 per invocation. Split larger jobs into reviewed incremental batches.
- Offline enumeration accepts JSON or JSON-lines up to 5 MB per batch; split larger exports so selection and error handling stay bounded.
- `--new-only` excludes stable IDs already marked processed in state.
- Enumeration prints candidates and planned command behavior without writing state or downloading.
- Stop after the requested limit, on authentication failure, or when gallery-dl reports access/rate-limit failure. Do not loop around access controls.

## Model-output validation and release evaluation

Treat transcript/frame extraction and claim classification as untrusted model output. Submit proposed fields only through `curation_state.py propose`; it enforces per-field and aggregate length limits, rejects control characters, executable markup, credential-like text, unsafe URLs, and instruction-like prompt injection, then validates the complete constructed catalog before its atomic write.

On rejection, pass only the validator category back to the extraction step. Attempt at most two corrected extractions. If both fail, do not change the catalog; record the source with `curation_state.py record-source ... --status failed` and require human review.

Before a release that changes the curator prompt, Moviola integration, classifications, or validation boundary, run the versioned adversarial cases in `tests/test_curator.py` and a live host evaluation over the same cases when Moviola is available. Confirm evidence timestamps, classification, authoritative-source disposition, safe rejection, and unchanged-catalog behavior. If the external host cannot run in CI, attach the live evaluation output to the release review; deterministic CI remains the fail-closed fallback and must pass.

## Retained record

Keep source ID, canonical URL, creator/profile, publication date when known, duration when known, evidence type, processing date, claim classifications, and catalog revision linkage. For a local file, compute its stable ID with `python3 scripts/curation_state.py source-id <path>` before cleanup. Do not retain session cookies, signed media URLs, raw media, or transient download paths.

Creator/profile names, canonical profile or post URLs, and linkable platform IDs are personal data even when public. Review retained source records at least annually and remove them no later than 365 days after processing unless a documented active-practice review still needs that source. Do not extend retention merely because storage is convenient.

Export everything retained for a source before responding to an access request:

```bash
python3 scripts/curation_state.py export-source state.json knowledge/practices.json \
  --source-id instagram:SHORTCODE
```

The command writes the state record and every current/revision catalog reference to standard output. Treat that export as personal data, deliver it through an approved channel, and delete transient copies afterward.

Remove a source after its retention period or a verified deletion request:

```bash
python3 scripts/curation_state.py delete-source state.json knowledge/practices.json \
  --source-id instagram:SHORTCODE \
  --reason "Verified deletion request"
```

Deletion removes the state record and the identifier from current and historical catalog provenance, then adds an identifier-free erasure revision. Privacy deletion is the explicit exception to append-only provenance. Re-review any practice left without sufficient evidence and downgrade or remove it separately. The command updates current files; repository owners must also apply their approved history-rewrite, backup-expiry, fork, and release-artifact procedure when deletion must cover older Git history or copies outside the repository.
