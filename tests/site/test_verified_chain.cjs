const assert = require("node:assert/strict");
const test = require("node:test");
const { createHash } = require("node:crypto");
const { hash } = require("../../site/lib/verified-record");
const { createHandler } = require("../../site/api/verified-chain");

function fixture() {
  const approved = { scope: "One bounded, resumed four-agent chain after controller fixes", task: "Task", brief_sha256: "brief", stages: [] };
  const rows = {};
  for (const [index, agent] of [..."ABCD"].entries()) {
    const run = "run-" + agent;
    const failed = Array.from({ length: 12 - index * 4 }, (_, i) => "failed-" + i);
    const full = { command: ["python", "tests"], exit_code: failed.length ? 1 : 0,
      stdout: JSON.stringify({ tests_run: 16, failed_tests: failed, skipped: 0 }),
      stderr: `Ran 16 tests\n${failed.length ? `FAILED (failures=${failed.length})` : "OK"}` };
    const focused = { ...full, exit_code: 0,
      stdout: JSON.stringify({ tests_run: 4, failed_tests: [], skipped: 0 }), stderr: "Ran 4 tests\nOK" };
    const previous = approved.stages.at(-1);
    const parent = previous ? Object.fromEntries(["run_id", "current_state_hash", "receipt_hash"].map(key => [key, previous[key]])) : null;
    const source = "def task(): return " + index + "\n";
    const evidence = { source_code: source, source_sha256: createHash("sha256").update(source).digest("hex"),
      diff: "+patch " + agent, partial_test: focused, full_test: full,
      selection: { function: ["normalize_status", "classify_claim", "summarize_claims", "choose_next_action"][index], reason: "Observed failing checks" },
      coding_model: "Nemotron", brief_sha256: "brief", private_metadata: "C:\\private\\do-not-publish",
      ...(parent ? { parent_handoff: parent, handoff_assessment: {
        state_hash: parent.current_state_hash, receipt_hash: parent.receipt_hash,
        focused_exit_code: 0, full_exit_code: 1, explanation: "Full suite is not yet passing" } } : {}) };
    const packet = { task: "Task", current_state: { what_changed: ["workstate.py"], open_loops: [], next_clean_action: "Review" },
      artifacts: [{ run_id: run, evidence }] };
    packet.deterministic_hash = hash(packet);
    const receipt = { run_id: run, current_state_hash: packet.deterministic_hash };
    receipt.receipt_hash = hash(receipt);
    const record = { agent, run_id: run, current_state_hash: packet.deterministic_hash, receipt_hash: receipt.receipt_hash };
    approved.stages.push(record);
    rows[run] = { ...record, packet_json: packet, state_json: packet.current_state, receipt_json: receipt };
  }
  const acceptance = { ...approved.stages.at(-1), basis: "Separate saved controller report",
    exit_code: 0, stdout: JSON.stringify({ tests_run: 8, failed_tests: [], skipped: 0 }), stderr: "Ran 8 tests\nOK" };
  return { approved, acceptance, rows };
}

function response() {
  return { headers: {}, setHeader(key, value) { this.headers[key] = value; }, end(body) { this.body = JSON.parse(body); } };
}

function handler(data, query) {
  return createHandler({ env: { YARE_PUBLIC_UPGRADE_ENABLED: "true", YARE_DATABASE_URL: "stub" },
    approved: data.approved, acceptance: data.acceptance,
    poolFor: () => ({ query: query || (async (_sql, params) => ({ rows: [data.rows[params[0]]] })) }) });
}

test("chain is GET-only and never connects when disabled", async () => {
  const run = createHandler({ env: {}, poolFor() { throw Error("must not connect"); } });
  const disabled = response();
  await run({ method: "GET" }, disabled);
  assert.equal(disabled.statusCode, 503);
  const post = response();
  await run({ method: "POST" }, post);
  assert.equal(post.statusCode, 405);
});

test("four exact SELECT-only records, real progression, parent checks and separate acceptance", async () => {
  const data = fixture();
  const queries = [];
  const res = response();
  await handler(data, async (sql, params) => {
    assert.match(sql.trim(), /^SELECT/);
    assert.doesNotMatch(sql, /INSERT|UPDATE|DELETE|CREATE/);
    queries.push(params);
    return { rows: [data.rows[params[0]]] };
  })({ method: "GET", query: { run_id: "not-approved" } }, res);
  assert.equal(res.statusCode, 200);
  assert.equal(queries.length, 4);
  assert.deepEqual(res.body.stages.map(stage => stage.test_summary.passed), [4, 8, 12, 16]);
  assert.deepEqual(queries[0], Object.values(data.approved.stages[0]).slice(1));
  assert.match(res.body.acceptance.basis, /Separate/);
  assert.doesNotMatch(JSON.stringify(res.body), /source_code|private_metadata|do-not-publish/);
  assert.equal(res.body.stages[1].parent_handoff.receipt_hash, res.body.stages[0].receipt_hash);
});

for (const [label, mutate] of [
  ["altered source", d => { d.rows['run-A'].packet_json.artifacts[0].evidence.source_code = "bad"; }],
  ["altered state", d => { d.rows['run-A'].state_json = {}; }],
  ["wrong identity", d => { d.rows['run-A'].run_id = "not-approved"; }],
  ["wrong acceptance identity", d => { d.acceptance.receipt_hash = "other"; }],
  ["acceptance failure", d => { d.acceptance.exit_code = 1; }],
]) {
  test(label + " fails closed", async () => {
    const data = fixture();
    mutate(data);
    const res = response();
    await handler(data)({ method: "GET" }, res);
    assert.equal(res.statusCode, 503);
    assert.ok(!res.body.stages);
  });
}

test("missing approved row returns 404", async () => {
  const res = response();
  await handler(fixture(), async () => ({ rows: [] }))({ method: "GET" }, res);
  assert.equal(res.statusCode, 404);
});

test("correctly rehashed broken parent and private patch are rejected", async () => {
  for (const change of [e => { e.parent_handoff.receipt_hash = "wrong"; }, e => { e.diff = "C:\\private\\secret"; }]) {
    const data = fixture();
    const row = data.rows['run-D'];
    change(row.packet_json.artifacts[0].evidence);
    delete row.packet_json.deterministic_hash;
    row.current_state_hash = row.packet_json.deterministic_hash = hash(row.packet_json);
    row.receipt_json.current_state_hash = row.current_state_hash;
    delete row.receipt_json.receipt_hash;
    row.receipt_hash = row.receipt_json.receipt_hash = hash(row.receipt_json);
    Object.assign(data.approved.stages[3], { current_state_hash: row.current_state_hash, receipt_hash: row.receipt_hash });
    Object.assign(data.acceptance, data.approved.stages[3]);
    const res = response();
    await handler(data)({ method: "GET" }, res);
    assert.equal(res.statusCode, 503);
    assert.ok(!JSON.stringify(res.body).includes("secret"));
  }
});
