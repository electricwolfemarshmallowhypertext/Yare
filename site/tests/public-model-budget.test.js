const test = require("node:test");
const assert = require("node:assert/strict");
const budget = require("../api/lib/public-model-budget");
const { createHandler } = require("../api/model-preview");

function fakeResponse() {
  return {
    statusCode: 200,
    setHeader() {},
    end(text) { this.body = JSON.parse(text); }
  };
}

function fakePool(allow = true) {
  const statements = [];
  const query = async (sql) => {
    statements.push(sql.trim());
    if (sql.includes("UPDATE yare_public_model_budgets") && sql.includes("RETURNING")) {
      return { rows: allow ? [{ budget_id: "test" }] : [] };
    }
    if (sql.includes("UPDATE yare_public_model_calls") && sql.includes("RETURNING")) {
      return { rows: [{ request_id: "test" }] };
    }
    return { rows: [] };
  };
  return {
    statements,
    query,
    connect: async () => ({ query, release() { statements.push("RELEASE"); } })
  };
}

const enabledEnv = {
  YARE_PUBLIC_MODEL_ENABLED: "true",
  YARE_DATABASE_URL: "postgresql://redacted",
  YARE_DATABASE_CA_PEM: "test-ca",
  NEBIUS_API_KEY: "test-secret",
  YARE_PUBLIC_BUDGET_ID: "test",
  YARE_PUBLIC_MODEL_ID: "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
  YARE_PUBLIC_INPUT_CEILING_USD_PER_MILLION: "0.06",
  YARE_PUBLIC_OUTPUT_CEILING_USD_PER_MILLION: "0.24"
};

test("quotes are bounded and use integer microdollars", () => {
  assert.equal(budget.parseRate("0.06"), 60000);
  assert.equal(budget.parseRate("0.24"), 240000);
  assert.equal(budget.quote("hello", 60000, 240000).tokenBound, 8709);
  assert.throws(() => budget.quote("x".repeat(4097), 60000, 240000));
  assert.throws(() => budget.parseRate("0"));
});

test("reservation updates the cap before inserting the call and commits once", async () => {
  const db = fakePool();
  const bound = budget.quote("hello", 60000, 240000);
  await budget.reserve(db, "request", "test", "nano", bound, 60000, 240000);
  assert.deepEqual(db.statements.map(s => s.split(/\s+/)[0]),
    ["BEGIN", "UPDATE", "INSERT", "COMMIT", "RELEASE"]);
  assert.match(db.statements[1], /charged_usd_micros \+ \$3 <= limit_usd_micros/);
  assert.match(db.statements[1], /tokens_charged \+ \$2 <= max_tokens/);
});

test("missing or exhausted budget rolls back without a call row", async () => {
  const db = fakePool(false);
  await assert.rejects(budget.reserve(db, "request", "test", "nano",
    budget.quote("hello", 60000, 240000), 60000, 240000));
  assert.deepEqual(db.statements.map(s => s.split(/\s+/)[0]),
    ["BEGIN", "UPDATE", "ROLLBACK", "RELEASE"]);
});

test("observed usage records cost without refunding the global reservation", async () => {
  const db = fakePool();
  const bound = budget.quote("hello", 60000, 240000);
  await budget.settle(db, "request", { prompt_tokens: 10, completion_tokens: 20 },
    bound, 60000, 240000);
  assert.equal(db.statements.length, 1);
  assert.match(db.statements[0], /UPDATE yare_public_model_calls/);
  await assert.rejects(budget.settle(db, "request", { prompt_tokens: 10,
    completion_tokens: 513 }, bound, 60000, 240000));
});

test("endpoint is disabled without touching storage or provider", async () => {
  let called = false;
  const handler = createHandler({ env: {}, poolFor: () => { called = true; },
    fetchFn: () => { called = true; } });
  const res = fakeResponse();
  await handler({ method: "POST", body: { prompt: "hi" } }, res);
  assert.equal(res.statusCode, 503);
  assert.equal(called, false);
});

test("no budget row means no provider request", async () => {
  let providerCalled = false;
  const db = fakePool(false);
  const handler = createHandler({ env: enabledEnv, poolFor: () => db,
    fetchFn: () => { providerCalled = true; } });
  const res = fakeResponse();
  await handler({ method: "POST", body: { prompt: "hi" } }, res);
  assert.equal(res.statusCode, 503);
  assert.equal(providerCalled, false);
});

test("invalid or oversized prompts never reach storage or provider", async () => {
  let called = false;
  const handler = createHandler({ env: enabledEnv, poolFor: () => { called = true; },
    fetchFn: () => { called = true; } });
  for (const body of [{ prompt: "x".repeat(4097) }, { prompt: "ok", model: "other" },
    { prompt: "" }]) {
    const res = fakeResponse();
    await handler({ method: "POST", body }, res);
    assert.equal(res.statusCode, 400);
  }
  assert.equal(called, false);
});

test("missing configuration never reaches storage or provider", async () => {
  let called = false;
  const handler = createHandler({ env: { YARE_PUBLIC_MODEL_ENABLED: "true" },
    poolFor: () => { called = true; }, fetchFn: () => { called = true; } });
  const res = fakeResponse();
  await handler({ method: "POST", body: { prompt: "hi" } }, res);
  assert.equal(res.statusCode, 503);
  assert.equal(called, false);
});

test("enabled fixture reserves, calls the provider, then settles", async () => {
  const db = fakePool();
  let providerCalled = false;
  const handler = createHandler({ env: enabledEnv, poolFor: () => db,
    fetchFn: async (_url, options) => {
      providerCalled = true;
      assert.match(options.headers.authorization, /^Bearer test-secret$/);
      return { ok: true, json: async () => ({ usage: { prompt_tokens: 10,
        completion_tokens: 5 }, choices: [{ message: { content: "response" } }] }) };
    } });
  const res = fakeResponse();
  await handler({ method: "POST", body: { prompt: "hi" } }, res);
  assert.equal(res.statusCode, 200);
  assert.equal(providerCalled, true);
  assert.equal(res.body.content, "response");
  assert.equal(JSON.stringify(res.body).includes("test-secret"), false);
  assert.equal(db.statements.some(s => s.includes("status = 'observed'")), true);
});

test("unknown provider usage blocks future calls and retains reservation", async () => {
  const db = fakePool();
  const handler = createHandler({ env: enabledEnv, poolFor: () => db,
    fetchFn: async () => { throw new Error("transport interrupted"); } });
  const res = fakeResponse();
  await handler({ method: "POST", body: { prompt: "hi" } }, res);
  assert.equal(res.statusCode, 502);
  assert.equal(db.statements.some(s => s.includes("SET blocked = true")), true);
});
