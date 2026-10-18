const { createHash } = require("node:crypto");

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map(key => `${canonical(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value).replace(/[\u0080-\uFFFF]/g,
    char => `\\u${char.charCodeAt(0).toString(16).padStart(4, "0")}`);
}

function hash(value) {
  return createHash("sha256").update(canonical(value)).digest("hex");
}

function withoutHash(value, key) {
  return Object.fromEntries(Object.entries(value).filter(([name]) => name !== key));
}

function stateHash(packet) {
  if (packet.hash_version !== "work-state.v2") return hash(withoutHash(packet, "deterministic_hash"));
  const excluded = new Set(["source_artifact", "git_state", "context_bundle_hash", "receipt_hash", "source_artifacts"]);
  const artifacts = packet.artifacts.map(artifact => Object.fromEntries(
    Object.entries(artifact).filter(([key]) => !excluded.has(key))));
  artifacts.sort((left, right) => hash(left).localeCompare(hash(right)));
  return hash({ hash_version: "work-state.v2", task: packet.task, current_state: packet.current_state, artifacts });
}

function publicText(value) {
  const text = String(value || "");
  if (/[A-Za-z]:[\\/]|\\\\[^\\\s]+\\|file:\/\/|\/(?:Users|home|root)\/|postgres(?:ql)?:\/\/|Bearer\s+|(?:API_KEY|PASSWORD)\s*[=:]/i.test(text)) {
    throw Error("private data in publication fields");
  }
  return text;
}

function checkPublicValue(value) {
  if (typeof value === "string") publicText(value);
  else if (Array.isArray(value)) value.forEach(checkPublicValue);
  else if (value && typeof value === "object") {
    for (const [key, item] of Object.entries(value)) {
      publicText(key);
      checkPublicValue(item);
    }
  }
}

function publicTest(value) {
  if (!value || !Array.isArray(value.command) || !Number.isInteger(value.exit_code) ||
      !(value.stdout || value.stderr)) throw Error("stored test evidence missing");
  return { command: value.command.map(publicText), exit_code: value.exit_code,
    stdout: publicText(value.stdout), stderr: publicText(value.stderr) };
}

function verifyRecord(row) {
  const receipt = row.receipt_json;
  const packet = receipt?.packet_snapshot || row.packet_json;
  if (!packet || packet.deterministic_hash !== row.current_state_hash ||
      stateHash(packet) !== row.current_state_hash ||
      (packet.hash_version === "work-state.v2" && receipt?.packet_hash !== hash(packet)) ||
      canonical(packet.current_state) !== canonical(row.state_json) ||
      !receipt || receipt.receipt_hash !== row.receipt_hash ||
      hash(withoutHash(receipt, "receipt_hash")) !== row.receipt_hash ||
      receipt.run_id !== row.run_id || receipt.current_state_hash !== row.current_state_hash) {
    throw Error("stored evidence hash mismatch");
  }
  const artifacts = packet.artifacts.filter(artifact => artifact.run_id === row.run_id);
  if (artifacts.length !== 1) throw Error("stored source is ambiguous");
  const evidence = artifacts[0].evidence;
  if (!evidence || typeof evidence.source_code !== "string" ||
      createHash("sha256").update(evidence.source_code).digest("hex") !== evidence.source_sha256 ||
      typeof evidence.diff !== "string") throw Error("stored source evidence missing");
  return { packet, evidence, receipt };
}

module.exports = { canonical, hash, publicText, checkPublicValue, publicTest, verifyRecord };
