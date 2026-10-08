const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../../site/api/latest-handoff.js"), "utf8");
const published = require("../../site/public-handoff.json");

function loadHandler(manifest, rows) {
  const queries = [];
  const module = { exports: {} };
  class Pool {
    async query(sql, params) {
      queries.push({ sql, params });
      return {
        rows: rows.filter(row => row.run_id === params[1] &&
          row.current_state_hash === params[0])
      };
    }
  }
  vm.runInNewContext(source, {
    module,
    require(name) {
      if (name === "pg") return { Pool };
      if (name === "../public-handoff.json") return manifest;
      throw new Error(`Unexpected dependency: ${name}`);
    },
    process: { env: { YARE_DATABASE_URL: "postgresql://test:secret@localhost/defaultdb?sslmode=disable" } }
  });
  return { handler: module.exports, queries };
}

async function invoke(handler, method = "GET") {
  const response = { statusCode: 200, headers: {}, body: "",
    setHeader(name, value) { this.headers[name] = value; },
    end(value) { this.body = value; } };
  await handler({ method }, response);
  return response;
}

test("public endpoint returns only the explicitly published state", async () => {
  const privateHash = "b".repeat(64);
  const rows = [
    { run_id: "private-failed-b", current_state_hash: privateHash, state_json: {} },
    { run_id: published.run_id, current_state_hash: published.current_state_hash,
      state_json: { what_is_true: ["published fact"] } }
  ];
  const { handler, queries } = loadHandler(published, rows);
  const response = await invoke(handler);
  assert.equal(response.statusCode, 200);
  assert.equal(JSON.parse(response.body).run_id, published.run_id);
  assert.equal(queries.length, 1);
  assert.match(queries[0].sql, /WHERE cs\.current_state_hash = \$1 AND cs\.run_id = \$2/);
  assert.deepEqual(Array.from(queries[0].params), [published.current_state_hash, published.run_id]);
});

test("missing publication fails closed without a database query", async () => {
  const { handler, queries } = loadHandler({}, []);
  const response = await invoke(handler);
  assert.equal(response.statusCode, 503);
  assert.equal(response.body, "no public handoff configured");
  assert.equal(queries.length, 0);
});

test("an absent published snapshot does not fall back to a private run", async () => {
  const { handler } = loadHandler(published, [
    { run_id: "private-failed-b", current_state_hash: "b".repeat(64), state_json: {} }
  ]);
  const response = await invoke(handler);
  assert.equal(response.statusCode, 404);
  assert.equal(response.body, "published handoff not found");
});
