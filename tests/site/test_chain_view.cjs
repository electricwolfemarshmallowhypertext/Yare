const assert = require("node:assert/strict");
const test = require("node:test");
const vm = require("node:vm");
const fs = require("node:fs");
const path = require("node:path");

function element() {
  return { textContent: "", children: [], listeners: {},
    append(...nodes) { this.children.push(...nodes); }, appendChild(node) { this.children.push(node); },
    replaceChildren(...nodes) { this.children = nodes; },
    setAttribute(name, value) { this[name] = value; }, addEventListener(name, callback) { this.listeners[name] = callback; } };
}

function fixture() {
  const full = { command: ["python", "tests"], exit_code: 0, stdout: "", stderr: "Ran 16 tests\nOK" };
  return { scope: "One bounded, resumed four-agent chain after controller fixes", stages: [..."ABCD"].map((agent, i) => ({
    agent, selected_function: ["normalize_status", "classify_claim", "summarize_claims", "choose_next_action"][i],
    run_id: "run-" + agent, current_state_hash: "state-" + agent, receipt_hash: "receipt-" + agent,
    parent_handoff: i ? { run_id: "previous" } : null, patch: "+saved patch", test_summary: { passed: (i + 1) * 4, total: 16 },
    targeted_test: full, full_test: full, handoff: {}, coding_model: "Nemotron" })),
    acceptance: { basis: "Separate saved controller report", test_summary: { passed: 8, total: 8 } } };
}

function setup(fetch) {
  const elements = {};
  let copied;
  const context = vm.createContext({ document: { getElementById(id) { return elements[id] ||= element(); }, createElement: element },
    window: { isSecureContext: true }, navigator: { clipboard: { async writeText(value) { copied = value; } } }, fetch });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../../site/demo.js"), "utf8"), context);
  return { elements, copied: () => copied };
}

test("default chain view is readable; receipts/logs stay expandable; copy retains exact scope", async () => {
  let endpoint;
  const { elements, copied } = setup(async url => { endpoint = url; return { ok: true, json: async () => fixture() }; });
  await elements.loadHandoff.listeners.click();
  assert.equal(endpoint, "/api/verified-chain");
  assert.equal(elements.chainRecordGrid.children.length, 12);
  assert.match(elements.handoffText.textContent, /One bounded, resumed four-agent chain after controller fixes/);
  assert.match(elements.handoffText.textContent, /Agent D:.*16\/16/);
  assert.match(elements.handoffText.textContent, /separate saved controller report, not bound/);
  assert.doesNotMatch(elements.handoffText.textContent, /saved patch|receipt-D/);
  assert.equal(elements.handoffSections.children.find(node => node.className === "chain-timeline").children.length, 4);
  assert.equal(elements.handoffSections.children.filter(node => node.className === "evidence-details").length, 9);
  await elements.copyHandoff.listeners.click();
  assert.equal(copied(), elements.handoffText.textContent);
});

test("switching views discards late responses and stale exports", async () => {
  let release;
  const { elements } = setup(() => new Promise(resolve => { release = resolve; }));
  const pending = elements.loadHandoff.listeners.click();
  elements.viewPair.listeners.click();
  release({ ok: true, json: async () => fixture() });
  await pending;
  assert.equal(elements.handoffSections.children.length, 0);
  assert.equal(elements.copyHandoff.disabled, true);
  assert.equal(elements.downloadJson.disabled, true);
  assert.equal(elements.viewPair['aria-selected'], "true");
  assert.equal(elements.loadHandoff.textContent, "Load verified handoff");
});
