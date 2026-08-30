import { describe, expect, it, vi } from "vitest";
import {
  handleStripeWebhook,
  receiveStripeWebhook,
  type StripeWebhookDependencies,
} from "../src/api/webhooks/stripe";

function dependencies(
  overrides: Partial<StripeWebhookDependencies> = {},
): StripeWebhookDependencies {
  return {
    stripe: {
      webhooks: {
        constructEvent: () => ({ id: "evt_fixture", type: "invoice.paid" }),
      },
    },
    webhookSecret: "fixture-secret",
    processedEvents: { insert: async () => "inserted" },
    queue: { publish: async () => undefined },
    ...overrides,
  };
}

describe("webhook", () => {
  it("rejects an invalid signature before publishing or recording the event", async () => {
    const insert = vi.fn();
    const publish = vi.fn();
    const verify = vi.fn(() => {
      throw new Error("invalid signature");
    });

    await expect(
      receiveStripeWebhook("raw body", "bad signature", {
        stripe: { webhooks: { constructEvent: verify } },
        webhookSecret: "fixture-secret",
        processedEvents: { insert },
        queue: { publish },
      }),
    ).rejects.toThrow();

    expect(verify).toHaveBeenCalledOnce();
    expect(insert).not.toHaveBeenCalled();
    expect(publish).not.toHaveBeenCalled();
  });

  it("records a verified event before publishing it", async () => {
    const order: string[] = [];
    const insert = vi.fn(async () => {
      order.push("insert");
      return "inserted" as const;
    });
    const publish = vi.fn(async () => {
      order.push("publish");
    });

    await receiveStripeWebhook("raw body", "valid signature", {
      stripe: {
        webhooks: {
          constructEvent: () => ({ id: "evt_fixture", type: "invoice.paid" }),
        },
      },
      webhookSecret: "fixture-secret",
      processedEvents: { insert },
      queue: { publish },
    });

    expect(order).toEqual(["insert", "publish"]);
    expect(insert).toHaveBeenCalledWith({ event_id: "evt_fixture", unique: true });
    expect(publish).toHaveBeenCalledWith({
      eventId: "evt_fixture",
      type: "invoice.paid",
    });
  });

  it("does not publish when durable duplicate detection rejects", async () => {
    const publish = vi.fn(async () => undefined);
    await expect(
      receiveStripeWebhook("raw body", "valid signature", {
        stripe: {
          webhooks: {
            constructEvent: () => ({ id: "evt_duplicate", type: "invoice.paid" }),
          },
        },
        webhookSecret: "fixture-secret",
        processedEvents: {
          insert: vi.fn(async () => "duplicate" as const),
        },
        queue: { publish },
      }),
    ).resolves.toEqual({ duplicate: true });

    expect(publish).not.toHaveBeenCalled();
  });

  it("rejects a missing webhook secret before verification", async () => {
    const verify = vi.fn();
    await expect(
      receiveStripeWebhook("raw body", "signature", {
        stripe: { webhooks: { constructEvent: verify } },
        webhookSecret: "",
        processedEvents: { insert: vi.fn() },
        queue: { publish: vi.fn() },
      }),
    ).rejects.toThrow();

    expect(verify).not.toHaveBeenCalled();
  });

  it.each([
    {
      name: "accepted event",
      request: { method: "POST", rawBody: "raw", signature: "valid" },
      deps: dependencies(),
      status: 202,
      body: { received: true, duplicate: false },
    },
    {
      name: "duplicate event",
      request: { method: "POST", rawBody: "raw", signature: "valid" },
      deps: dependencies({
        processedEvents: { insert: async () => "duplicate" as const },
      }),
      status: 200,
      body: { received: true, duplicate: true },
    },
    {
      name: "invalid signature",
      request: { method: "POST", rawBody: "raw", signature: "invalid" },
      deps: dependencies({
        stripe: {
          webhooks: {
            constructEvent: () => {
              throw new Error("provider detail");
            },
          },
        },
      }),
      status: 400,
      body: {
        error: {
          code: "invalid_signature",
          message: "Signature verification failed.",
        },
      },
    },
    {
      name: "missing secret",
      request: { method: "POST", rawBody: "raw", signature: "valid" },
      deps: dependencies({ webhookSecret: "" }),
      status: 503,
      body: {
        error: {
          code: "webhook_unavailable",
          message: "Webhook processing is unavailable.",
        },
      },
    },
    {
      name: "internal failure",
      request: { method: "POST", rawBody: "raw", signature: "valid" },
      deps: dependencies({
        processedEvents: {
          insert: async () => {
            throw new Error("database detail");
          },
        },
      }),
      status: 500,
      body: {
        error: {
          code: "webhook_processing_failed",
          message: "Webhook processing failed.",
        },
      },
    },
  ])("maps $name to a stable HTTP contract", async ({ request, deps, status, body }) => {
    const response = await handleStripeWebhook(request, deps);
    expect(response.status).toBe(status);
    expect(response.headers).toEqual({ "content-type": "application/json" });
    expect(response.body).toEqual(body);
    expect(JSON.stringify(response)).not.toContain("detail");
  });

  it("rejects unsupported methods and malformed requests before verification", async () => {
    const verify = vi.fn(() => ({ id: "evt_fixture", type: "invoice.paid" }));
    const deps = dependencies({ stripe: { webhooks: { constructEvent: verify } } });

    await expect(
      handleStripeWebhook({ method: "GET", rawBody: "", signature: undefined }, deps),
    ).resolves.toMatchObject({
      status: 405,
      body: { error: { code: "method_not_allowed" } },
    });
    await expect(
      handleStripeWebhook({ method: "POST", rawBody: "", signature: undefined }, deps),
    ).resolves.toMatchObject({
      status: 400,
      body: { error: { code: "invalid_request" } },
    });
    expect(verify).not.toHaveBeenCalled();
  });
});
