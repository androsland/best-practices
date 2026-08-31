# AI data flow

The Anthropic model provider receives redacted support text only. Personal data is removed before upload. Provider retention and training settings are reviewed by the privacy owner and disclosed to users.

Every provider attempt requires one reservation from the usage guard. The reservation atomically enforces a rolling per-workspace request limit, a per-workspace monthly budget, and an aggregate service/provider monthly budget before spend occurs. Each budget scope emits an alert at the configured threshold. Alert delivery uses an outbox-style sink and cannot roll back or disguise a successful reservation. The in-memory implementation is a deterministic fixture/test reference; production composition must supply the same contract from a shared transactional store so horizontally scaled workers cannot bypass either ceiling.

The provider is asked for a narrow JSON object. Application code parses that object, rejects extra fields, excessive length, control characters, executable markup, credential-like output, and malformed JSON, and permits only one budgeted corrective retry. The retry receives only a bounded validator category, never raw provider output. Calls have a fixed timeout. Validation or provider failure returns no raw model output and marks the case for human review.

Prompt/model changes must update the versioned corpus in `evals/summarization.json` and pass the real provider path before release:

```bash
ANTHROPIC_API_KEY=... npm run eval:live
```

The live gate invokes `AnthropicSummaryProvider` through the production `summarize` boundary, scores actual returned summaries, and emits prompt/model/time/case metadata in the captured test log. Normal CI validates the corpus schema and all deterministic safety/degradation paths without spending provider budget; it cannot substitute for the explicit live release gate.
