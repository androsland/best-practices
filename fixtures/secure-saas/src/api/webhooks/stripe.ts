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
    insert(value: { event_id: string; unique: true }): Promise<
      "inserted" | "duplicate"
    >;
  };
  queue: {
    publish(value: { eventId: string; type: string }): Promise<void>;
  };
}

export interface StripeWebhookRequest {
  method: string;
  rawBody: string;
  signature?: string;
}

export interface StripeWebhookResponse {
  status: 200 | 202 | 400 | 405 | 500 | 503;
  headers: Readonly<Record<string, string>>;
  body:
    | { received: true; duplicate: boolean }
    | { error: { code: string; message: string } };
}

export const MAX_WEBHOOK_BODY_CHARACTERS = 1_000_000;
const JSON_HEADERS = Object.freeze({ "content-type": "application/json" });

class WebhookConfigurationError extends Error {}
class WebhookSignatureError extends Error {}

export async function receiveStripeWebhook(
  rawBody: string,
  signature: string,
  dependencies: StripeWebhookDependencies,
) {
  if (!dependencies.webhookSecret) {
    throw new WebhookConfigurationError("webhook secret is required");
  }

  // Stripe's verifier throws before either side effect when the signature is bad.
  let event: { id: string; type: string };
  try {
    event = dependencies.stripe.webhooks.constructEvent(
      rawBody,
      signature,
      dependencies.webhookSecret,
    );
  } catch {
    throw new WebhookSignatureError("invalid webhook signature");
  }
  const insertion = await dependencies.processedEvents.insert({
    event_id: event.id,
    unique: true,
  });
  if (insertion === "duplicate") return { duplicate: true } as const;
  await dependencies.queue.publish({ eventId: event.id, type: event.type });
  return { duplicate: false } as const;
}

function errorResponse(
  status: StripeWebhookResponse["status"],
  code: string,
  message: string,
): StripeWebhookResponse {
  return { status, headers: JSON_HEADERS, body: { error: { code, message } } };
}

export async function handleStripeWebhook(
  request: StripeWebhookRequest,
  dependencies: StripeWebhookDependencies,
): Promise<StripeWebhookResponse> {
  if (request.method !== "POST") {
    return errorResponse(405, "method_not_allowed", "POST is required.");
  }
  if (
    !request.rawBody ||
    request.rawBody.length > MAX_WEBHOOK_BODY_CHARACTERS ||
    !request.signature
  ) {
    return errorResponse(
      400,
      "invalid_request",
      "A bounded raw body and Stripe-Signature header are required.",
    );
  }
  try {
    const result = await receiveStripeWebhook(
      request.rawBody,
      request.signature,
      dependencies,
    );
    return {
      status: result.duplicate ? 200 : 202,
      headers: JSON_HEADERS,
      body: { received: true, duplicate: result.duplicate },
    };
  } catch (error) {
    if (error instanceof WebhookSignatureError) {
      return errorResponse(400, "invalid_signature", "Signature verification failed.");
    }
    if (error instanceof WebhookConfigurationError) {
      return errorResponse(503, "webhook_unavailable", "Webhook processing is unavailable.");
    }
    return errorResponse(500, "webhook_processing_failed", "Webhook processing failed.");
  }
}
