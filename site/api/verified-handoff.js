const published = require("../public-upgrade-handoff.json");
const { createHash } = require("node:crypto");

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map(key => `${canonical(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value).replace(/[\u0080-\uFFFF]/g,
    char => `\\u${char.charCodeAt(0).toString(16).padStart(4, "0")}`);
}

function hash(value) {
  return createHash("sha256").update(canonical(value)).digest("hex");
}

function withoutHash(value, key) {
  return Object.fromEntries(Object.entries(value).filter(([name]) => name !== key));
}

function publicText(value) {
  const text = String(value || "");
  if (/[A-Za-z]:[\\/]|\/(?:Users|home)\/|postgres(?:ql)?:\/\/|Bearer\s+|(?:API_KEY|PASSWORD)\s*[=:]/i.test(text)) {
    throw Error("private data in publication fields");
  }
  return text;
}

function publicTest(value) {
  if (!value || !Array.isArray(value.command) || !Number.isInteger(value.exit_code) ||
      !(value.stdout || value.stderr)) throw Error("stored test evidence missing");
  return { command: value.command.map(publicText), exit_code: value.exit_code,
    stdout: publicText(value.stdout), stderr: publicText(value.stderr) };
}

function evidenceFor(row) {
  const packet = row.packet_json;
  const receipt = row.receipt_json;
  if (!packet || packet.deterministic_hash !== row.current_state_hash ||
      hash(withoutHash(packet, "deterministic_hash")) !== row.current_state_hash ||
      canonical(packet.current_state) !== canonical(row.state_json) ||
      !receipt || receipt.receipt_hash !== row.receipt_hash ||
      hash(withoutHash(receipt, "receipt_hash")) !== row.receipt_hash ||
      receipt.run_id !== row.run_id || receipt.current_state_hash !== row.current_state_hash) {
    throw Error("stored evidence hash mismatch");
  }
  const artifacts = packet.artifacts.filter(artifact => artifact.run_id === row.run_id);
  if (artifacts.length !== 1) throw Error("stored source is ambiguous");
  const evidence = artifacts[0].evidence;
  if (!evidence || typeof evidence.source_code !== "string" ||
      createHash("sha256").update(evidence.source_code).digest("hex") !== evidence.source_sha256 ||
      typeof evidence.diff !== "string" || !receipt.access_evidence) {
    throw Error("stored source evidence missing");
  }
  const state = {};
  for (const key of ["what_changed", "what_is_true", "what_is_unverified",
    "what_contradicts_prior_state", "what_needs_human_approval", "open_loops", "next_clean_action"]) {
    const value = row.state_json[key];
    state[key] = Array.isArray(value) ? value.map(item => typeof item === "object"
      ? publicText(item.text) : publicText(item)) : publicText(value);
  }
  const access = receipt.access_evidence;
  if (typeof access.policy_allows_read !== "boolean" || !Number.isInteger(access.exit_code)) {
    throw Error("stored access decision missing");
  }
  return {
    task: publicText(packet.task), patch: publicText(evidence.diff), source_sha256: evidence.source_sha256,
    targeted_test: publicTest(evidence.partial_test), full_test: publicTest(evidence.full_test),
    handoff: state,
    assessment: evidence.handoff_assessment ? {
      observed_exit_code: evidence.handoff_assessment.observed_exit_code,
      unverified_claim: publicText(evidence.handoff_assessment.unverified_claim),
      explanation: publicText(evidence.handoff_assessment.explanation)
    } : null,
    access: { policy_allows_read: access.policy_allows_read, exit_code: access.exit_code,
      stderr: publicText(access.stderr),
      effective_policy_hash: access.effective_policy_hash, source_sha256: access.source_sha256 }
  };
}

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

function createHandler({ env = process.env, poolFor = getPool, approved = published } = {}) {
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
        const record = approved[phase];
        const result = await db.query(`
          SELECT cs.run_id, cs.current_state_hash, cs.created_at, rec.receipt_hash,
                 cs.state_json, rec.receipt_json,
                 COALESCE(cs.packet_json, CASE WHEN r.current_state_hash = cs.current_state_hash
                   THEN r.compiled_state_json END) AS packet_json
          FROM yare_current_states cs
          JOIN yare_receipts rec
            ON rec.run_id = cs.run_id
           AND rec.current_state_hash = cs.current_state_hash
          JOIN yare_runs r ON r.run_id = cs.run_id
          WHERE cs.run_id = $1
            AND cs.current_state_hash = $2
            AND rec.receipt_hash = $3
          LIMIT 1
        `, [record.run_id, record.current_state_hash, record.receipt_hash]);
        if (result.rows.length !== 1) {
          respond(res, 404, { error: "published handoff not found" });
          return;
        }
        const row = result.rows[0];
        if (row.run_id !== record.run_id || row.current_state_hash !== record.current_state_hash ||
            row.receipt_hash !== record.receipt_hash) throw Error("unapproved record");
        const evidence = evidenceFor(row);
        runs[phase] = {
          run_id: row.run_id,
          current_state_hash: row.current_state_hash,
          receipt_hash: row.receipt_hash,
          created_at: row.created_at instanceof Date
            ? row.created_at.toISOString() : String(row.created_at || ""),
          ...evidence,
          next_action: evidence.handoff.next_clean_action
        };
      }
      if (runs.a.access.source_sha256 !== runs.b.access.source_sha256) {
        throw Error("access decisions name different snapshots");
      }
      respond(res, 200, {
        task: runs.a.task,
        scope: approved.scope,
        summary_source: "Recorded evidence loaded from CockroachDB; state, source and receipt hashes checked. No new agent run.",
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
module.exports.hash = hash;
