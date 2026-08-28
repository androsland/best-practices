export interface StripeWebhookDependencies {
  stripe: {
    webhooks: {
      constructEvent(
        rawBody: string,
        signature: string,
        secret: string,
      ): { id: string; type: string };
    };
  };
  webhookSecret: string;
  processedEvents: {
    insert(value: { event_id: string; unique: true }): Promise<void>;
  };
  queue: {
    publish(value: { eventId: string; type: string }): Promise<void>;
  };
}

export async function receiveStripeWebhook(
  rawBody: string,
  signature: string,
  dependencies: StripeWebhookDependencies,
) {
  if (!dependencies.webhookSecret) throw new Error("webhook secret is required");

  // Stripe's verifier throws before either side effect when the signature is bad.
  const event = dependencies.stripe.webhooks.constructEvent(
    rawBody,
    signature,
    dependencies.webhookSecret,
  );
  await dependencies.processedEvents.insert({ event_id: event.id, unique: true });
  await dependencies.queue.publish({ eventId: event.id, type: event.type });
}
