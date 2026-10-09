const assert = require("node:assert/strict");
const test = require("node:test");
const { createHash } = require("node:crypto");
const { createHandler, hash } = require("../../site/api/verified-handoff.js");

function fixture() {
  const approved = { scope: "One recorded task" };
  const rows = {};
  for (const phase of ["a", "b"]) {
    const run = `run-${phase}`;
    const test = { command: ["python", "-m", "unittest"], exit_code: phase === "a" ? 1 : 0,
      stdout: "", stderr: phase === "a" ? "FAILED (failures=2)" : "Ran 6 tests\nOK" };
    const source = "def task(): return True\n";
    const packet = { task: "Recorded task", current_state: { what_changed: ["task.py"],
      next_clean_action: "Review results", private_path: "do not publish" },
    artifacts: [{ run_id: run, evidence: { source_code: source,
      source_sha256: createHash("sha256").update(source).digest("hex"),
      diff: `--- task.py\n+++ task.py\n+${phase} actual patch`, partial_test: test, full_test: test,
      private_metadata: "do not publish" } }] };
    packet.deterministic_hash = hash(packet);
    const receipt = { run_id: run, current_state_hash: packet.deterministic_hash,
      access_evidence: { policy_allows_read: phase === "a", exit_code: phase === "a" ? 0 : 1,
        effective_policy_hash: "policy", source_sha256: "snapshot", path: "do not publish" } };
    receipt.receipt_hash = hash(receipt);
    approved[phase] = { run_id: run, current_state_hash: packet.deterministic_hash,
      receipt_hash: receipt.receipt_hash, result: "invented summary must not appear" };
    rows[run] = { ...approved[phase], created_at: new Date("2026-10-07T00:00:00Z"),
      state_json: packet.current_state, packet_json: packet, receipt_json: receipt };
  }
  return { approved, rows };
}

const { approved: published, rows } = fixture();

function response() {
  return {
    statusCode: 0,
    headers: {},
    setHeader(key, value) { this.headers[key] = value; },
    end(value) { this.body = JSON.parse(value); }
  };
}

test("upgrade endpoint is off without an explicit enable flag", async () => {
  const res = response();
  await createHandler({ env: {}, poolFor() { throw Error("must not connect"); } })(
    { method: "GET" }, res);
  assert.equal(res.statusCode, 503);
  assert.equal(res.body.error, "upgrade handoff not published");
});

test("only exact approved state and receipt pairs are returned", async () => {
  const seen = [];
  const db = { async query(sql, params) {
    seen.push(params);
    assert.match(sql, /JOIN yare_receipts/);
    return { rows: [rows[params[0]]] };
  } };
  const res = response();
  await createHandler({
    env: { YARE_PUBLIC_UPGRADE_ENABLED: "true", YARE_DATABASE_URL: "test-url" },
    approved: published,
    poolFor: () => db
  })({ method: "GET" }, res);
  assert.equal(res.statusCode, 200);
  assert.deepEqual(seen, [
    [published.a.run_id, published.a.current_state_hash, published.a.receipt_hash],
    [published.b.run_id, published.b.current_state_hash, published.b.receipt_hash]
  ]);
  assert.equal(res.body.b.receipt_hash, published.b.receipt_hash);
  assert.ok(!JSON.stringify(res.body).includes("do not publish"));
  assert.ok(!JSON.stringify(res.body).includes("invented summary"));
  assert.ok(!JSON.stringify(res.body).includes("source_code"));
  assert.equal(res.body.a.full_test.exit_code, 1);
  assert.equal(res.body.b.full_test.stderr, "Ran 6 tests\nOK");
  assert.match(res.body.a.patch, /a actual patch/);
});

test("a missing approved record fails closed", async () => {
  const res = response();
  await createHandler({
    env: { YARE_PUBLIC_UPGRADE_ENABLED: "true", YARE_DATABASE_URL: "test-url" },
    poolFor: () => ({ query: async () => ({ rows: [] }) })
  })({ method: "GET" }, res);
  assert.equal(res.statusCode, 404);
});

test("a receipt without stored evidence fails closed", async () => {
  const res = response();
  await createHandler({
    env: { YARE_PUBLIC_UPGRADE_ENABLED: "true", YARE_DATABASE_URL: "test-url" },
    poolFor: () => ({ query: async (_sql, params) => ({ rows: [{
      run_id: params[0], current_state_hash: params[1], receipt_hash: params[2],
      state_json: {}, has_access_evidence: false
    }] }) })
  })({ method: "GET" }, res);
  assert.equal(res.statusCode, 503);
});

for (const [name, mutate] of [
  ["altered packet", d => { d.rows['run-a'].packet_json.task = "altered"; }],
  ["altered state", d => { d.rows['run-a'].state_json = {}; }],
  ["altered receipt", d => { d.rows['run-a'].receipt_json.access_evidence.exit_code = 99; }],
  ["unapproved record", d => { d.rows['run-a'].run_id = "other"; }],
  ["missing packet", d => { d.rows['run-a'].packet_json = null; }],
]) {
  test(`${name} fails closed`, async () => {
    const data = fixture();
    mutate(data);
    const res = response();
    await createHandler({ env: { YARE_PUBLIC_UPGRADE_ENABLED: "true", YARE_DATABASE_URL: "stub" },
      approved: data.approved, poolFor: () => ({ query: async (_sql, params) => ({ rows: [data.rows[params[0]]] }) })
    })({ method: "GET", query: { run_id: "other" } }, res);
    assert.equal(res.statusCode, 503);
    assert.ok(!res.body.a);
  });
}

test("correctly hashed private publication fields are rejected", async () => {
  const data = fixture();
  const row = data.rows['run-a'];
  row.packet_json.artifacts[0].evidence.diff = "C:\\Users\\private\\secret.py";
  delete row.packet_json.deterministic_hash;
  row.packet_json.deterministic_hash = hash(row.packet_json);
  row.current_state_hash = row.packet_json.deterministic_hash;
  row.receipt_json.current_state_hash = row.current_state_hash;
  delete row.receipt_json.receipt_hash;
  row.receipt_json.receipt_hash = hash(row.receipt_json);
  row.receipt_hash = row.receipt_json.receipt_hash;
  data.approved.a = { run_id: row.run_id, current_state_hash: row.current_state_hash, receipt_hash: row.receipt_hash };
  const res = response();
  await createHandler({ env: { YARE_PUBLIC_UPGRADE_ENABLED: "true", YARE_DATABASE_URL: "stub" },
    approved: data.approved, poolFor: () => ({ query: async (_sql, params) => ({ rows: [data.rows[params[0]]] }) })
  })({ method: "GET" }, res);
  assert.equal(res.statusCode, 503);
});
