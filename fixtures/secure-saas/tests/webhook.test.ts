import { describe, expect, it, vi } from "vitest";
import { receiveStripeWebhook } from "../src/api/webhooks/stripe";

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
    const publish = vi.fn();
    await expect(
      receiveStripeWebhook("raw body", "valid signature", {
        stripe: {
          webhooks: {
            constructEvent: () => ({ id: "evt_duplicate", type: "invoice.paid" }),
          },
        },
        webhookSecret: "fixture-secret",
        processedEvents: {
          insert: vi.fn(async () => {
            throw new Error("unique violation");
          }),
        },
        queue: { publish },
      }),
    ).rejects.toThrow();

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
});
