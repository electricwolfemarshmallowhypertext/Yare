# Four-Agent Handoff Chain

This runner exercises A -> B -> C -> D on one isolated Python task. It is a bounded continuity check, not an open-ended autonomous service or a general coding benchmark. A successful result must come from a real run, not the offline fixtures.

## Fixed Task and Turn Boundary

All four agents receive the same [brief](../examples/nemotron-chain/brief.md), action protocol, and visible test file. The brief describes four utility contracts. The controller does not assign a function or supply a repair to any agent. Each agent chooses one currently failing function, edits only that function, and runs its focused tests before handing off. This one-function turn boundary deliberately creates four handoffs; the number of turns is not an independently discovered plan.

The loop accepts schema-checked read, assessment, work-selection, edit, test, and handoff actions. Edits are an array of lines for the selected function body, not an escaped whole-file string. The controller joins and indents those lines, preserves other functions, and validates the resulting Python before writing. Model-supplied command output is rejected. Only the controller executes tests. It closes a turn after an observed focused pass, independently reruns the checks, and creates the handoff. Two consecutive invalid actions or identical edit rejections stop the run with responses retained privately. Each turn has at most 16 calls, additionally constrained by the existing shared ledger; no caps are raised or reset.

The request uses Token Factory's [strict JSON-schema output](https://docs.tokenfactory.nebius.com/ai-models-inference/json). The controller constrains the next protocol step (read, assess, select, edit, test), not the selected function or its implementation. The model must still interpret the stored test results correctly; valid JSON alone is not accepted as proof.

## Durable Continuity

Each stage runs in a new Python process and a new OpenShell sandbox. After the stage, its sandbox is stopped and deleted before the next one starts. The image contains only the initial task source and visible tests; there is no host checkout attachment.

Before B, C, or D starts coding, it loads the preceding run from CockroachDB using the existing state/source/receipt verifier. The controller installs the verified saved source in that fresh sandbox. The agent sees a bounded projection of the saved state, focused and full-suite test counts and failure identifiers, prior work selection, and a generic controller next-action statement. Complete logs remain in saved evidence. It does not receive the previous model conversation or the controller's repair hints. Work selection belongs to the agent; turn completion and handoff packaging belong to the controller.

The next agent must identify the exact parent state/receipt hashes and distinguish focused test results from full-suite results. Its output artifact records those parent identifiers. The controller compiles each artifact through the existing Yare path, reads it back, and checks that the evidence survived storage. Claims describe observed focused tests; unfinished full-suite checks remain open loops.

## Independent Acceptance

The controller reruns focused and full tests after every turn. A turn must fix exactly four previously failing visible checks without regressing any passing check. The expected progression is 4/16, 8/16, 12/16, then 16/16.

After D, a fifth, non-model verifier sandbox loads D's code from CockroachDB and runs the full visible suite plus eight separate acceptance cases. Those acceptance cases are outside the agent image, read tools, and model prompt. They are local task checks, not an external benchmark evaluator. The final controller also reloads all four records and checks the three exact parent links and common brief hash.

No public success claim is justified unless all stages, read-backs, final checks, parent links, ledger-preservation checks, and sandbox cleanup succeed.

## Commands

Prerequisites: the existing Yare OpenShell gateway, Docker, CLI dependencies, and the ignored `.env.nebius` containing `NEBIUS_API_KEY`, `NEBIUS_MODEL_ID`, and `YARE_DATABASE_URL`. The configured coding model must appear in Token Factory's live model list and have a known price in the existing budget implementation. The runner reads the environment file without editing it or printing credentials.

```powershell
docker build -t yare-nemotron-chain:local examples/nemotron-chain
python -m producers.chain --run-id your-unique-chain-id
```

To continue after a controller/protocol failure without paying for A again:

```powershell
python -m producers.chain --run-id your-unique-continuation-id --seed-a exact-stored-a-run-id
```

This verifies that the seed is an A record for the same brief with four passing visible tests and twelve failures remaining. It then runs fresh B, C, and D. The manifest names the original A and its unchanged hashes. Report this as a resumed chain, not one uninterrupted execution; failed attempts remain separate evidence.

The gateway must already be running. The runner creates and cleans only its own uniquely named sandboxes; the operator should stop a gateway started solely for this run afterward. Reusing a run ID with existing evidence or database records is rejected.

The runner requires the existing `.tmp/nebius-first-test/budget.json`. It refuses to create a replacement ledger. Evidence is written under ignored `.tmp/chain/<run-id>/`, including the original budget snapshot, action traces, provider request/response metadata, artifacts, effective policies, read-back records, process results, and final result. API keys are not included in those request records.

S3 is explicitly disabled for these compile calls. No frontend, public demo record selection, paid endpoint activation, or schema change is part of this runner.

## Verification Status

Offline fixtures exercise protocol rejection, one-function edit guards, scripted four-stage progression, parent assessment, and preservation of ledger entries and caps. Scripted fixture decisions are not evidence of model autonomy. Live results must be reported separately with their actual run ID, receipts, test totals, calls, and estimated cost.

## Read-Only Public View

The demo's four-agent tab calls `GET /api/verified-chain`. It selects four pinned state/receipt pairs listed in `site/public-chain.json`, verifies original record integrity and all three parent links, and projects only approved task fields. It does not accept arbitrary run IDs or make writes or model calls. The earlier A/B tab remains available.

The eight independent acceptance results are a committed export in `site/public-chain-acceptance.json`. Its output was compared with the original private controller report and names D's exact state and receipt. It is displayed separately and explicitly not represented as evidence bound into the agent receipts. The four coding records are fetched from CockroachDB; the acceptance output is a saved controller report.
