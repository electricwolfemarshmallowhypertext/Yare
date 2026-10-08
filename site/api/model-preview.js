const { randomUUID } = require("node:crypto");
const budget = require("./lib/public-model-budget");

const NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B";
let pool;

function getPool(env) {
  if (!pool) {
    const { Pool } = require("pg");
    pool = new Pool({
      connectionString: env.YARE_DATABASE_URL,
      ssl: { ca: env.YARE_DATABASE_CA_PEM, rejectUnauthorized: true },
      max: 2
    });
  }
  return pool;
}

function respond(res, status, value) {
  res.statusCode = status;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.end(JSON.stringify(value));
}

function createHandler({ env = process.env, poolFor = getPool, fetchFn = globalThis.fetch } = {}) {
  return async function handler(req, res) {
    if (req.method !== "POST") {
      respond(res, 405, { error: "method not allowed" });
      return;
    }
    if (env.YARE_PUBLIC_MODEL_ENABLED !== "true") {
      respond(res, 503, { error: "public model execution disabled" });
      return;
    }

    let inputRate;
    let outputRate;
    try {
      if (!env.YARE_DATABASE_URL || !env.YARE_DATABASE_CA_PEM || !env.NEBIUS_API_KEY ||
          !env.YARE_PUBLIC_BUDGET_ID || env.YARE_PUBLIC_MODEL_ID !== NANO) {
        throw new Error("Public model configuration incomplete");
      }
      inputRate = budget.parseRate(env.YARE_PUBLIC_INPUT_CEILING_USD_PER_MILLION);
      outputRate = budget.parseRate(env.YARE_PUBLIC_OUTPUT_CEILING_USD_PER_MILLION);
      if (inputRate < 60000 || outputRate < 240000) {
        throw new Error("Price ceiling below historical Nano rate");
      }
    } catch {
      respond(res, 503, { error: "public model configuration unavailable" });
      return;
    }

    let prompt;
    let bound;
    try {
      const body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
      if (!body || typeof body !== "object" || Array.isArray(body) ||
          Object.keys(body).length !== 1 || typeof body.prompt !== "string") {
        throw new Error("Invalid request");
      }
      prompt = body.prompt;
      bound = budget.quote(prompt, inputRate, outputRate);
    } catch {
      respond(res, 400, { error: "invalid or oversized prompt" });
      return;
    }

    const requestId = randomUUID();
    let db;
    try {
      db = poolFor(env);
      await budget.reserve(db, requestId, env.YARE_PUBLIC_BUDGET_ID, NANO,
        bound, inputRate, outputRate);
    } catch {
      respond(res, 503, { error: "public model budget unavailable" });
      return;
    }

    try {
      const response = await fetchFn("https://api.tokenfactory.nebius.com/v1/chat/completions", {
        method: "POST",
        headers: {
          "authorization": `Bearer ${env.NEBIUS_API_KEY}`,
          "content-type": "application/json"
        },
        body: JSON.stringify({ model: NANO, messages: [{ role: "user", content: prompt }],
          max_tokens: bound.outputBound, temperature: 0 }),
        signal: AbortSignal.timeout(25000)
      });
      if (!response.ok) {
        throw new Error("Provider request failed");
      }
      const result = await response.json();
      await budget.settle(db, requestId, result.usage, bound, inputRate, outputRate);
      const content = result.choices && result.choices[0] && result.choices[0].message &&
        result.choices[0].message.content;
      if (typeof content !== "string") {
        throw new Error("Provider response missing content");
      }
      respond(res, 200, { request_id: requestId, model: NANO, content });
    } catch {
      try {
        await budget.block(db, env.YARE_PUBLIC_BUDGET_ID, requestId);
      } catch {
        // A failed block cannot release the already-charged reservation.
      }
      respond(res, 502, { error: "model response unavailable; budget held" });
    }
  };
}

module.exports = createHandler();
module.exports.createHandler = createHandler;
