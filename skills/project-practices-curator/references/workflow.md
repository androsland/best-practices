# Video curation workflow

## Direct URLs and local files

Use Moviola, following its installed `SKILL.md` rather than assuming a fixed installation path. Prefer native captions, then local Whisper when configured; API transcription may upload extracted audio and must follow Moviola's disclosed configuration/consent behavior. Read all frames Moviola returns and align visual claims with timestamped transcript evidence.

Create a temporary working directory outside the repository. After extracting claims and provenance, remove downloaded video, audio, frames, intermediate subtitles, and raw transcript. Never commit those artifacts. Keep a transcript excerpt only when essential to explain a claim, within copyright limits, and record its timestamp.

## Instagram profiles

Live profile enumeration requires `gallery-dl` on `PATH`. Check before collection:

```bash
python3 scripts/collect_instagram.py --check-dependencies
```

The JSON response reports the installed path/version or host-appropriate installation choices. If missing, offer those choices to the user and request explicit approval for one exact command. Do not install silently, combine approval with cookie consent, or replace gallery-dl with an ad hoc scraper. After an approved installation, rerun the check and proceed only when `installed` is `true`. A failed install gets one reported attempt unless the user directs another approach.

Run the collector in this order:

```bash
python3 scripts/collect_instagram.py PROFILE_URL --state state.json --dry-run --limit 10 --new-only
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
- Dry-run prints candidates and planned command behavior without writing state or downloading.
- Stop after the requested limit, on authentication failure, or when gallery-dl reports access/rate-limit failure. Do not loop around access controls.

## Retained record

Keep source ID, canonical URL, creator/profile, publication date when known, duration when known, evidence type, processing date, claim classifications, and catalog revision linkage. For a local file, compute its stable ID with `python3 scripts/curation_state.py source-id <path>` before cleanup. Do not retain session cookies, signed media URLs, raw media, or transient download paths.
