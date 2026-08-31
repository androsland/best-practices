const express = require("express");
const app = express();

app.post("/login", async (request, response) => response.json({ ok: true }));

app.post("/webhook", async (request, response) => {
  await fulfillOrder(request.body);
  response.json({ received: true });
});

app.get("/projects", async (request, response) => {
  const tenant_id = request.query.tenant_id;
  response.json(await db.projects.findMany({ tenant_id }));
});

async function fulfillOrder() {}
const db = { projects: { findMany: async () => [] } };
