# AI data flow

The Anthropic model provider receives redacted support text only. Personal data is removed before upload. Provider retention and training settings are reviewed by the privacy owner and disclosed to users.

Every provider attempt requires a per-workspace reservation from the usage guard. The reservation atomically enforces a rolling request limit and a hard monthly budget before spend occurs, and emits an alert at the configured threshold. The in-memory implementation is a deterministic fixture/test reference; production composition must supply the same contract from a shared transactional store so horizontally scaled workers cannot bypass the ceiling.

The provider is asked for a narrow JSON object. Application code parses that object, rejects extra fields, excessive length, control characters, executable markup, credential-like output, and malformed JSON, and permits only one budgeted corrective retry. Calls have a fixed timeout. Validation or provider failure returns no raw model output and marks the case for human review.
