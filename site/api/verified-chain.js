const published = require("../public-chain.json");
const recordedAcceptance = require("../public-chain-acceptance.json");
const { canonical, publicText, checkPublicValue, publicTest, verifyRecord } = require("../lib/verified-record");

let pool;
function getPool(env) {
  if (!pool) {
    const { Pool } = require("pg");
    pool = new Pool({ connectionString: env.YARE_DATABASE_URL, max: 1,
      connectionTimeoutMillis: 15000, query_timeout: 15000, idleTimeoutMillis: 30000,
      ssl: { ca: env.YARE_DATABASE_CA_PEM || undefined, rejectUnauthorized: true } });
    pool.on("error", () => console.error("yare_verified_chain", { code: "POOL_ERROR" }));
  }
  return pool;
}

function testSummary(test, expectedTotal) {
  const summary = JSON.parse(test.stdout);
  if (summary.tests_run !== expectedTotal || summary.skipped !== 0 ||
      !Array.isArray(summary.failed_tests) || new Set(summary.failed_tests).size !== summary.failed_tests.length ||
      test.exit_code !== (summary.failed_tests.length ? 1 : 0) ||
      !test.stderr.includes(`Ran ${expectedTotal} tests`)) throw Error("stored test summary mismatch");
  return { total: expectedTotal, passed: expectedTotal - summary.failed_tests.length,
    failed: summary.failed_tests.length };
}

function projectStage(row, record, previous, approved) {
  if (["run_id", "current_state_hash", "receipt_hash"].some(key => row[key] !== record[key])) {
    throw Error("unapproved chain record");
  }
  const { packet, evidence } = verifyRecord(row);
  if (packet.task !== approved.task || evidence.brief_sha256 !== approved.brief_sha256) {
    throw Error("stored chain brief mismatch");
  }
  const expectedParent = previous ? Object.fromEntries(
    ["run_id", "current_state_hash", "receipt_hash"].map(key => [key, previous[key]])) : null;
  if (canonical(evidence.parent_handoff || null) !== canonical(expectedParent)) throw Error("stored parent link mismatch");
  if (previous && (!evidence.handoff_assessment ||
      evidence.handoff_assessment.state_hash !== previous.current_state_hash ||
      evidence.handoff_assessment.receipt_hash !== previous.receipt_hash ||
      evidence.handoff_assessment.focused_exit_code !== previous.targeted_test.exit_code ||
      evidence.handoff_assessment.full_exit_code !== previous.full_test.exit_code)) {
    throw Error("stored assessment mismatch");
  }
  const fullTest = publicTest(evidence.full_test);
  const focused = publicTest(evidence.partial_test);
  const summary = testSummary(fullTest, 16);
  if (testSummary(focused, 4).passed !== 4) throw Error("stored focused tests failed");
  const handoff = {};
  for (const key of ["what_changed", "what_is_true", "what_is_unverified", "what_contradicts_prior_state",
    "what_needs_human_approval", "open_loops", "next_clean_action"]) {
    const value = row.state_json[key];
    handoff[key] = Array.isArray(value) ? value.map(item => publicText(typeof item === "object" ? item.text : item)) : publicText(value);
  }
  return { agent: record.agent, run_id: row.run_id, current_state_hash: row.current_state_hash,
    receipt_hash: row.receipt_hash, source_sha256: evidence.source_sha256,
    selected_function: publicText(evidence.selection.function), selection_reason: publicText(evidence.selection.reason),
    coding_model: publicText(evidence.coding_model), patch: publicText(evidence.diff),
    targeted_test: focused, full_test: fullTest, test_summary: summary, handoff,
    parent_handoff: expectedParent, assessment: evidence.handoff_assessment ? {
      state_hash: evidence.handoff_assessment.state_hash, receipt_hash: evidence.handoff_assessment.receipt_hash,
      focused_exit_code: evidence.handoff_assessment.focused_exit_code,
      full_exit_code: evidence.handoff_assessment.full_exit_code,
      explanation: publicText(evidence.handoff_assessment.explanation) } : null };
}

function respond(res, status, payload) {
  if (status === 200) checkPublicValue(payload);
  res.statusCode = status;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.setHeader("cache-control", status === 200 ? "public, max-age=0, s-maxage=60, stale-while-revalidate=300" : "no-store");
  res.end(JSON.stringify(payload));
}

function createHandler({ env = process.env, poolFor = getPool, approved = published, acceptance = recordedAcceptance } = {}) {
  return async (req, res) => {
    if (req.method !== "GET") return respond(res, 405, { error: "method not allowed" });
    if (env.YARE_PUBLIC_UPGRADE_ENABLED !== "true" || !env.YARE_DATABASE_URL) {
      return respond(res, 503, { error: "recorded chain unavailable" });
    }
    try {
      const db = poolFor(env);
      const stages = [];
      for (const record of approved.stages) {
        const result = await db.query(`
          SELECT cs.run_id, cs.current_state_hash, cs.state_json, rec.receipt_hash, rec.receipt_json,
                 COALESCE(cs.packet_json, CASE WHEN r.current_state_hash = cs.current_state_hash
                   THEN r.compiled_state_json END) AS packet_json
          FROM yare_current_states cs
          JOIN yare_receipts rec ON rec.run_id = cs.run_id AND rec.current_state_hash = cs.current_state_hash
          JOIN yare_runs r ON r.run_id = cs.run_id
          WHERE cs.run_id = $1 AND cs.current_state_hash = $2 AND rec.receipt_hash = $3 LIMIT 1
        `, [record.run_id, record.current_state_hash, record.receipt_hash]);
        if (result.rows.length !== 1) return respond(res, 404, { error: "published chain record not found" });
        const stage = projectStage(result.rows[0], record, stages.at(-1), approved);
        if (stage.test_summary.passed !== (stages.length + 1) * 4) throw Error("stored chain progression mismatch");
        stages.push(stage);
      }
      const final = stages.at(-1);
      if (stages.length !== 4 || ["run_id", "current_state_hash", "receipt_hash"].some(key => final[key] !== acceptance[key]) ||
          testSummary(acceptance, 8).passed !== 8) throw Error("recorded acceptance mismatch");
      respond(res, 200, { scope: approved.scope, task: approved.task, brief_sha256: approved.brief_sha256,
        resumed_from: stages[0].run_id, stages,
        acceptance: { basis: acceptance.basis, run_id: acceptance.run_id, current_state_hash: acceptance.current_state_hash,
          receipt_hash: acceptance.receipt_hash, exit_code: acceptance.exit_code,
          stdout: acceptance.stdout, stderr: acceptance.stderr, test_summary: testSummary(acceptance, 8) },
        summary_source: "Four exact CockroachDB records verified. Acceptance output is a separate saved controller report, not agent-receipt evidence. No new model run." });
    } catch {
      console.error("yare_verified_chain", { code: "CHAIN_PUBLICATION_REJECTED" });
      respond(res, 503, { error: "recorded chain unavailable", code: "CHAIN_PUBLICATION_REJECTED" });
    }
  };
}

module.exports = createHandler();
module.exports.createHandler = createHandler;
