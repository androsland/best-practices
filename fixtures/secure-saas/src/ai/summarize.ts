import Anthropic from "@anthropic-ai/sdk";

export type SummaryFailureReason =
  | "budget_exhausted"
  | "invalid_input"
  | "invalid_output"
  | "provider_failure"
  | "rate_limited";

export type SummaryResult =
  | { status: "ok"; summary: string; needsHumanReview: false }
  | {
      status: "degraded";
      summary: null;
      reason: SummaryFailureReason;
      needsHumanReview: true;
    };

export interface SummaryInput {
  workspaceId: string;
  redactedText: string;
}

export interface SummaryProvider {
  createSummary(redactedText: string, signal: AbortSignal): Promise<string>;
}

export interface UsageGuard {
  reserve(workspaceId: string, nowMs: number): Promise<
    | { allowed: true }
    | { allowed: false; reason: "budget_exhausted" | "rate_limited" }
  >;
}

export interface SummaryPolicy {
  maxInputCharacters: number;
  maxSummaryCharacters: number;
  maxRequestsPerMinute: number;
  monthlyBudgetCents: number;
  reservedCostPerAttemptCents: number;
  budgetAlertPercent: number;
  providerTimeoutMs: number;
  correctiveRetries: number;
}

export const DEFAULT_SUMMARY_POLICY: Readonly<SummaryPolicy> = Object.freeze({
  maxInputCharacters: 12_000,
  maxSummaryCharacters: 500,
  maxRequestsPerMinute: 20,
  monthlyBudgetCents: 2_000,
  reservedCostPerAttemptCents: 5,
  budgetAlertPercent: 80,
  providerTimeoutMs: 8_000,
  correctiveRetries: 1,
});

type BudgetAlert = (event: {
  workspaceId: string;
  reservedCents: number;
  monthlyBudgetCents: number;
}) => void;

interface UsageRecord {
  month: string;
  reservedCents: number;
  windowStartedAtMs: number;
  requestsInWindow: number;
  alertSent: boolean;
}

/**
 * Deterministic reference guard for this fixture and its tests. A horizontally
 * scaled deployment must provide the same UsageGuard contract from a shared,
 * transactional store so reservations remain atomic across processes.
 */
export class InMemoryUsageGuard implements UsageGuard {
  private readonly records = new Map<string, UsageRecord>();

  constructor(
    private readonly policy: Readonly<SummaryPolicy> = DEFAULT_SUMMARY_POLICY,
    private readonly onBudgetAlert: BudgetAlert = () => undefined,
  ) {}

  async reserve(workspaceId: string, nowMs: number) {
    const month = new Date(nowMs).toISOString().slice(0, 7);
    const previous = this.records.get(workspaceId);
    const record: UsageRecord =
      previous?.month === month
        ? previous
        : {
            month,
            reservedCents: 0,
            windowStartedAtMs: nowMs,
            requestsInWindow: 0,
            alertSent: false,
          };

    if (nowMs - record.windowStartedAtMs >= 60_000) {
      record.windowStartedAtMs = nowMs;
      record.requestsInWindow = 0;
    }

    if (record.requestsInWindow >= this.policy.maxRequestsPerMinute) {
      this.records.set(workspaceId, record);
      return { allowed: false, reason: "rate_limited" } as const;
    }

    const nextReservedCents =
      record.reservedCents + this.policy.reservedCostPerAttemptCents;
    if (nextReservedCents > this.policy.monthlyBudgetCents) {
      this.records.set(workspaceId, record);
      return { allowed: false, reason: "budget_exhausted" } as const;
    }

    // No await occurs before both counters are updated, so a reservation is atomic
    // within this reference process. Production implementations must transact here.
    record.requestsInWindow += 1;
    record.reservedCents = nextReservedCents;
    this.records.set(workspaceId, record);

    const alertThreshold =
      (this.policy.monthlyBudgetCents * this.policy.budgetAlertPercent) / 100;
    if (!record.alertSent && record.reservedCents >= alertThreshold) {
      record.alertSent = true;
      this.onBudgetAlert({
        workspaceId,
        reservedCents: record.reservedCents,
        monthlyBudgetCents: this.policy.monthlyBudgetCents,
      });
    }

    return { allowed: true } as const;
  }
}

export class AnthropicSummaryProvider implements SummaryProvider {
  private readonly client: Anthropic;

  constructor(apiKey: string | undefined) {
    if (!apiKey) throw new Error("ANTHROPIC_API_KEY is required");
    this.client = new Anthropic({ apiKey });
  }

  async createSummary(redactedText: string, signal: AbortSignal): Promise<string> {
    const response = await this.client.messages.create(
      {
        model: "claude-sonnet-4-5",
        max_tokens: 300,
        system:
          "Return exactly one JSON object with one string field named summary. " +
          "Do not include links, executable markup, credentials, or additional fields.",
        messages: [
          {
            role: "user",
            content: `<redacted_support_text>${redactedText}</redacted_support_text>`,
          },
        ],
      },
      { signal },
    );

    return response.content
      .filter((block) => block.type === "text")
      .map((block) => block.text)
      .join("");
  }
}

const UNSAFE_OUTPUT = [
  /<\/?(?:script|iframe|object)\b/i,
  /\bjavascript:/i,
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/,
  /\b(?:api[_ -]?key|password|secret)\s*[:=]\s*\S+/i,
];

function degraded(reason: SummaryFailureReason): SummaryResult {
  return { status: "degraded", summary: null, reason, needsHumanReview: true };
}

function validateSummary(raw: string, maxCharacters: number): string | null {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }

  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  if (Object.keys(record).length !== 1 || typeof record.summary !== "string") {
    return null;
  }

  const summary = record.summary.trim();
  if (
    !summary ||
    summary.length > maxCharacters ||
    /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/.test(summary)
  ) {
    return null;
  }
  if (UNSAFE_OUTPUT.some((pattern) => pattern.test(summary))) return null;
  return summary;
}

async function callWithTimeout(
  provider: SummaryProvider,
  text: string,
  timeoutMs: number,
): Promise<string> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      provider.createSummary(text, controller.signal),
      new Promise<never>((_, reject) => {
        timer = setTimeout(() => {
          controller.abort();
          reject(new Error("summary provider timed out"));
        }, timeoutMs);
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export async function summarize(
  input: SummaryInput,
  dependencies: {
    provider: SummaryProvider;
    usageGuard: UsageGuard;
    now?: () => number;
  },
  policy: Readonly<SummaryPolicy> = DEFAULT_SUMMARY_POLICY,
): Promise<SummaryResult> {
  const workspaceId = input.workspaceId.trim();
  const redactedText = input.redactedText.trim();
  if (
    !workspaceId ||
    workspaceId.length > 128 ||
    !redactedText ||
    redactedText.length > policy.maxInputCharacters
  ) {
    return degraded("invalid_input");
  }

  const now = dependencies.now ?? Date.now;
  for (let attempt = 0; attempt <= policy.correctiveRetries; attempt += 1) {
    const reservation = await dependencies.usageGuard.reserve(workspaceId, now());
    if (!reservation.allowed) return degraded(reservation.reason);

    let raw: string;
    try {
      raw = await callWithTimeout(
        dependencies.provider,
        redactedText,
        policy.providerTimeoutMs,
      );
    } catch {
      return degraded("provider_failure");
    }

    const summary = validateSummary(raw, policy.maxSummaryCharacters);
    if (summary !== null) {
      return { status: "ok", summary, needsHumanReview: false };
    }
  }

  return degraded("invalid_output");
}
