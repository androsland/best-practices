import { describe, expect, it, vi } from "vitest";
import {
  DEFAULT_SUMMARY_POLICY,
  InMemoryUsageGuard,
  summarize,
  type SummaryPolicy,
  type SummaryProvider,
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

describe("summarize", () => {
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

  it("uses one bounded corrective retry for malformed output", async () => {
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
    expect(fake.createSummary).toHaveBeenCalledTimes(2);
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

  it("times out a stalled provider", async () => {
    const stalled: SummaryProvider = {
      createSummary: () => new Promise(() => undefined),
    };
    const result = await summarize(
      input,
      { provider: stalled, usageGuard: new InMemoryUsageGuard() },
      policy({ providerTimeoutMs: 5 }),
    );

    expect(result).toMatchObject({
      status: "degraded",
      reason: "provider_failure",
    });
  });

  it("enforces a per-workspace request ceiling before a paid call", async () => {
    const limits = policy({ maxRequestsPerMinute: 1 });
    const guard = new InMemoryUsageGuard(limits);
    const fake = providerFrom([
      JSON.stringify({ summary: "First result." }),
      JSON.stringify({ summary: "This must not be used." }),
    ]);

    await summarize(input, { provider: fake.provider, usageGuard: guard }, limits);
    const denied = await summarize(
      input,
      { provider: fake.provider, usageGuard: guard },
      limits,
    );

    expect(denied).toMatchObject({
      status: "degraded",
      reason: "rate_limited",
    });
    expect(fake.createSummary).toHaveBeenCalledTimes(1);
  });

  it("enforces a hard monthly budget and emits the configured alert", async () => {
    const limits = policy({
      monthlyBudgetCents: 10,
      reservedCostPerAttemptCents: 10,
      budgetAlertPercent: 80,
    });
    const alert = vi.fn();
    const guard = new InMemoryUsageGuard(limits, alert);
    const fake = providerFrom([
      JSON.stringify({ summary: "Within budget." }),
      JSON.stringify({ summary: "Over budget." }),
    ]);

    await summarize(input, { provider: fake.provider, usageGuard: guard }, limits);
    const denied = await summarize(
      input,
      { provider: fake.provider, usageGuard: guard },
      limits,
    );

    expect(alert).toHaveBeenCalledOnce();
    expect(denied).toMatchObject({
      status: "degraded",
      reason: "budget_exhausted",
    });
    expect(fake.createSummary).toHaveBeenCalledTimes(1);
  });
});
