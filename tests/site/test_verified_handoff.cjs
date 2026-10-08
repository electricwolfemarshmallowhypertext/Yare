const assert = require("node:assert/strict");
const test = require("node:test");
const published = require("../../site/public-upgrade-handoff.json");
const { createHandler } = require("../../site/api/verified-handoff.js");

function response() {
  return {
    statusCode: 0,
    headers: {},
    setHeader(key, value) { this.headers[key] = value; },
    end(value) { this.body = JSON.parse(value); }
  };
}

test("upgrade endpoint is off without an explicit enable flag", async () => {
  const res = response();
  await createHandler({ env: {}, poolFor() { throw Error("must not connect"); } })(
    { method: "GET" }, res);
  assert.equal(res.statusCode, 503);
  assert.equal(res.body.error, "upgrade handoff not published");
});

test("only exact approved state and receipt pairs are returned", async () => {
  const seen = [];
  const db = { async query(sql, params) {
    seen.push(params);
    assert.match(sql, /JOIN yare_receipts/);
    return { rows: [{
      run_id: params[0], current_state_hash: params[1],
      receipt_hash: params[2], created_at: new Date("2026-10-07T00:00:00Z"),
      state_json: { private_path: "do not publish" }, has_access_evidence: true
    }] };
  } };
  const res = response();
  await createHandler({
    env: { YARE_PUBLIC_UPGRADE_ENABLED: "true", YARE_DATABASE_URL: "test-url" },
    poolFor: () => db
  })({ method: "GET" }, res);
  assert.equal(res.statusCode, 200);
  assert.deepEqual(seen, [
    [published.a.run_id, published.a.current_state_hash, published.a.receipt_hash],
    [published.b.run_id, published.b.current_state_hash, published.b.receipt_hash]
  ]);
  assert.equal(res.body.b.receipt_hash, published.b.receipt_hash);
  assert.ok(!JSON.stringify(res.body).includes("do not publish"));
});

test("a missing approved record fails closed", async () => {
  const res = response();
  await createHandler({
    env: { YARE_PUBLIC_UPGRADE_ENABLED: "true", YARE_DATABASE_URL: "test-url" },
    poolFor: () => ({ query: async () => ({ rows: [] }) })
  })({ method: "GET" }, res);
  assert.equal(res.statusCode, 404);
});

test("a receipt without access evidence fails closed", async () => {
  const res = response();
  await createHandler({
    env: { YARE_PUBLIC_UPGRADE_ENABLED: "true", YARE_DATABASE_URL: "test-url" },
    poolFor: () => ({ query: async (_sql, params) => ({ rows: [{
      run_id: params[0], current_state_hash: params[1], receipt_hash: params[2],
      state_json: {}, has_access_evidence: false
    }] }) })
  })({ method: "GET" }, res);
  assert.equal(res.statusCode, 404);
});
