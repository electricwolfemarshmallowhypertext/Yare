const MAX_PROMPT_BYTES = 4096;
const INPUT_OVERHEAD_TOKENS = 8192;
const MAX_OUTPUT_TOKENS = 512;

function parseRate(value) {
  if (typeof value !== "string" || !/^\d+(?:\.\d{1,6})?$/.test(value)) {
    throw new Error("A server-side price ceiling is required");
  }
  const [whole, fraction = ""] = value.split(".");
  const micros = BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, "0") || "0");
  if (micros <= 0n || micros > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new Error("Invalid server-side price ceiling");
  }
  return Number(micros);
}

function costMicros(inputTokens, outputTokens, inputRate, outputRate) {
  return Number((BigInt(inputTokens) * BigInt(inputRate) +
    BigInt(outputTokens) * BigInt(outputRate) + 999999n) / 1000000n);
}

function quote(prompt, inputRate, outputRate) {
  if (typeof prompt !== "string" || !prompt.trim()) {
    throw new Error("Prompt is required");
  }
  const bytes = Buffer.byteLength(prompt, "utf8");
  if (bytes > MAX_PROMPT_BYTES) {
    throw new Error("Prompt exceeds public input bound");
  }
  const inputBound = bytes + INPUT_OVERHEAD_TOKENS;
  return {
    inputBound,
    outputBound: MAX_OUTPUT_TOKENS,
    tokenBound: inputBound + MAX_OUTPUT_TOKENS,
    usdMicros: costMicros(inputBound, MAX_OUTPUT_TOKENS, inputRate, outputRate)
  };
}

async function reserve(pool, requestId, budgetId, modelId, bound, inputRate, outputRate) {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const budget = await client.query(`
      UPDATE yare_public_model_budgets
      SET calls_used = calls_used + 1,
          tokens_charged = tokens_charged + $2,
          charged_usd_micros = charged_usd_micros + $3
      WHERE budget_id = $1 AND blocked = false
        AND calls_used < max_calls
        AND tokens_charged + $2 <= max_tokens
        AND charged_usd_micros + $3 <= limit_usd_micros
      RETURNING budget_id
    `, [budgetId, bound.tokenBound, bound.usdMicros]);
    if (budget.rows.length !== 1) {
      throw new Error("Public model budget unavailable");
    }
    await client.query(`
      INSERT INTO yare_public_model_calls
        (request_id, budget_id, model_id, reserved_usd_micros, input_bound,
         output_bound, input_rate_micros, output_rate_micros, status)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'reserved')
    `, [requestId, budgetId, modelId, bound.usdMicros, bound.inputBound,
      bound.outputBound, inputRate, outputRate]);
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK").catch(() => {});
    throw error;
  } finally {
    client.release();
  }
}

async function settle(pool, requestId, usage, bound, inputRate, outputRate) {
  const input = usage && usage.prompt_tokens;
  const output = usage && usage.completion_tokens;
  if (!Number.isSafeInteger(input) || !Number.isSafeInteger(output) ||
      input < 0 || output < 0 || input > bound.inputBound || output > bound.outputBound) {
    throw new Error("Provider usage missing or outside reservation");
  }
  const observed = costMicros(input, output, inputRate, outputRate);
  if (observed > bound.usdMicros) {
    throw new Error("Provider cost exceeded reservation");
  }
  const result = await pool.query(`
    UPDATE yare_public_model_calls
    SET status = 'observed', prompt_tokens = $2, completion_tokens = $3,
        observed_usd_micros = $4
    WHERE request_id = $1 AND status = 'reserved'
    RETURNING request_id
  `, [requestId, input, output, observed]);
  if (result.rows.length !== 1) {
    throw new Error("Reservation could not be settled");
  }
  // The global counter keeps its worst-case reservation; no refund is issued.
  return observed;
}

async function block(pool, budgetId, requestId) {
  await pool.query("UPDATE yare_public_model_budgets SET blocked = true WHERE budget_id = $1", [budgetId]);
  await pool.query("UPDATE yare_public_model_calls SET status = 'usage_unknown' WHERE request_id = $1 AND status = 'reserved'", [requestId]);
}

module.exports = { quote, parseRate, reserve, settle, block, costMicros };
