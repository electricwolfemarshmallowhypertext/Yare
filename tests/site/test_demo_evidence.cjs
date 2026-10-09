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
    targeted_test: testResult, full_test: testResult, handoff: { next_clean_action: "Review" },
    access: { policy_allows_read: true, exit_code: 0, source_sha256: "snapshot" }, assessment: null };
  const data = { task: "Recorded task", a: { ...phase, full_test: { ...testResult, exit_code: 1, stderr: "FAILED (failures=2)" } },
    b: phase, scope: "Recorded scope", summary_source: "Stored evidence" };
  let healthy = true;
  let copied;
  const context = vm.createContext({ document, window: { isSecureContext: true },
    navigator: { clipboard: { async writeText(text) { copied = text; } } },
    fetch: async () => ({ ok: healthy, json: async () => data }) });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../../site/demo.js"), "utf8"), context);
  await elements.loadHandoff.listeners.click();
  assert.match(elements.handoffText.textContent, /\+real patch/);
  assert.match(elements.handoffText.textContent, /FAILED \(failures=2\)/);
  assert.match(elements.handoffText.textContent, /Ran 6 tests/);
  assert.equal(elements.copyHandoff.disabled, false);
  await elements.copyHandoff.listeners.click();
  assert.equal(copied, elements.handoffText.textContent);
  healthy = false;
  await elements.loadHandoff.listeners.click();
  assert.equal(elements.copyHandoff.disabled, true);
  assert.equal(elements.downloadJson.disabled, true);
  assert.equal(elements.handoffSections.children.length, 0);
});
