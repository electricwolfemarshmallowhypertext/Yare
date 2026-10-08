const fs = require("node:fs");
const { createHash } = require("node:crypto");
const { Pool } = require("pg");
const { summarizeLedger, seedBlockedBudget } = require("../api/lib/public-model-ledger");

async function main() {
  if (process.argv.length !== 3 || process.env.YARE_PUBLIC_MODEL_ENABLED === "true" ||
      !process.env.YARE_PUBLIC_BUDGET_ID || !process.env.YARE_DATABASE_URL ||
      !process.env.YARE_DATABASE_CA_PEM) {
    throw new Error("Blocked seed prerequisites missing");
  }
  const raw = fs.readFileSync(process.argv[2]);
  const digest = createHash("sha256").update(raw).digest("hex");
  const summary = summarizeLedger(JSON.parse(raw.toString("utf8")));
  const pool = new Pool({ connectionString: process.env.YARE_DATABASE_URL,
    ssl: { ca: process.env.YARE_DATABASE_CA_PEM, rejectUnauthorized: true }, max: 1 });
  try {
    await seedBlockedBudget(pool, process.env.YARE_PUBLIC_BUDGET_ID, summary);
    const after = createHash("sha256").update(fs.readFileSync(process.argv[2])).digest("hex");
    if (after !== digest) throw new Error("Ledger changed during blocked seed");
    process.stdout.write("Blocked budget row seeded; public model execution remains disabled\n");
  } finally {
    await pool.end();
  }
}

main().catch(() => {
  process.stderr.write("Blocked budget seed failed; review row state before retrying\n");
  process.exitCode = 1;
});
