const MONEY_SCALE = 1000000000000000000n;
const MICRO_SCALE = 1000000000000n;

function moneyUnits(value) {
  if (typeof value !== "string" || !/^\d+(?:\.\d{1,18})?$/.test(value)) {
    throw new Error("Invalid ledger amount");
  }
  const [whole, fraction = ""] = value.split(".");
  return BigInt(whole) * MONEY_SCALE + BigInt(fraction.padEnd(18, "0") || "0");
}

function safeNumber(value) {
  if (value < 0n || value > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new Error("Ledger amount exceeds integer storage");
  }
  return Number(value);
}

function summarizeLedger(state) {
  if (!state || !Array.isArray(state.calls) ||
      !Number.isSafeInteger(state.max_calls) || !Number.isSafeInteger(state.max_tokens) ||
      state.max_calls <= 0 || state.max_tokens <= 0) {
    throw new Error("Invalid ledger limits");
  }
  const maxCalls = Math.min(state.max_calls, 500);
  const maxTokens = Math.min(state.max_tokens, 2000000);
  const limitMicros = safeNumber(
    (moneyUnits(state.limit_usd) < 5n * MONEY_SCALE ?
      moneyUnits(state.limit_usd) : 5n * MONEY_SCALE) / MICRO_SCALE);
  let tokens = 0;
  let cost = 0n;
  for (const call of state.calls) {
    if (!call || !Number.isSafeInteger(call.charged_tokens) || call.charged_tokens < 0) {
      throw new Error("Invalid ledger token charge");
    }
    tokens += call.charged_tokens;
    if (!Number.isSafeInteger(tokens)) throw new Error("Ledger token total overflow");
    cost += moneyUnits(call.charged_usd);
  }
  const chargedMicros = safeNumber((cost + MICRO_SCALE - 1n) / MICRO_SCALE);
  if (state.calls.length > maxCalls || tokens > maxTokens || chargedMicros > limitMicros) {
    throw new Error("Existing ledger exceeds its allowance");
  }
  const exact = `${cost / MONEY_SCALE}.${String(cost % MONEY_SCALE).padStart(18, "0")}`
    .replace(/\.?0+$/, "");
  return {
    calls_used: state.calls.length,
    max_calls: maxCalls,
    tokens_charged: tokens,
    max_tokens: maxTokens,
    charged_usd_exact: exact,
    charged_usd_micros: chargedMicros,
    limit_usd_micros: limitMicros,
    ledger_blocked: Boolean(state.blocked)
  };
}

async function seedBlockedBudget(pool, budgetId, summary) {
  if (typeof budgetId !== "string" || !/^[a-zA-Z0-9_-]{1,64}$/.test(budgetId)) {
    throw new Error("Invalid budget ID");
  }
  const result = await pool.query(`
    INSERT INTO yare_public_model_budgets
      (budget_id, limit_usd_micros, max_calls, max_tokens,
       charged_usd_micros, calls_used, tokens_charged, blocked)
    VALUES ($1, $2, $3, $4, $5, $6, $7, true)
    ON CONFLICT (budget_id) DO NOTHING
    RETURNING budget_id
  `, [budgetId, summary.limit_usd_micros, summary.max_calls, summary.max_tokens,
    summary.charged_usd_micros, summary.calls_used, summary.tokens_charged]);
  if (result.rows.length !== 1) {
    throw new Error("Budget ID already exists; no counters changed");
  }
}

module.exports = { summarizeLedger, seedBlockedBudget };
