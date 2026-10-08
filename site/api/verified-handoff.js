const published = require("../public-upgrade-handoff.json");

let pool;

function getPool(env) {
  if (!pool) {
    const { Pool } = require("pg");
    pool = new Pool({
      connectionString: env.YARE_DATABASE_URL,
      max: 1,
      ssl: {
        ca: env.YARE_DATABASE_CA_PEM || undefined,
        rejectUnauthorized: true
      }
    });
  }
  return pool;
}

function respond(res, status, payload) {
  res.statusCode = status;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.setHeader("cache-control", "no-store");
  res.end(JSON.stringify(payload));
}

function createHandler({ env = process.env, poolFor = getPool } = {}) {
  return async function handler(req, res) {
    if (req.method !== "GET") {
      respond(res, 405, { error: "method not allowed" });
      return;
    }
    if (env.YARE_PUBLIC_UPGRADE_ENABLED !== "true") {
      respond(res, 503, { error: "upgrade handoff not published" });
      return;
    }
    if (!env.YARE_DATABASE_URL) {
      respond(res, 503, { error: "database unavailable" });
      return;
    }

    try {
      const db = poolFor(env);
      const runs = {};
      for (const phase of ["a", "b"]) {
        const record = published[phase];
        const result = await db.query(`
          SELECT cs.run_id, cs.current_state_hash, cs.created_at, rec.receipt_hash,
                 cs.state_json, rec.receipt_json ? 'access_evidence' AS has_access_evidence
          FROM yare_current_states cs
          JOIN yare_receipts rec
            ON rec.run_id = cs.run_id
           AND rec.current_state_hash = cs.current_state_hash
          WHERE cs.run_id = $1
            AND cs.current_state_hash = $2
            AND rec.receipt_hash = $3
          LIMIT 1
        `, [record.run_id, record.current_state_hash, record.receipt_hash]);
        if (result.rows.length !== 1 || !result.rows[0].state_json ||
            result.rows[0].has_access_evidence !== true) {
          respond(res, 404, { error: "published handoff not found" });
          return;
        }
        const row = result.rows[0];
        runs[phase] = {
          run_id: row.run_id,
          current_state_hash: row.current_state_hash,
          receipt_hash: row.receipt_hash,
          created_at: row.created_at instanceof Date
            ? row.created_at.toISOString() : String(row.created_at || ""),
          result: record.result,
          next_action: record.next_action
        };
      }
      respond(res, 200, {
        task: published.task,
        scope: published.scope,
        source_access: published.source_access,
        summary_source: "Curated from docs/NEMOTRON_BOUNDARY_RESULT.md; exact state and receipt IDs checked against CockroachDB",
        a: runs.a,
        b: runs.b
      });
    } catch {
      respond(res, 503, { error: "database unavailable" });
    }
  };
}

module.exports = createHandler();
module.exports.createHandler = createHandler;
