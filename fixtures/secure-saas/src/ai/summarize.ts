import Anthropic from "@anthropic-ai/sdk";

export const SUMMARY_PROMPT_VERSION = "support-summary-v1";

export type SummaryFailureReason =
  | "budget_exhausted"
  | "invalid_input"
  | "invalid_output"
  | "provider_failure"
  | "rate_limited";

export type CorrectionReason =
  | "control_character"
  | "empty_summary"
  | "invalid_json"
  | "invalid_shape"
  | "summary_too_long"
  | "unsafe_content";

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
  createSummary(
    redactedText: string,
    signal: AbortSignal,
    correction?: CorrectionReason,
  ): Promise<string>;
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
  serviceMonthlyBudgetCents: number;
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
  serviceMonthlyBudgetCents: 20_000,
  reservedCostPerAttemptCents: 5,
  budgetAlertPercent: 80,
  providerTimeoutMs: 8_000,
  correctiveRetries: 1,
});

export interface BudgetAlert {
  scope: "service" | "workspace";
  workspaceId?: string;
  reservedCents: number;
  monthlyBudgetCents: number;
}

export interface BudgetAlertSink {
  enqueue(event: BudgetAlert): Promise<void>;
}

interface UsageRecord {
  month: string;
  reservedCents: number;
  windowStartedAtMs: number;
  requestsInWindow: number;
  alertSent: boolean;
}

function emptyUsageRecord(month: string, nowMs: number): UsageRecord {
  return {
    month,
    reservedCents: 0,
    windowStartedAtMs: nowMs,
    requestsInWindow: 0,
    alertSent: false,
  };
}

/**
 * Deterministic reference guard for this fixture and its tests. A horizontally
 * scaled deployment must provide the same UsageGuard contract from a shared,
 * transactional store so workspace and service reservations remain atomic.
 */
export class InMemoryUsageGuard implements UsageGuard {
  private readonly workspaceRecords = new Map<string, UsageRecord>();
  private serviceRecord: UsageRecord | undefined;

  constructor(
    private readonly policy: Readonly<SummaryPolicy> = DEFAULT_SUMMARY_POLICY,
    private readonly alertSink: BudgetAlertSink = {
      enqueue: async () => undefined,
    },
    private readonly onAlertFailure: (event: BudgetAlert, error: unknown) => void =
      () => undefined,
  ) {}

  private async emitAlert(event: BudgetAlert): Promise<void> {
    try {
      await this.alertSink.enqueue(event);
    } catch (error) {
      // Budget reservations remain successful and observable even when alert
      // transport is unavailable. Production uses an outbox-backed sink here.
      this.onAlertFailure(event, error);
    }
  }

  async reserve(workspaceId: string, nowMs: number) {
    const month = new Date(nowMs).toISOString().slice(0, 7);
    const previousWorkspace = this.workspaceRecords.get(workspaceId);
    const workspace =
      previousWorkspace?.month === month
        ? previousWorkspace
        : emptyUsageRecord(month, nowMs);
    const service =
      this.serviceRecord?.month === month
        ? this.serviceRecord
        : emptyUsageRecord(month, nowMs);

    if (nowMs - workspace.windowStartedAtMs >= 60_000) {
      workspace.windowStartedAtMs = nowMs;
      workspace.requestsInWindow = 0;
    }

    if (workspace.requestsInWindow >= this.policy.maxRequestsPerMinute) {
      this.workspaceRecords.set(workspaceId, workspace);
      return { allowed: false, reason: "rate_limited" } as const;
    }

    const cost = this.policy.reservedCostPerAttemptCents;
    const nextWorkspaceSpend = workspace.reservedCents + cost;
    const nextServiceSpend = service.reservedCents + cost;
    if (
      nextWorkspaceSpend > this.policy.monthlyBudgetCents ||
      nextServiceSpend > this.policy.serviceMonthlyBudgetCents
    ) {
      this.workspaceRecords.set(workspaceId, workspace);
      this.serviceRecord = service;
      return { allowed: false, reason: "budget_exhausted" } as const;
    }

    // No await occurs before all counters update, so the reservation is atomic
    // within this process. Production implementations transact both records.
    workspace.requestsInWindow += 1;
    workspace.reservedCents = nextWorkspaceSpend;
    service.reservedCents = nextServiceSpend;
    this.workspaceRecords.set(workspaceId, workspace);
    this.serviceRecord = service;

    const alertPercent = this.policy.budgetAlertPercent / 100;
    const alerts: BudgetAlert[] = [];
    if (
      !workspace.alertSent &&
      workspace.reservedCents >= this.policy.monthlyBudgetCents * alertPercent
    ) {
      workspace.alertSent = true;
      alerts.push({
        scope: "workspace",
        workspaceId,
        reservedCents: workspace.reservedCents,
        monthlyBudgetCents: this.policy.monthlyBudgetCents,
      });
    }
    if (
      !service.alertSent &&
      service.reservedCents >= this.policy.serviceMonthlyBudgetCents * alertPercent
    ) {
      service.alertSent = true;
      alerts.push({
        scope: "service",
        reservedCents: service.reservedCents,
        monthlyBudgetCents: this.policy.serviceMonthlyBudgetCents,
      });
    }
    await Promise.all(alerts.map((event) => this.emitAlert(event)));

    return { allowed: true } as const;
  }
}

const CORRECTION_INSTRUCTIONS: Record<CorrectionReason, string> = {
  control_character: "Remove control characters from the summary string.",
  empty_summary: "Return a non-empty summary string.",
  invalid_json: "Return valid JSON without Markdown fences.",
  invalid_shape: "Return only one string field named summary.",
  summary_too_long: "Shorten the summary to the requested limit.",
  unsafe_content: "Remove executable markup, credentials, and unsafe links.",
};

export class AnthropicSummaryProvider implements SummaryProvider {
  private readonly client: Anthropic;

  constructor(apiKey: string | undefined) {
    if (!apiKey) throw new Error("ANTHROPIC_API_KEY is required");
    this.client = new Anthropic({ apiKey });
  }

  async createSummary(
    redactedText: string,
    signal: AbortSignal,
    correction?: CorrectionReason,
  ): Promise<string> {
    const correctionInstruction = correction
      ? ` Correct the previous ${correction} failure: ${CORRECTION_INSTRUCTIONS[correction]}`
      : "";
    const response = await this.client.messages.create(
      {
        model: "claude-sonnet-4-5",
        max_tokens: 300,
        system:
          `[${SUMMARY_PROMPT_VERSION}] Return exactly one JSON object with one string field named summary. ` +
          "Do not include links, executable markup, credentials, or additional fields." +
          correctionInstruction,
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

type ValidationResult =
  | { valid: true; summary: string }
  | { valid: false; correction: CorrectionReason };

function degraded(reason: SummaryFailureReason): SummaryResult {
  return { status: "degraded", summary: null, reason, needsHumanReview: true };
}

function validateSummary(raw: string, maxCharacters: number): ValidationResult {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return { valid: false, correction: "invalid_json" };
  }

  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { valid: false, correction: "invalid_shape" };
  }
  const record = value as Record<string, unknown>;
  if (Object.keys(record).length !== 1 || typeof record.summary !== "string") {
    return { valid: false, correction: "invalid_shape" };
  }

  const summary = record.summary.trim();
  if (!summary) return { valid: false, correction: "empty_summary" };
  if (summary.length > maxCharacters) {
    return { valid: false, correction: "summary_too_long" };
  }
  if (/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/.test(summary)) {
    return { valid: false, correction: "control_character" };
  }
  if (UNSAFE_OUTPUT.some((pattern) => pattern.test(summary))) {
    return { valid: false, correction: "unsafe_content" };
  }
  return { valid: true, summary };
}

async function callWithTimeout(
  provider: SummaryProvider,
  text: string,
  timeoutMs: number,
  correction?: CorrectionReason,
): Promise<string> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      provider.createSummary(text, controller.signal, correction),
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
  let correction: CorrectionReason | undefined;
  for (let attempt = 0; attempt <= policy.correctiveRetries; attempt += 1) {
    const reservation = await dependencies.usageGuard.reserve(workspaceId, now());
    if (!reservation.allowed) return degraded(reservation.reason);

    let raw: string;
    try {
      raw = await callWithTimeout(
        dependencies.provider,
        redactedText,
        policy.providerTimeoutMs,
        correction,
      );
    } catch {
      return degraded("provider_failure");
    }

    const validation = validateSummary(raw, policy.maxSummaryCharacters);
    if (validation.valid) {
      return {
        status: "ok",
        summary: validation.summary,
        needsHumanReview: false,
      };
    }
    correction = validation.correction;
  }

  return degraded("invalid_output");
}
