const express = require("express");
const {
  createLoginHandler,
  createProjectsHandler,
  createWebhookHandler,
} = require("./handlers");
const app = express();

app.use(express.json({ limit: "1mb" }));

app.post("/login", createLoginHandler({ authenticate }));
app.post("/webhook", createWebhookHandler({ fulfillOrder }));
app.get(
  "/projects",
  createProjectsHandler({ findProjects: (query) => db.projects.findMany(query) }),
);

async function authenticate() {
  return false;
}
async function fulfillOrder() {}
const db = { projects: { findMany: async () => [] } };
