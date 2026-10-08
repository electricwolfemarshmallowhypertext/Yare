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
}

function render(data) {
  setText("handoffTask", data.task);
  for (const phase of ["a", "b"]) {
    setText(`${phase}RunId`, data[phase].run_id);
    setText(`${phase}StateHash`, data[phase].current_state_hash);
    setText(`${phase}ReceiptHash`, data[phase].receipt_hash);
  }
  sectionsEl.replaceChildren();
  addSection("A: partial handoff", [data.a.result, `Next action: ${data.a.next_action}`]);
  addSection("B: completion", [data.b.result, `Next action: ${data.b.next_action}`]);
  addSection("Access and scope", [data.source_access, data.scope]);
  handoffTextEl.textContent = [
    "Yare verified A/B handoff", "", `Task: ${data.task}`, "",
    `A: ${data.a.result}`, `A state: ${data.a.current_state_hash}`,
    `A receipt: ${data.a.receipt_hash}`, "",
    `B: ${data.b.result}`, `B state: ${data.b.current_state_hash}`,
    `B receipt: ${data.b.receipt_hash}`, "", data.source_access,
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
  try {
    const response = await fetch("/api/verified-handoff");
    if (!response.ok) throw new Error("Verified handoff is not available");
    verifiedHandoff = await response.json();
    render(verifiedHandoff);
    copyButton.disabled = false;
    downloadButton.disabled = false;
    statusEl.textContent = "Loaded two verified CockroachDB records";
  } catch (error) {
    statusEl.textContent = error.message;
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
