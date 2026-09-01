# Forgeward integration boundary

Best Practices and Forgeward form a suite without sharing mutable runtime state.

| Component | Scope | Product |
|---|---|---|
| Moviola | Individual media source | Observation and timestamped evidence |
| Best Practices | Whole repository and evolving catalog | Learning, contextual alignment, and gaps |
| Forgeward Audit | Whole repository | Security and threat analysis |
| Forgeward Gate | Publish diff | Enforced pre-ship conformance |

Best Practices does not write Forgeward markers, invoke shipping, or turn candidate knowledge into failures. Forgeward does not need Best Practices installed to operate.

## Promotion path

A practice is eligible for a Forgeward contribution only after it is objective, has explicit applicability and exceptions, has current authoritative support where consequential, and survives realistic aligned/divergent/non-applicable repository tests with acceptably low false positives.

Promotion copies a reviewed, narrow control into Forgeward with the source catalog revision and content hash. A drift check may then report when the canonical practice changes. The evolving catalog remains here; Forgeward versions remain reproducible and do not silently change because a new video was ingested.
