const { Pool } = require("pg");

let pool;

function getPool() {
  const connectionString = process.env.YARE_DATABASE_URL;
  if (!connectionString) {
    throw new Error("YARE_DATABASE_URL is required");
  }

  if (!pool) {
    const ssl = connectionString.includes("sslmode=disable")
      ? false
      : { rejectUnauthorized: false };

    pool = new Pool({
      connectionString,
      max: 1,
      ssl
    });
  }

  return pool;
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

module.exports = async function handler(req, res) {
  if (req.method !== "GET") {
    res.statusCode = 405;
    res.setHeader("content-type", "text/plain; charset=utf-8");
    res.end("method not allowed");
    return;
  }

  let db;
  try {
    db = getPool();
  } catch (error) {
    res.statusCode = 500;
    res.setHeader("content-type", "text/plain; charset=utf-8");
    res.end(error.message);
    return;
  }

  try {
    const result = await db.query(`
      SELECT
        cs.run_id,
        COALESCE(r.task, '') AS task,
        cs.current_state_hash,
        COALESCE(yr.receipt_hash, '') AS receipt_hash,
        cs.created_at,
        cs.state_json
      FROM yare_current_states cs
      LEFT JOIN yare_runs r ON r.run_id = cs.run_id
      LEFT JOIN LATERAL (
        SELECT receipt_hash
        FROM yare_receipts
        WHERE current_state_hash = cs.current_state_hash
        ORDER BY created_at DESC
        LIMIT 1
      ) yr ON true
      ORDER BY cs.created_at DESC
      LIMIT 1
    `);

    if (result.rows.length === 0) {
      res.statusCode = 404;
      res.setHeader("content-type", "text/plain; charset=utf-8");
      res.end("no handoff records found");
      return;
    }

    const row = result.rows[0];
    const state = row.state_json || {};
    const payload = {
      run_id: row.run_id,
      task: row.task,
      current_state_hash: row.current_state_hash,
      receipt_hash: row.receipt_hash,
      created_at: row.created_at instanceof Date ? row.created_at.toISOString() : String(row.created_at || ""),
      what_changed: asArray(state.what_changed),
      what_is_true: asArray(state.what_is_true),
      what_is_unverified: asArray(state.what_is_unverified),
      contradictions: asArray(state.what_contradicts_prior_state),
      human_approval_items: asArray(state.what_needs_human_approval),
      open_loops: asArray(state.open_loops),
      next_clean_action: state.next_clean_action || ""
    };

    res.statusCode = 200;
    res.setHeader("content-type", "application/json; charset=utf-8");
    res.end(JSON.stringify(payload));
  } catch (error) {
    res.statusCode = 500;
    res.setHeader("content-type", "text/plain; charset=utf-8");
    res.end(`latest handoff query failed: ${error.message}`);
  }
};
