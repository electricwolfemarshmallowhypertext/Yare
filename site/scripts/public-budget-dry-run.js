const fs = require("node:fs");
const { summarizeLedger } = require("../api/lib/public-model-ledger");

if (process.argv.length !== 3) {
  process.stderr.write("Usage: node site/scripts/public-budget-dry-run.js <ignored-ledger-path>\n");
  process.exitCode = 2;
} else {
  try {
    const state = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
    process.stdout.write(`${JSON.stringify(summarizeLedger(state), null, 2)}\n`);
  } catch {
    process.stderr.write("Private ledger cannot be reconciled\n");
    process.exitCode = 1;
  }
}
