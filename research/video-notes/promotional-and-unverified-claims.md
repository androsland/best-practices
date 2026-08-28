# Promotional and unverified claims

This file isolates claims that should not quietly become operational guidance.

## Side-hustle / income reel

S05 instructs viewers to add a `vmx.io/mcp` connector, provide a popular children’s YouTube channel to Claude, and request a 30-day content plan allegedly capable of earning $10,000 per month (`S05 00:17–00:47`). It also claims $12,000 in personal earnings without evidence.

Do not treat this as a business plan. Missing considerations include:

- copyright, trademark, and imitation risk;
- YouTube rules for reused, synthetic, and child-directed content;
- advertising and disclosure obligations;
- audience acquisition, production quality, moderation, and support costs;
- the security and permissions of the connector;
- evidence for the income claim and whether results are representative.

## “Top model on a normal laptop”

S16 does not name the model or repository in speech or sampled frames. “Top-level,” “normal laptop,” “almost usable speed,” “no monthly bill,” and “easy to set up” are too vague to evaluate. Local inference can improve data control, but validate model license, model size, RAM/VRAM, tokens per second, quality for the real workload, update traffic, telemetry, and total hardware/energy cost.

## Repository and plugin superlatives

The following claims appear in S02, S04, S14, S20, S22, and S25 and remain unverified:

- exact GitHub star counts;
- “10×/11× smarter or more productive”;
- “almost unlimited usage” or billions of free tokens;
- a complete development team “for free”;
- a premium website from one command in two minutes;
- claims of official status, prize winnings, or universal cross-platform support.

Repository metrics and product terms change. More importantly, popularity does not establish security, correctness, fit, or maintenance quality.

## Watermark-removal claim

S27 says a repository removes invisible Unicode, EXIF metadata, and other properties that identify AI-generated files (`S27 00:07–00:43`). The clip does not establish that:

- every named provider currently applies such markers to every listed format;
- the repository detects or removes all provenance mechanisms;
- removal is permitted by provider terms, employer policy, client contracts, or law;
- stripping metadata leaves document semantics and accessibility intact.

Removing provenance can also enable deception. A legitimate metadata-sanitization need should be narrowly defined, documented, and tested without representing generated work as human-authored.

## Cost claims about deployment

S15 frames a VPS as fixed-cost and managed/serverless platforms as financially irrational for “actual applications.” Real cost includes operator time, backups, observability, incident response, redundancy, bandwidth, storage, scaling, and downtime. Compare full workload-specific costs; do not select architecture from a reel’s absolute rule.

## A credibility checklist

Before acting on a clip’s claim:

1. Identify the canonical product/repository and current version.
2. Find primary documentation for the claimed behavior.
3. Inspect permissions, data flows, dependencies, license, and uninstall path.
4. Reproduce the result with a defined baseline and representative input.
5. Separate one-time promotional results from ongoing cost and maintenance.
6. Check legal, platform-policy, privacy, and security constraints.
7. Record what remains unknown.
