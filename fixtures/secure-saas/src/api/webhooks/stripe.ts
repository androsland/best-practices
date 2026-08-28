import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

export async function receiveStripeWebhook(rawBody: string, signature: string) {
  const event = stripe.webhooks.constructEvent(
    rawBody,
    signature,
    process.env.STRIPE_WEBHOOK_SECRET!,
  );
  await db.processed_events.insert({ event_id: event.id, unique: true });
  await queue.publish({ eventId: event.id, type: event.type });
}

declare const db: { processed_events: { insert(value: object): Promise<void> } };
declare const queue: { publish(value: object): Promise<void> };
