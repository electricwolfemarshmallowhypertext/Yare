# Four-Agent Handoff Chain Result

Recorded October 17, 2026: **PASS for a bounded, resumed A -> B -> C -> D coding chain.**

Four fresh agent processes chose work from one fixed task brief. Each used an isolated OpenShell sandbox. B, C, and D loaded their predecessor's code and test evidence from CockroachDB, not a prior chat or sandbox. The controller checked the exact state, source, receipt, and parent associations.

## Observed Result

| Agent | Model-selected function | Full visible suite after the change |
| --- | --- | --- |
| A | `normalize_status` | 4/16 passed |
| B | `classify_claim` | 8/16 passed |
| C | `summarize_claims` | 12/16 passed |
| D | `choose_next_action` | 16/16 passed |

All coding calls used `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` through Nebius Token Factory. The configured model was checked against the live model list. Each agent chose a failing function and supplied its implementation; no function was assigned to a particular agent, and no human repair code or issue-specific fix was supplied during execution.

The fixed brief requires one function per turn. The controller handles turn boundaries, validation, test execution, handoff packaging, and sandbox lifecycle. This demonstrates bounded work selection and durable continuity, not independent discovery of an unrestricted task plan.

## Restart and Independent Verification

A's valid stored result came from `nebius-chain-20261017-r3-a`. The continuation `nebius-chain-20261017-r5` reused that exact record after controller protocol corrections, without rerunning or editing A's saved result. B, C, and D were fresh processes and sandboxes. This was a resumed chain, not one uninterrupted attempt. The task brief remained identical; the controller's action encoding was revised during development.

Each run-owned sandbox was stopped and deleted before its successor started. After D, a separate non-model verifier sandbox loaded D's source from CockroachDB and observed:

```text
Visible suite: 16 tests, 0 failures, 0 skips, exit 0
Separate acceptance cases: 8 tests, 0 failures, 0 skips, exit 0
Exact stored record read-backs: 4
Verified parent links: 3
```

The eight acceptance cases were not in the agent image, tools, or prompts. They are controller-owned checks for this task, not an external benchmark score. No task source was attached from a host checkout.

Final read-only database counts across the four exact run IDs were:

| Table | Rows |
| --- | --- |
| `yare_runs` | 4 |
| `yare_lead_artifacts` | 4 |
| `yare_current_states` | 4 |
| `yare_receipts` | 4 |
| `yare_events` | 4 |

## Record Identifiers

| Agent | Run ID |
| --- | --- |
| A | `nebius-chain-20261017-r3-a` |
| B | `nebius-chain-20261017-r5-b` |
| C | `nebius-chain-20261017-r5-c` |
| D | `nebius-chain-20261017-r5-d` |

| Agent | State hash |
| --- | --- |
| A | `0508a8ee53de771800156807af5bc0f92119dafd11792468c733097dfd17b9bf` |
| B | `4c5f64b24d5fcb6aa7a2a5506bf1cf5c6228a31833c0e3886756c3204a36fb8f` |
| C | `5fe86ae47980ad3c5dd0e15837445a4b721abc565fabc045249a49c1eb622c3d` |
| D | `4d5cd023b82fe023e82816f423edcc6011586caaf5c9f6db9c49a30c7f176a0d` |

| Agent | Receipt hash |
| --- | --- |
| A | `0db4ef273b6fc34649101444cd957f1611d72c73cdddf2712036eca289bda27b` |
| B | `6044c517f2a7dab71f3652f2f66d116c4f9dd5a0916d85ff074084a78dec506d` |
| C | `7400fffa72f67d150ab61d27abd4e9c8a66671eb1d430ac7ae36d1e12d04c60c` |
| D | `2418829ba48842816907a4aa21faeaefaa556b53e8b783ad0bc76f61b8f7ae12` |

The common task-brief SHA256 was `bd44d8800fdfe2c74781205a1ce97a42f3f024b101b5965ca63a4a420f5e64f4`.

## Commands and Evidence Scope

```powershell
docker build -t yare-nemotron-chain:local examples/nemotron-chain
python -m producers.chain --run-id nebius-chain-20261017-r3
python -m producers.chain --run-id nebius-chain-20261017-r5 --seed-a nebius-chain-20261017-r3-a
```

The first command sequence produced A's valid record; its B phase did not complete. The final command continued from A and completed B, C, D, and independent acceptance. These exact historical IDs cannot be rerun because the runner rejects existing evidence and database IDs; use new IDs for a new execution.

The effective successful stages used 35 paid calls: A 16, B 7, C 6, D 6. The B/C/D continuation used 19 of those calls; that is not the total development usage. All other attempt charges remain in the original shared ledger. Original entries and spending/call/token limits were preserved, not reset. Raw traces, usage accounting, failed attempts, and the final manifest remain private under ignored `.tmp/chain/`.

Focused offline controller checks: **14 passed**. Those scripted fixtures are separate from the live result. Final exact-record identity guards were also applied in read-only checks to all four live records after the run.

The task-specific source and tests are under `examples/nemotron-chain/`; the runner is `producers/chain.py`. See [runner documentation](AGENT_CHAIN.md).

The coding run made no frontend changes, deployment, AWS calls, or public model activation. Run-owned sandboxes were removed and the local gateway was stopped afterward. The subsequent read-only chain viewer is separate from coding execution: it loads the four pinned database records and displays the separate saved acceptance report. Loading it does not repeat this run. The earlier A/B view remains available.

This result establishes continuity on one small, deliberately staged exercise after controller engineering. It does not establish indefinite autonomous operation, broad coding accuracy, or general benchmark performance.
