import { describe, expect, it } from "vitest";
import evaluationCorpus from "../evals/summarization.json";
import {
  AnthropicSummaryProvider,
  InMemoryUsageGuard,
  SUMMARY_MODEL,
  SUMMARY_PROMPT_VERSION,
  summarize,
} from "../src/ai/summarize";

const liveEvaluation = process.env.RUN_LIVE_AI_EVAL === "1";

describe.skipIf(!liveEvaluation)("live versioned summary quality evaluation", () => {
  it("scores current provider outputs through the production prompt and validator", async () => {
    const apiKey = process.env.ANTHROPIC_API_KEY;
    expect(apiKey, "ANTHROPIC_API_KEY is required for the live release gate").toBeTruthy();
    const provider = new AnthropicSummaryProvider(apiKey);
    const results = [];

    for (const example of evaluationCorpus.cases) {
      const result = await summarize(
        {
          workspaceId: `release-eval-${example.id}`,
          redactedText: example.input,
        },
        { provider, usageGuard: new InMemoryUsageGuard() },
      );
      expect(result.status, example.id).toBe("ok");
      if (result.status !== "ok") continue;
      const normalized = result.summary.toLowerCase();
      const covered = example.expected_concepts.filter((concept) =>
        normalized.includes(concept.toLowerCase()),
      ).length;
      const conceptCoverage = covered / example.expected_concepts.length;
      for (const forbidden of evaluationCorpus.forbidden_phrases) {
        expect(normalized, example.id).not.toContain(forbidden.toLowerCase());
      }
      expect(conceptCoverage, example.id).toBeGreaterThanOrEqual(
        evaluationCorpus.minimum_concept_coverage,
      );
      results.push({
        id: example.id,
        conceptCoverage,
        summary: result.summary,
      });
    }

    console.log(JSON.stringify({
      schemaVersion: 1,
      runAt: new Date().toISOString(),
      promptVersion: SUMMARY_PROMPT_VERSION,
      model: SUMMARY_MODEL,
      cases: results,
    }));
  });
});
