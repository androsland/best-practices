import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

export async function summarize(redactedText: string) {
  return client.messages.create({ model: "claude-sonnet-4-5", max_tokens: 300, messages: [{ role: "user", content: redactedText }] });
}
