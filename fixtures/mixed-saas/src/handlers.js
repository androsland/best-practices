const DEFAULT_PROJECT_PAGE_SIZE = 25;
const MAX_PROJECT_PAGE_SIZE = 100;

function createLoginHandler({ authenticate }) {
  return async function login(request, response) {
    const email = request.body?.email;
    const password = request.body?.password;
    if (typeof email !== "string" || typeof password !== "string") {
      return response.status(400).json({ error: "invalid_credentials" });
    }

    try {
      const authenticated = await authenticate({ email, password });
      if (!authenticated) {
        return response.status(401).json({ error: "invalid_credentials" });
      }
      return response.status(200).json({ ok: true });
    } catch {
      return response.status(503).json({ error: "authentication_unavailable" });
    }
  };
}

function createWebhookHandler({ fulfillOrder }) {
  return async function webhook(request, response) {
    const eventId = request.body?.event_id;
    if (typeof eventId !== "string" || !eventId.trim()) {
      return response.status(400).json({ error: "invalid_event" });
    }

    try {
      await fulfillOrder(request.body);
      return response.status(200).json({ received: true });
    } catch {
      return response.status(500).json({ error: "fulfillment_failed" });
    }
  };
}

function parsePageSize(value) {
  if (value === undefined) return DEFAULT_PROJECT_PAGE_SIZE;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) return null;
  return Math.min(parsed, MAX_PROJECT_PAGE_SIZE);
}

function createProjectsHandler({ findProjects }) {
  return async function projects(request, response) {
    const tenantId = request.query.tenant_id;
    const cursor = request.query.cursor;
    const pageSize = parsePageSize(request.query.limit);
    if (
      typeof tenantId !== "string" ||
      !tenantId.trim() ||
      (cursor !== undefined && typeof cursor !== "string") ||
      pageSize === null
    ) {
      return response.status(400).json({ error: "invalid_query" });
    }

    try {
      const records = await findProjects({
        where: { tenant_id: tenantId },
        take: pageSize + 1,
        ...(cursor ? { cursor: { id: cursor }, skip: 1 } : {}),
      });
      const hasNextPage = records.length > pageSize;
      const items = records.slice(0, pageSize);
      return response.status(200).json({
        items,
        next_cursor: hasNextPage ? items.at(-1)?.id ?? null : null,
      });
    } catch {
      return response.status(500).json({ error: "projects_unavailable" });
    }
  };
}

module.exports = {
  DEFAULT_PROJECT_PAGE_SIZE,
  MAX_PROJECT_PAGE_SIZE,
  createLoginHandler,
  createProjectsHandler,
  createWebhookHandler,
};
