const test = require("node:test");
const assert = require("node:assert/strict");
const { summarizeLedger, seedBlockedBudget } = require("../api/lib/public-model-ledger");

test("summarizes charges without changing ledger entries", () => {
  const state = { limit_usd: "5", max_calls: 500, max_tokens: 2000000,
    calls: [{ charged_tokens: 10, charged_usd: "0.00000001" },
      { charged_tokens: 20, charged_usd: "0.00000001" }] };
  const before = JSON.stringify(state);
  const result = summarizeLedger(state);
  assert.equal(result.calls_used, 2);
  assert.equal(result.tokens_charged, 30);
  assert.equal(result.charged_usd_exact, "0.00000002");
  assert.equal(result.charged_usd_micros, 1);
  assert.equal(result.limit_usd_micros, 5000000);
  assert.equal(JSON.stringify(state), before);
});

test("never increases the existing global caps", () => {
  const result = summarizeLedger({ limit_usd: "9", max_calls: 999,
    max_tokens: 9000000, calls: [] });
  assert.equal(result.max_calls, 500);
  assert.equal(result.max_tokens, 2000000);
  assert.equal(result.limit_usd_micros, 5000000);
});

test("rejects invalid and over-limit ledgers", () => {
  assert.throws(() => summarizeLedger({ limit_usd: "5", max_calls: 1,
    max_tokens: 100, calls: [{ charged_tokens: 101, charged_usd: "0.01" }] }));
  assert.throws(() => summarizeLedger({ limit_usd: "secret", max_calls: 1,
    max_tokens: 100, calls: [] }));
  assert.throws(() => summarizeLedger({ limit_usd: "5", max_calls: 1,
    max_tokens: 100, calls: [{ charged_tokens: -1, charged_usd: "0" }] }));
});

test("blocked seed preserves counters and never overwrites an existing row", async () => {
  const summary = summarizeLedger({ limit_usd: "5", max_calls: 500,
    max_tokens: 2000000, calls: [{ charged_tokens: 20, charged_usd: "0.01" }] });
  let parameters;
  const pool = { query: async (sql, values) => {
    assert.match(sql, /blocked\)\s+VALUES \([^)]*true\)/);
    assert.match(sql, /ON CONFLICT \(budget_id\) DO NOTHING/);
    parameters = values;
    return { rows: [{ budget_id: "test" }] };
  } };
  await seedBlockedBudget(pool, "test", summary);
  assert.deepEqual(parameters, ["test", 5000000, 500, 2000000, 10000, 1, 20]);
  await assert.rejects(seedBlockedBudget({ query: async () => ({ rows: [] }) },
    "test", summary), /already exists/);
  await assert.rejects(seedBlockedBudget(pool, "bad/id", summary), /Invalid budget ID/);
});
