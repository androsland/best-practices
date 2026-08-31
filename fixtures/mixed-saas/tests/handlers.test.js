const assert = require("node:assert/strict");
const { describe, it, mock } = require("node:test");
const {
  MAX_PROJECT_PAGE_SIZE,
  createLoginHandler,
  createProjectsHandler,
  createWebhookHandler,
} = require("../src/handlers");

function responseRecorder() {
  return {
    statusCode: undefined,
    body: undefined,
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(body) {
      this.body = body;
      return this;
    },
  };
}

describe("login handler", () => {
  it("covers successful, denied, and provider-failure paths", async () => {
    for (const testCase of [
      { authenticate: async () => true, status: 200, body: { ok: true } },
      {
        authenticate: async () => false,
        status: 401,
        body: { error: "invalid_credentials" },
      },
      {
        authenticate: async () => {
          throw new Error("provider unavailable");
        },
        status: 503,
        body: { error: "authentication_unavailable" },
      },
    ]) {
      const response = responseRecorder();
      await createLoginHandler({ authenticate: testCase.authenticate })(
        { body: { email: "user@example.test", password: "fixture-password" } },
        response,
      );
      assert.equal(response.statusCode, testCase.status);
      assert.deepEqual(response.body, testCase.body);
    }
  });
});

describe("webhook handler", () => {
  it("covers successful, rejected, and fulfillment-failure paths", async () => {
    const fulfillOrder = mock.fn(async () => undefined);
    const accepted = responseRecorder();
    await createWebhookHandler({ fulfillOrder })(
      { body: { event_id: "evt_123" } },
      accepted,
    );
    assert.equal(accepted.statusCode, 200);
    assert.deepEqual(accepted.body, { received: true });
    assert.equal(fulfillOrder.mock.callCount(), 1);

    const rejected = responseRecorder();
    await createWebhookHandler({ fulfillOrder })({ body: {} }, rejected);
    assert.equal(rejected.statusCode, 400);
    assert.deepEqual(rejected.body, { error: "invalid_event" });
    assert.equal(fulfillOrder.mock.callCount(), 1);

    const failed = responseRecorder();
    await createWebhookHandler({
      fulfillOrder: async () => {
        throw new Error("database unavailable");
      },
    })({ body: { event_id: "evt_456" } }, failed);
    assert.equal(failed.statusCode, 500);
    assert.deepEqual(failed.body, { error: "fulfillment_failed" });
  });
});

describe("projects handler", () => {
  it("caps page size and returns a cursor instead of an unbounded result", async () => {
    const records = Array.from(
      { length: MAX_PROJECT_PAGE_SIZE + 1 },
      (_, index) => ({ id: `project-${index + 1}` }),
    );
    const findProjects = mock.fn(async () => records);
    const response = responseRecorder();

    await createProjectsHandler({ findProjects })(
      { query: { tenant_id: "tenant-1", limit: "1000", cursor: "project-0" } },
      response,
    );

    assert.equal(response.statusCode, 200);
    assert.equal(response.body.items.length, MAX_PROJECT_PAGE_SIZE);
    assert.equal(response.body.next_cursor, "project-100");
    assert.deepEqual(findProjects.mock.calls[0].arguments[0], {
      where: { tenant_id: "tenant-1" },
      take: MAX_PROJECT_PAGE_SIZE + 1,
      cursor: { id: "project-0" },
      skip: 1,
    });
  });
});
