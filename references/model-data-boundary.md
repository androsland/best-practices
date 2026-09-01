# Model data boundary

This protocol applies before the project mapper, any domain reviewer, or the
verification reviewer receives repository content. It is a hard launch gate, not a
reporting note.

## Processing disclosure and consent

Before reading repository files into a model context, tell the user:

- the model provider and exact reviewer model selected by the active runtime;
- that repository-derived paths, excerpts, architecture summaries, and findings will
  be processed by the mapper and applicable reviewers;
- the retention and training posture established by the active product, workspace
  policy, or current provider documentation; and
- any part of that posture that is unknown or cannot be verified from the current
  environment.

Do not infer account, workspace, zero-retention, or training settings from the plugin,
the repository, or a generic provider policy. An unknown posture must be disclosed as
unknown. The original request for an audit is not consent to an undisclosed processing
boundary. Obtain explicit confirmation for the disclosed provider, model, data classes,
and known or unknown retention/training posture before launching a model reviewer.

## Local minimization preflight

Perform the preflight with local deterministic tools before any subagent launch. Do
not print matched values or send raw scanner matches to a model.

1. Limit discovery to version-controlled files. Never inspect untracked, ignored,
   credential-store, browser-profile, production-export, or user-upload paths.
2. Classify likely secret material, private keys, environment files, database dumps,
   logs, support exports, recordings/transcripts, analytics exports, and files that may
   contain customer, employee, patient, student, financial, authentication, or other
   personal records.
3. Always exclude credential values, private keys, session material, and raw production
   records. Consent does not make those values necessary audit input. When behavior
   around them matters, use a value-free schema, configuration key name, or redacted
   excerpt.
4. Default to excluding or redacting personal and private operational data. If those
   exclusions make a requested conclusion impossible, stop and ask again before
   including anything. Name the exact path category and purpose, repeat the provider,
   model, and retention/training posture, and offer an exclusion-based audit with an
   explicit coverage limit. Do not treat consent from another run as reusable.
5. Record a `model_input_plan` outside the target repository. It must contain the
   approved tracked paths or bounded excerpts, excluded path categories and reasons,
   redactions, provider, model, retention/training posture, the user's confirmation,
   and the expected coverage impact. Do not copy raw sensitive files into the plan.

If safe classification cannot be completed without exposing values, stop. A partial
audit with named coverage limits is preferable to silently expanding the model data
boundary.

## Minimum-necessary reviewer inputs

- The project mapper receives the deterministic inventory plus only the approved
  architecture-relevant paths or bounded excerpts. Passing `<target-root>` identifies
  paths; it does not authorize unrestricted reads.
- Each domain reviewer receives the project map, its catalog packet, and a domain-sized
  allowlist or excerpt bundle. It must not rescan the whole repository.
- The verifier receives only challenged results and their approved cited evidence. It
  must not perform a new whole-repository search.
- If an agent needs another file, it returns an `evidence_request` naming the smallest
  path and purpose. The main operator applies this protocol again before adding that
  evidence to the plan.

Every launch prompt includes the applicable `model_input_plan` scope. Every excluded,
redacted, inaccessible, or declined surface appears in the final coverage limits.
