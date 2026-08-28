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
});
