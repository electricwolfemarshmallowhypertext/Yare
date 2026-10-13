const assert = require("node:assert/strict");
const test = require("node:test");
const vm = require("node:vm");
const fs = require("node:fs");
const path = require("node:path");

function element() {
  return { textContent: "", children: [], disabled: false, listeners: {},
    append(...nodes) { this.children.push(...nodes); },
    appendChild(node) { this.children.push(node); },
    replaceChildren(...nodes) { this.children = nodes; },
    addEventListener(name, callback) { this.listeners[name] = callback; } };
}

test("demo renders and copies actual patch/test evidence; failed reload disables stale exports", async () => {
  const elements = {};
  const document = { getElementById(id) { return elements[id] ||= element(); }, createElement: element };
  const testResult = { command: ["python", "-m", "unittest"], exit_code: 0, stdout: "", stderr: "Ran 6 tests\nOK" };
  const phase = { run_id: "run", current_state_hash: "state", receipt_hash: "receipt", patch: "+real patch",
    targeted_test: testResult, full_test: testResult, handoff: { next_clean_action: "Review",
      what_changed: ["workstate.py"], what_is_true: [], what_is_unverified: [],
      what_contradicts_prior_state: [], what_needs_human_approval: [], open_loops: [] },
    access: { policy_allows_read: true, exit_code: 0, source_sha256: "snapshot" }, assessment: null };
  const data = { task: "Recorded task", a: { ...phase,
    handoff: { ...phase.handoff, what_contradicts_prior_state: ["All full-suite tests passed"] },
    full_test: { ...testResult, exit_code: 1, stderr: "FAILED (failures=2)" } },
    b: phase, scope: "Recorded scope", summary_source: "Stored evidence" };
  let healthy = true;
  let copied;
  const context = vm.createContext({ document, window: { isSecureContext: true },
    navigator: { clipboard: { async writeText(text) { copied = text; } } },
    fetch: async () => ({ ok: healthy, json: async () => data }) });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../../site/demo.js"), "utf8"), context);
  await elements.loadHandoff.listeners.click();
  assert.match(elements.handoffText.textContent, /2 test failures remained/);
  assert.match(elements.handoffText.textContent, /All 6 tests passed/);
  assert.match(elements.handoffText.textContent, /What the first agent's test results disproved\n- All full-suite tests passed/);
  assert.doesNotMatch(elements.handoffText.textContent, /\+real patch/);
  const evidence = elements.handoffSections.children.filter(node => node.className === "evidence-details");
  assert.ok(evidence.some(node => node.children[1].textContent.includes("+real patch")));
  assert.ok(evidence.some(node => node.children[1].textContent.includes("FAILED (failures=2)")));
  assert.ok(evidence.every(node => !node.open));
  assert.equal(elements.copyHandoff.disabled, false);
  await elements.copyHandoff.listeners.click();
  assert.equal(copied, elements.handoffText.textContent);
  healthy = false;
  await elements.loadHandoff.listeners.click();
  assert.equal(elements.copyHandoff.disabled, true);
  assert.equal(elements.downloadJson.disabled, true);
  assert.equal(elements.handoffSections.children.length, 0);
});
