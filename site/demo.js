const loadButton = document.getElementById("loadHandoff");
const copyButton = document.getElementById("copyHandoff");
const downloadButton = document.getElementById("downloadJson");
const statusEl = document.getElementById("demoStatus");
const sectionsEl = document.getElementById("handoffSections");
const handoffTextEl = document.getElementById("handoffText");

let verifiedHandoff = null;
let view = "chain";
let requestId = 0;

function setText(id, value) {
  document.getElementById(id).textContent = value || "none";
}

function addSection(title, lines) {
  const section = document.createElement("section");
  section.className = "demo-section";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const list = document.createElement("ul");
  for (const line of lines) {
    const item = document.createElement("li");
    item.textContent = line;
    list.appendChild(item);
  }
  section.append(heading, list);
  sectionsEl.appendChild(section);
  return section;
}

function addEvidence(title, value) {
  const section = document.createElement("details");
  section.className = "evidence-details";
  const heading = document.createElement("summary");
  heading.textContent = title;
  const output = document.createElement("pre");
  output.className = "evidence-output";
  output.textContent = value || "No output recorded.";
  section.append(heading, output);
  sectionsEl.appendChild(section);
}

function testResult(test) {
  const output = [test.stdout, test.stderr].filter(Boolean).join("\n");
  const count = output.match(/Ran (\d+) tests?\b/);
  const failures = output.match(/failures=(\d+)/);
  if (test.exit_code === 0) return count ? `All ${count[1]} tests passed.` : "The recorded test command passed.";
  return failures ? `${failures[1]} test failures remained in the full suite.` : `The recorded test command failed (exit ${test.exit_code}).`;
}

function testText(test) {
  return [`$ ${test.command.join(" ")}`, `Exit code: ${test.exit_code}`,
    test.stdout, test.stderr].filter(Boolean).join("\n");
}

function render(data) {
  setText("handoffTask", data.task === "Evidence-based claim classification with case and whitespace normalization"
    ? "From unfinished code to passing tests" : data.task);
  for (const phase of ["a", "b"]) {
    setText(`${phase}RunId`, data[phase].run_id);
    setText(`${phase}StateHash`, data[phase].current_state_hash);
    setText(`${phase}ReceiptHash`, data[phase].receipt_hash);
  }
  sectionsEl.replaceChildren();
  addSection("The first agent", [
    "Changed workstate.py so a claim needs supporting evidence before it is marked verified.",
    `Focused checks: ${testResult(data.a.targeted_test)}`,
    `Full checks: ${testResult(data.a.full_test)}`
  ]);
  addSection("What Yare saved", [
    "The code change, actual test output and remaining work were stored in CockroachDB.",
    ...data.a.handoff.what_contradicts_prior_state.map(claim => `Disproved by the full-suite results: ${claim}.`),
    ...data.a.handoff.what_is_unverified.map(claim => `Not confirmed: ${claim}.`),
    ...data.a.handoff.open_loops.map(loop => `Still to do: ${typeof loop === "string" ? loop : loop.text}.`)
  ]);
  addSection("The next agent", [
    "Loaded the saved handoff instead of relying on the previous agent's running process.",
    ...(data.b.patch.includes(".strip().lower()") ? ["Fixed handling of capital letters and extra spaces."] : ["Made the completion patch shown in the evidence below."]),
    testResult(data.b.full_test)
  ]);
  addSection("What happens next", [
    data.b.handoff.next_clean_action,
    data.b.handoff.open_loops.length === 0 ? "No open work is listed in the final handoff." : `${data.b.handoff.open_loops.length} open items remain.`,
    data.b.handoff.what_is_unverified.length === 0 ? "No unverified claims remain in the final handoff." : `${data.b.handoff.what_is_unverified.length} claims still need verification.`,
    data.b.handoff.what_needs_human_approval.length === 0 ? "No human approval items are recorded." : `${data.b.handoff.what_needs_human_approval.length} items need human review.`,
    "This demonstrates one recorded task, not a broad benchmark score."
  ]);
  const evidenceHeading = document.createElement("h2");
  evidenceHeading.textContent = "Inspect evidence";
  sectionsEl.appendChild(evidenceHeading);
  addEvidence("A: saved partial patch", data.a.patch);
  addEvidence("A: targeted tests", testText(data.a.targeted_test));
  addEvidence("A: full-suite failures", testText(data.a.full_test));
  addEvidence("Stored Yare handoff from A (original record)", JSON.stringify(data.a.recorded_handoff || data.a.handoff, null, 2));
  if (data.a.classification_corrections?.length) {
    addEvidence("Evidence-based classification correction", JSON.stringify({
      corrections: data.a.classification_corrections, handoff: data.a.handoff,
      note: "Corrected view derived from the recorded full-suite output; original stored record and hashes are unchanged."
    }, null, 2));
  }
  if (data.b.assessment) {
    addEvidence("B: recorded handoff assessment (agent statement)", JSON.stringify(data.b.assessment, null, 2));
  }
  addEvidence("B: saved completion patch", data.b.patch);
  addEvidence("B: full-suite test output", testText(data.b.full_test));
  addEvidence("Stored Yare handoff from B", JSON.stringify(data.b.handoff, null, 2));
  addEvidence("Recorded access decisions", [
    `A: policy allows read = ${data.a.access.policy_allows_read}; command exit = ${data.a.access.exit_code}`,
    `B: policy allows read = ${data.b.access.policy_allows_read}; command exit = ${data.b.access.exit_code}`,
    data.b.access.stderr,
    `Task snapshot hash: ${data.a.access.source_sha256}`, data.scope
  ].filter(Boolean).join("\n"));
  const finalState = data.b.handoff;
  const lines = values => values.length
    ? values.map(value => `- ${typeof value === "string" ? value : value.text}`).join("\n")
    : "None recorded.";
  handoffTextEl.textContent = [
    "Yare coding handoff", "",
    "The first agent left a partial fix. Yare saved its code, test results and unfinished work in CockroachDB. A fresh agent loaded that handoff and completed the fix.", "",
    "What changed", lines(finalState.what_changed),
    ...(data.b.patch.includes(".strip().lower()") ? ["The fix now handles capital letters and extra spaces."] : []), "",
    "What the tests show", `First agent, focused checks: ${testResult(data.a.targeted_test)}`,
    `First agent, full checks: ${testResult(data.a.full_test)}`,
    `Next agent, full checks: ${testResult(data.b.full_test)}`, "",
    "What the first agent's test results disproved", lines(data.a.handoff.what_contradicts_prior_state), "",
    "What remains unverified from the first handoff", lines(data.a.handoff.what_is_unverified), "",
    "What is still unverified", lines(finalState.what_is_unverified), "",
    "Contradictions", lines(finalState.what_contradicts_prior_state), "",
    "Needs human review", lines(finalState.what_needs_human_approval), "",
    "Unfinished work", lines(finalState.open_loops), "",
    "Next action", finalState.next_clean_action, "",
    "This is one recorded coding task. Reading it does not start a new agent run.",
    "Technical patches, logs and record identifiers are available in the demo's evidence sections and JSON download."
  ].join("\n");
}

function renderChain(data) {
  setText("handoffTask", "A fresh agent picked up each saved handoff");
  const grid = document.getElementById("chainRecordGrid");
  grid.replaceChildren();
  const names = { normalize_status: "Clean up status text", classify_claim: "Check claims against evidence",
    summarize_claims: "Count what is verified or unresolved", choose_next_action: "Choose what needs attention next" };
  sectionsEl.replaceChildren();
  addSection("What happened", [
    "One fixed brief described four small coding behaviors. Each agent chose one unfinished behavior to implement.",
    "Yare saved each change and its test results in CockroachDB. The next agent started fresh from that stored handoff.",
    "A's successful record was reused after controller fixes; B, C and D then continued from it."
  ]);
  const timeline = document.createElement("ol");
  timeline.className = "chain-timeline";
  for (const stage of data.stages) {
    const item = document.createElement("li");
    item.className = "chain-step";
    const letter = document.createElement("strong");
    letter.textContent = stage.agent;
    const body = document.createElement("div");
    const heading = document.createElement("h3");
    heading.textContent = names[stage.selected_function] || stage.selected_function;
    const result = document.createElement("p");
    result.className = "chain-result";
    result.textContent = `${stage.test_summary.passed}/${stage.test_summary.total} checks passing after this agent`;
    const continuity = document.createElement("p");
    continuity.textContent = stage.parent_handoff
      ? `Loaded ${String.fromCharCode(stage.agent.charCodeAt(0) - 1)}'s saved code and test evidence; then chose its next change.`
      : "Started the task. Its verified saved result was reused for the continuation.";
    body.append(heading, result, continuity);
    item.append(letter, body);
    timeline.appendChild(item);
    for (const [label, value] of [["run ID", stage.run_id], ["state hash", stage.current_state_hash], ["receipt hash", stage.receipt_hash]]) {
      const meta = document.createElement("div");
      meta.className = "meta-item";
      const title = document.createElement("span");
      title.textContent = `${stage.agent} ${label}`;
      const code = document.createElement("code");
      code.textContent = value;
      meta.append(title, code);
      grid.appendChild(meta);
    }
  }
  sectionsEl.appendChild(timeline);
  addSection("The visible result", [
    "All 16 task checks passed after D's change.",
    "A separate verifier loaded D's saved code and passed 8 additional acceptance checks that were not shown to the coding agents.",
    "Those 8 results are a separate saved controller report, not evidence bound into the agent receipts."
  ]);
  addSection("What this shows", [data.scope + ".",
    "The controller limited each turn to one behavior. Agents chose their work and implementation; the controller handled tests and handoff packaging.",
    "This is not indefinite autonomy or a broad coding benchmark. Loading the view makes no model calls."
  ]);
  const evidenceHeading = document.createElement("h2");
  evidenceHeading.textContent = "Inspect the saved evidence";
  sectionsEl.appendChild(evidenceHeading);
  for (const stage of data.stages) {
    addEvidence(`${stage.agent}: patch and tests`, [stage.patch, "Focused checks", testText(stage.targeted_test),
      "Full suite after this change", testText(stage.full_test)].join("\n\n"));
    addEvidence(`${stage.agent}: stored handoff and receipt link`, JSON.stringify({
      run_id: stage.run_id, current_state_hash: stage.current_state_hash, receipt_hash: stage.receipt_hash,
      source_sha256: stage.source_sha256, parent_handoff: stage.parent_handoff,
      model: stage.coding_model, selection_reason: stage.selection_reason,
      assessment: stage.assessment, handoff: stage.handoff
    }, null, 2));
  }
  addEvidence("Separate verifier: 8 acceptance checks (saved controller report)", JSON.stringify(data.acceptance, null, 2));
  handoffTextEl.textContent = ["Yare four-agent handoff", "", data.scope + ".", "",
    "Each agent chose one unfinished coding behavior from the same brief. Yare saved its code and test evidence in CockroachDB before the next fresh agent continued.", "",
    ...data.stages.map(stage => `Agent ${stage.agent}: ${names[stage.selected_function] || stage.selected_function}. ${stage.test_summary.passed}/${stage.test_summary.total} checks passing.`), "",
    "Final result: 16/16 visible checks passed. A separate verifier passed 8/8 unseen acceptance checks on D's saved code.",
    "The 8 acceptance results are a separate saved controller report, not bound into the agent receipts.", "",
    "A's verified saved record was reused after controller fixes; fresh B, C and D continued from it. The controller limited each agent to one behavior per turn.",
    "One bounded, resumed chain; not indefinite autonomy or a broad benchmark. Loading this evidence does not start agents or make model calls."
  ].join("\n");
}

function setView(next) {
  view = next;
  requestId += 1;
  verifiedHandoff = null;
  copyButton.disabled = true;
  downloadButton.disabled = true;
  loadButton.disabled = false;
  for (const [id, selected] of [["viewChain", view === "chain"], ["viewPair", view === "pair"]]) {
    document.getElementById(id).setAttribute("aria-selected", String(selected));
  }
  document.getElementById("pairIdentifiers").hidden = view !== "pair";
  document.getElementById("chainIdentifiers").hidden = view !== "chain";
  sectionsEl.setAttribute("aria-labelledby", view === "chain" ? "viewChain" : "viewPair");
  sectionsEl.replaceChildren();
  document.getElementById("chainRecordGrid").replaceChildren();
  for (const phase of ["a", "b"]) {
    for (const field of ["RunId", "StateHash", "ReceiptHash"]) setText(phase + field, "none");
  }
  handoffTextEl.textContent = "No recorded run loaded.";
  const label = view === "chain" ? "Load recorded chain" : "Load verified handoff";
  loadButton.textContent = label;
  setText("loadLabel", label);
  setText("demoTitle", view === "chain" ? "Four agents. One saved chain." : "One agent stopped. The next finished.");
  setText("demoStory", view === "chain"
    ? "Each agent picked one unfinished behavior, tested its change, and saved a handoff for a fresh agent."
    : "Yare saved the first agent's code, failing tests and unfinished work. A fresh agent loaded that handoff and completed the fix.");
  setText("demoScope", view === "chain"
    ? "One bounded, resumed four-agent chain after controller fixes. This is saved evidence, not a new model run."
    : "One earlier recorded A/B task. Loading it reads saved evidence; it does not start agents or make new model calls.");
  setText("handoffTask", view === "chain" ? "Load the chain to see each handoff." : "Load the handoff to see what happened.");
  statusEl.textContent = view === "chain" ? "Waiting for recorded chain" : "Waiting for verified handoff";
}

async function copyText(value) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const area = document.createElement("textarea");
  area.value = value;
  area.setAttribute("readonly", "");
  document.body.appendChild(area);
  area.select();
  const copied = document.execCommand("copy");
  area.remove();
  if (!copied) throw new Error("Copy unavailable");
}

function downloadJson(payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = view === "chain" ? "verified-yare-chain.json" : "verified-yare-handoff.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

loadButton.addEventListener("click", async () => {
  const currentRequest = ++requestId;
  const currentView = view;
  statusEl.textContent = "Loading verified CockroachDB records...";
  loadButton.disabled = true;
  verifiedHandoff = null;
  copyButton.disabled = true;
  downloadButton.disabled = true;
  try {
    const response = await fetch(currentView === "chain" ? "/api/verified-chain" : "/api/verified-handoff");
    if (!response.ok) throw new Error("Verified handoff is not available");
    const data = await response.json();
    if (currentRequest !== requestId) return;
    verifiedHandoff = data;
    if (currentView === "chain") renderChain(data);
    else render(data);
    copyButton.disabled = false;
    downloadButton.disabled = false;
    statusEl.textContent = currentView === "chain" ? "Four saved handoffs loaded from CockroachDB" : "Recorded handoff loaded from CockroachDB";
  } catch (error) {
    if (currentRequest !== requestId) return;
    statusEl.textContent = error.message;
    sectionsEl.replaceChildren();
    handoffTextEl.textContent = error.message;
  } finally {
    if (currentRequest === requestId) loadButton.disabled = false;
  }
});

document.getElementById("viewChain").addEventListener("click", () => setView("chain"));
document.getElementById("viewPair").addEventListener("click", () => setView("pair"));
setView("chain");

copyButton.addEventListener("click", async () => {
  try {
    await copyText(handoffTextEl.textContent);
    statusEl.textContent = "Handoff copied";
  } catch {
    statusEl.textContent = "Copy unavailable";
  }
});

downloadButton.addEventListener("click", () => {
  if (!verifiedHandoff) return;
  downloadJson(verifiedHandoff);
  statusEl.textContent = "JSON downloaded";
});
