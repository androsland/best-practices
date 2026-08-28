# Coding and AI-agent best practices

## The central rule

Use AI to accelerate implementation, not to outsource understanding. The failure mode described in S10 is not that an AI writes code; it is that the developer accepts code without forming a mental model of the design, behavior, and risks (`S10 00:00–00:20`).

Before accepting a change, be able to answer:

- What problem does this solve?
- Which assumptions does it make?
- Which files, interfaces, and data flows does it affect?
- How will failure appear?
- What evidence shows that the change works?

## Four operating principles

The two “behavior skill” clips converge on the same useful rules (`S04 00:20–00:39`; `S22 00:16–00:25`):

1. **Think before coding.** Surface assumptions, ambiguity, and missing information before editing.
2. **Prefer the smallest sufficient design.** Avoid speculative abstractions and code that is not required by the current task.
3. **Make surgical changes.** Touch only the behavior and files needed to meet the request.
4. **Define and verify done.** Turn the goal into observable acceptance criteria, then test those criteria.

These principles are more valuable than the unverified claim that a particular `CLAUDE.md` or skill makes an agent “10× smarter.”

## Keep long agent tasks coherent

S26 proposes a practical orchestration pattern for work that can outgrow a context window (`S26 00:31–02:07`):

### Maintain a project-state file

Update it after every meaningful chunk. Keep it concise enough to reread at the start of each session.

```md
# Project state

## Objective
What outcome is being pursued.

## Acceptance criteria
- Observable condition 1
- Observable condition 2

## Constraints
- Compatibility, security, scope, and non-goals

## Decisions
- Decision: reason and consequences

## Completed
- Result and verification evidence

## In progress
- Current work and unresolved questions

## Next
- The next bounded action
```

### Decompose before execution

- Split a long job into independently reviewable chunks.
- The video suggests roughly five to seven steps per chunk; treat this as a heuristic, not a rule (`S26 01:02–01:27`).
- Start each new session by reading the state file and the relevant code, not by trusting a prose summary alone.
- Give each chunk its own acceptance check.

### Validate between chunks

- Run tests, linters, type checks, or focused manual verification appropriate to the risk.
- Review the diff for unrelated changes and assumptions.
- Summarize what changed and update project state before continuing.
- Require human approval at consequential boundaries such as production changes, migrations, billing, security policy, or destructive actions.

## A compact AI-assisted coding loop

1. Restate the goal and non-goals.
2. Inspect the current implementation.
3. Record assumptions and ask only questions that materially change the result.
4. Choose the smallest design that meets the acceptance criteria.
5. Implement one bounded slice.
6. Verify behavior and inspect the diff.
7. Update state, then continue or stop.

## Warning signs

- The agent invents an API instead of checking the real interface.
- A simple request creates a new framework or abstraction layer.
- Unrelated files change “for consistency.”
- The agent declares success without running relevant checks.
- A later step contradicts an earlier decision.
- Neither the developer nor the state file can explain why the code is shaped this way.

## Source synthesis

- S10 supplies the “understand as fast as AI writes” motivation.
- S04 and S22 supply the four behavioral principles.
- S26 supplies the state-file, chunking, and checkpoint workflow.
