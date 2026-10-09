const loadButton = document.getElementById("loadHandoff");
const copyButton = document.getElementById("copyHandoff");
const downloadButton = document.getElementById("downloadJson");
const statusEl = document.getElementById("demoStatus");
const sectionsEl = document.getElementById("handoffSections");
const handoffTextEl = document.getElementById("handoffText");

let verifiedHandoff = null;

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
  const section = addSection(title, []);
  const output = document.createElement("pre");
  output.className = "evidence-output";
  output.textContent = value || "No output recorded.";
  section.appendChild(output);
}

function testText(test) {
  return [`$ ${test.command.join(" ")}`, `Exit code: ${test.exit_code}`,
    test.stdout, test.stderr].filter(Boolean).join("\n");
}

function render(data) {
  setText("handoffTask", data.task);
  for (const phase of ["a", "b"]) {
    setText(`${phase}RunId`, data[phase].run_id);
    setText(`${phase}StateHash`, data[phase].current_state_hash);
    setText(`${phase}ReceiptHash`, data[phase].receipt_hash);
  }
  sectionsEl.replaceChildren();
  addEvidence("A: saved partial patch", data.a.patch);
  addEvidence("A: targeted tests", testText(data.a.targeted_test));
  addEvidence("A: full-suite failures", testText(data.a.full_test));
  addEvidence("Stored Yare handoff from A", JSON.stringify(data.a.handoff, null, 2));
  if (data.b.assessment) {
    addEvidence("B: recorded handoff assessment (agent statement)", JSON.stringify(data.b.assessment, null, 2));
  }
  addEvidence("B: saved completion patch", data.b.patch);
  addEvidence("B: full-suite test output", testText(data.b.full_test));
  addEvidence("Stored Yare handoff from B", JSON.stringify(data.b.handoff, null, 2));
  addSection("Recorded access decisions", [
    `A: policy allows read = ${data.a.access.policy_allows_read}; command exit = ${data.a.access.exit_code}`,
    `B: policy allows read = ${data.b.access.policy_allows_read}; command exit = ${data.b.access.exit_code}`,
    data.b.access.stderr,
    `Task snapshot hash: ${data.a.access.source_sha256}`, data.scope
  ]);
  handoffTextEl.textContent = [
    "Yare recorded A/B evidence", "", `Task: ${data.task}`, "",
    "A patch", data.a.patch, "A targeted tests", testText(data.a.targeted_test),
    "A full suite", testText(data.a.full_test), "A stored handoff", JSON.stringify(data.a.handoff, null, 2),
    `A state: ${data.a.current_state_hash}`, `A receipt: ${data.a.receipt_hash}`, "",
    "B patch", data.b.patch, "B full suite", testText(data.b.full_test),
    "B recorded assessment (agent statement)", JSON.stringify(data.b.assessment, null, 2),
    "B stored handoff", JSON.stringify(data.b.handoff, null, 2),
    `B state: ${data.b.current_state_hash}`, `B receipt: ${data.b.receipt_hash}`, "",
    "Access decisions", JSON.stringify({ a: data.a.access, b: data.b.access }, null, 2),
    data.scope, "", data.summary_source
  ].join("\n");
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
  link.download = "verified-yare-handoff.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

loadButton.addEventListener("click", async () => {
  statusEl.textContent = "Loading verified CockroachDB records...";
  loadButton.disabled = true;
  verifiedHandoff = null;
  copyButton.disabled = true;
  downloadButton.disabled = true;
  try {
    const response = await fetch("/api/verified-handoff");
    if (!response.ok) throw new Error("Verified handoff is not available");
    verifiedHandoff = await response.json();
    render(verifiedHandoff);
    copyButton.disabled = false;
    downloadButton.disabled = false;
    statusEl.textContent = "Loaded saved patches, tests and handoffs from CockroachDB";
  } catch (error) {
    statusEl.textContent = error.message;
    sectionsEl.replaceChildren();
    handoffTextEl.textContent = error.message;
  } finally {
    loadButton.disabled = false;
  }
});

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
