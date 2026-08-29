import { describe, expect, it, vi } from "vitest";
import evaluationCorpus from "../evals/summarization.json";
import {
  DEFAULT_SUMMARY_POLICY,
  InMemoryUsageGuard,
  SUMMARY_PROMPT_VERSION,
  summarize,
  type BudgetAlert,
  type SummaryPolicy,
  type SummaryProvider,
  type UsageGuard,
} from "../src/ai/summarize";

function policy(overrides: Partial<SummaryPolicy> = {}): SummaryPolicy {
  return { ...DEFAULT_SUMMARY_POLICY, ...overrides };
}

function providerFrom(outputs: Array<string | Error>) {
  const createSummary = vi.fn<SummaryProvider["createSummary"]>();
  for (const output of outputs) {
    if (output instanceof Error) createSummary.mockRejectedValueOnce(output);
    else createSummary.mockResolvedValueOnce(output);
  }
  return { provider: { createSummary }, createSummary };
}

const input = {
  workspaceId: "workspace-a",
  redactedText: "A redacted support case",
};

describe("summarize output boundary", () => {
  it("returns only a validated application-owned summary", async () => {
    const fake = providerFrom([
      JSON.stringify({ summary: "Resolved after a retry." }),
    ]);
    const result = await summarize(input, {
      provider: fake.provider,
      usageGuard: new InMemoryUsageGuard(),
    });

    expect(result.status).toBe("ok");
    if (result.status !== "ok") throw new Error("expected a validated summary");
    expect(result.needsHumanReview).toBe(false);
    expect(result.summary.length).toBeGreaterThan(0);
    expect(result.summary.length).toBeLessThanOrEqual(
      DEFAULT_SUMMARY_POLICY.maxSummaryCharacters,
    );
    expect(fake.createSummary).toHaveBeenCalledTimes(1);
  });

  it("sends a bounded validator-derived correction on the retry", async () => {
    const fake = providerFrom([
      "not-json",
      JSON.stringify({ summary: "A valid bounded result." }),
    ]);
    const result = await summarize(input, {
      provider: fake.provider,
      usageGuard: new InMemoryUsageGuard(),
    });

    expect(result.status).toBe("ok");
    expect(fake.createSummary).toHaveBeenCalledTimes(2);
    expect(fake.createSummary.mock.calls[0][2]).toBeUndefined();
    expect(fake.createSummary.mock.calls[1][2]).toBe("invalid_json");
  });

  it("rejects unsafe output and hands off for human review", async () => {
    const unsafe = JSON.stringify({ summary: "<script>steal()</script>" });
    const fake = providerFrom([unsafe, unsafe]);
    const result = await summarize(input, {
      provider: fake.provider,
      usageGuard: new InMemoryUsageGuard(),
    });

    expect(result).toMatchObject({
      status: "degraded",
      reason: "invalid_output",
      needsHumanReview: true,
      summary: null,
    });
    expect(fake.createSummary.mock.calls[1][2]).toBe("unsafe_content");
  });

  it("degrades without exposing provider failures", async () => {
    const fake = providerFrom([new Error("provider detail")]);
    const result = await summarize(input, {
      provider: fake.provider,
      usageGuard: new InMemoryUsageGuard(),
    });

    expect(result).toMatchObject({
      status: "degraded",
      reason: "provider_failure",
      needsHumanReview: true,
    });
    expect(JSON.stringify(result)).not.toContain("provider detail");
  });

  it("aborts a stalled provider at the deterministic timeout", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | undefined;
    const stalled: SummaryProvider = {
      createSummary: (_text, capturedSignal) => {
        signal = capturedSignal;
        return new Promise(() => undefined);
      },
    };
    const resultPromise = summarize(
      input,
      { provider: stalled, usageGuard: new InMemoryUsageGuard() },
      policy({ providerTimeoutMs: 50 }),
    );

    await vi.advanceTimersByTimeAsync(50);
    const result = await resultPromise;
    expect(signal?.aborted).toBe(true);
    expect(result).toMatchObject({
      status: "degraded",
      reason: "provider_failure",
    });
    vi.useRealTimers();
  });

  it.each([
    { workspaceId: "", redactedText: "valid" },
    { workspaceId: "w".repeat(129), redactedText: "valid" },
    { workspaceId: "workspace-a", redactedText: "" },
    {
      workspaceId: "workspace-a",
      redactedText: "x".repeat(DEFAULT_SUMMARY_POLICY.maxInputCharacters + 1),
    },
  ])("rejects invalid input before budget reservation", async (invalidInput) => {
    const provider = { createSummary: vi.fn() };
    const usageGuard: UsageGuard = { reserve: vi.fn() };
    const result = await summarize(invalidInput, { provider, usageGuard });

    expect(result).toMatchObject({ status: "degraded", reason: "invalid_input" });
    expect(usageGuard.reserve).not.toHaveBeenCalled();
    expect(provider.createSummary).not.toHaveBeenCalled();
  });

  it("accepts input at the documented boundary", async () => {
    const fake = providerFrom([JSON.stringify({ summary: "At the boundary." })]);
    const result = await summarize(
      {
        workspaceId: "w".repeat(128),
        redactedText: "x".repeat(DEFAULT_SUMMARY_POLICY.maxInputCharacters),
      },
      { provider: fake.provider, usageGuard: new InMemoryUsageGuard() },
    );

    expect(result.status).toBe("ok");
    expect(fake.createSummary).toHaveBeenCalledOnce();
  });
});

describe("usage guard", () => {
  const start = Date.UTC(2026, 7, 1, 0, 0, 0);

  it("resets rate limits at 60 seconds and isolates workspaces", async () => {
    const limits = policy({ maxRequestsPerMinute: 1 });
    const guard = new InMemoryUsageGuard(limits);

    expect(await guard.reserve("workspace-a", start)).toMatchObject({ allowed: true });
    expect(await guard.reserve("workspace-a", start + 59_999)).toMatchObject({
      allowed: false,
      reason: "rate_limited",
    });
    expect(await guard.reserve("workspace-b", start + 59_999)).toMatchObject({
      allowed: true,
    });
    expect(await guard.reserve("workspace-a", start + 60_000)).toMatchObject({
      allowed: true,
    });
  });

  it("resets workspace and service budgets on month rollover", async () => {
    const limits = policy({
      monthlyBudgetCents: 5,
      serviceMonthlyBudgetCents: 5,
      reservedCostPerAttemptCents: 5,
    });
    const guard = new InMemoryUsageGuard(limits);

    expect(await guard.reserve("workspace-a", start)).toMatchObject({ allowed: true });
    expect(await guard.reserve("workspace-a", start + 1)).toMatchObject({
      allowed: false,
      reason: "budget_exhausted",
    });
    expect(await guard.reserve("workspace-a", Date.UTC(2026, 8, 1))).toMatchObject({
      allowed: true,
    });
  });

  it("enforces the global service ceiling across many workspaces", async () => {
    const limits = policy({
      monthlyBudgetCents: 100,
      serviceMonthlyBudgetCents: 10,
      reservedCostPerAttemptCents: 5,
    });
    const guard = new InMemoryUsageGuard(limits);

    const reservations = await Promise.all([
      guard.reserve("workspace-a", start),
      guard.reserve("workspace-b", start),
      guard.reserve("workspace-c", start),
    ]);
    expect(reservations.filter((item) => item.allowed)).toHaveLength(2);
    expect(reservations.filter((item) => !item.allowed)).toHaveLength(1);
  });

  it("emits each threshold alert once and contains alert transport failure", async () => {
    const limits = policy({
      monthlyBudgetCents: 10,
      serviceMonthlyBudgetCents: 20,
      reservedCostPerAttemptCents: 5,
      budgetAlertPercent: 50,
    });
    const events: BudgetAlert[] = [];
    const failures: BudgetAlert[] = [];
    const guard = new InMemoryUsageGuard(
      limits,
      {
        enqueue: async (event) => {
          events.push(event);
          if (event.scope === "service") throw new Error("alert transport down");
        },
      },
      (event) => failures.push(event),
    );

    expect(await guard.reserve("workspace-a", start)).toMatchObject({ allowed: true });
    expect(await guard.reserve("workspace-a", start + 1)).toMatchObject({ allowed: true });
    expect(await guard.reserve("workspace-b", start + 2)).toMatchObject({ allowed: true });
    expect(events.filter((event) => event.scope === "workspace")).toHaveLength(2);
    expect(events.filter((event) => event.scope === "service")).toHaveLength(1);
    expect(failures).toHaveLength(1);
  });
});

describe("versioned summary quality evaluations", () => {
  it("meets the corpus concept-coverage threshold", () => {
    expect(evaluationCorpus.prompt_version).toBe(SUMMARY_PROMPT_VERSION);
    for (const example of evaluationCorpus.cases) {
      const normalized = example.recorded_summary.toLowerCase();
      const covered = example.expected_concepts.filter((concept) =>
        normalized.includes(concept.toLowerCase()),
      ).length;
      const coverage = covered / example.expected_concepts.length;
      expect(coverage, example.id).toBeGreaterThanOrEqual(
        evaluationCorpus.minimum_concept_coverage,
      );
      for (const forbidden of evaluationCorpus.forbidden_phrases) {
        expect(normalized, example.id).not.toContain(forbidden.toLowerCase());
      }
    }
  });
});
