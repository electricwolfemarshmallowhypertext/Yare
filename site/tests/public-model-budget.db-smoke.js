const assert = require("node:assert/strict");
const { randomUUID } = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { Pool } = require("pg");
const budget = require("../api/lib/public-model-budget");
const { summarizeLedger, seedBlockedBudget } = require("../api/lib/public-model-ledger");
const { createHandler } = require("../api/model-preview");

function databaseUrl() {
  const settings = fs.readFileSync(path.resolve(__dirname, "../../.env.nebius"), "utf8");
  const line = settings.split(/\r?\n/).find(value => /^YARE_DATABASE_URL=/.test(value));
  if (!line) throw new Error("YARE_DATABASE_URL missing from ignored local settings");
  return line.slice("YARE_DATABASE_URL=".length).trim().replace(/^['"]|['"]$/g, "");
}

async function main() {
  const ca = fs.readFileSync(path.join(process.env.APPDATA, "postgresql", "root.crt"), "utf8");
  const pool = new Pool({ connectionString: databaseUrl(), ssl: { ca, rejectUnauthorized: true }, max: 4 });
  const budgetId = `smoke-${randomUUID()}`;
  const endpointId = `smoke-${randomUUID()}`;
  const seedId = `smoke-${randomUUID()}`;
  const bound = budget.quote("budget smoke", 60000, 240000);
  try {
    const schema = fs.readFileSync(path.resolve(__dirname, "../schema/public-model-budget.sql"), "utf8");
    await pool.query(schema);
    await pool.query(`
      INSERT INTO yare_public_model_budgets
        (budget_id, limit_usd_micros, max_calls, max_tokens, blocked)
      VALUES ($1, $2, 1, $3, false)
    `, [budgetId, bound.usdMicros, bound.tokenBound]);
    const attempts = await Promise.allSettled([randomUUID(), randomUUID()].map(requestId =>
      budget.reserve(pool, requestId, budgetId, "nano", bound, 60000, 240000)));
    assert.equal(attempts.filter(result => result.status === "fulfilled").length, 1);
    const row = (await pool.query(`
      SELECT calls_used, tokens_charged, charged_usd_micros
      FROM yare_public_model_budgets WHERE budget_id = $1
    `, [budgetId])).rows[0];
    assert.equal(Number(row.calls_used), 1);
    assert.equal(Number(row.tokens_charged), bound.tokenBound);
    assert.equal(Number(row.charged_usd_micros), bound.usdMicros);
    const count = (await pool.query(`
      SELECT count(*) AS n FROM yare_public_model_calls WHERE budget_id = $1
    `, [budgetId])).rows[0].n;
    assert.equal(Number(count), 1);
    const reserved = (await pool.query(`
      SELECT request_id FROM yare_public_model_calls WHERE budget_id = $1
    `, [budgetId])).rows[0];
    await budget.block(pool, budgetId, reserved.request_id);
    const blocked = (await pool.query(`
      SELECT blocked, calls_used, tokens_charged, charged_usd_micros
      FROM yare_public_model_budgets WHERE budget_id = $1
    `, [budgetId])).rows[0];
    assert.equal(blocked.blocked, true);
    assert.equal(Number(blocked.calls_used), 1);
    assert.equal(Number(blocked.tokens_charged), bound.tokenBound);
    assert.equal(Number(blocked.charged_usd_micros), bound.usdMicros);
    const call = (await pool.query(`
      SELECT status FROM yare_public_model_calls WHERE request_id = $1
    `, [reserved.request_id])).rows[0];
    assert.equal(call.status, "usage_unknown");
    await assert.rejects(budget.reserve(pool, randomUUID(), budgetId, "nano", bound, 60000, 240000));
    await pool.query(`
      INSERT INTO yare_public_model_budgets
        (budget_id, limit_usd_micros, max_calls, max_tokens, blocked)
      VALUES ($1, $2, 1, $3, false)
    `, [endpointId, bound.usdMicros, bound.tokenBound]);
    let providerCalls = 0;
    const handler = createHandler({
      env: {
        YARE_PUBLIC_MODEL_ENABLED: "true",
        YARE_DATABASE_URL: "fixture-only",
        YARE_DATABASE_CA_PEM: "fixture-only",
        NEBIUS_API_KEY: "fixture-only",
        YARE_PUBLIC_BUDGET_ID: endpointId,
        YARE_PUBLIC_MODEL_ID: "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
        YARE_PUBLIC_INPUT_CEILING_USD_PER_MILLION: "0.06",
        YARE_PUBLIC_OUTPUT_CEILING_USD_PER_MILLION: "0.24"
      },
      poolFor: () => pool,
      fetchFn: async () => {
        providerCalls++;
        return { ok: true, json: async () => ({
          usage: { prompt_tokens: 10, completion_tokens: 5 },
          choices: [{ message: { content: "fixture response" } }]
        }) };
      }
    });
    const response = () => ({ statusCode: 200, setHeader() {},
      end(value) { this.body = JSON.parse(value); } });
    const first = response();
    await handler({ method: "POST", body: { prompt: "budget smoke" } }, first);
    assert.equal(first.statusCode, 200);
    assert.equal(first.body.content, "fixture response");
    const second = response();
    await handler({ method: "POST", body: { prompt: "budget smoke" } }, second);
    assert.equal(second.statusCode, 503);
    assert.equal(providerCalls, 1);
    const endpointCall = (await pool.query(`
      SELECT status FROM yare_public_model_calls WHERE budget_id = $1
    `, [endpointId])).rows;
    assert.deepEqual(endpointCall.map(row => row.status), ["observed"]);
    const seed = summarizeLedger({ limit_usd: "5", max_calls: 500,
      max_tokens: 2000000, calls: [{ charged_tokens: 20, charged_usd: "0.01" }] });
    await seedBlockedBudget(pool, seedId, seed);
    const seeded = (await pool.query(`
      SELECT blocked, calls_used, tokens_charged, charged_usd_micros
      FROM yare_public_model_budgets WHERE budget_id = $1
    `, [seedId])).rows[0];
    assert.equal(seeded.blocked, true);
    assert.equal(Number(seeded.calls_used), 1);
    assert.equal(Number(seeded.tokens_charged), 20);
    assert.equal(Number(seeded.charged_usd_micros), 10000);
    await assert.rejects(seedBlockedBudget(pool, seedId, seed));
    process.stdout.write("Cockroach budget: PASS (concurrency, unknown-usage block, endpoint cap, blocked seed)\n");
  } finally {
    try {
      for (const id of [budgetId, endpointId, seedId]) {
        await pool.query("DELETE FROM yare_public_model_calls WHERE budget_id = $1", [id]);
        await pool.query("DELETE FROM yare_public_model_budgets WHERE budget_id = $1", [id]);
      }
    } finally {
      await pool.end();
    }
  }
}

main().catch(error => {
  process.stderr.write(`Cockroach budget smoke failed: ${error.code || error.name}\n`);
  process.exitCode = 1;
});
