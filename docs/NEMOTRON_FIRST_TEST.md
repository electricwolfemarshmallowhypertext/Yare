# Nemotron Producer: First Live Coding Test

Status: PASS for one coding producer smoke, run on October 7, 2026.

This test called Nebius Token Factory, edited a disposable Python repository,
and ran its tests through OpenShell v0.1.2. It does not establish the complete
two-agent handoff, restart continuity, distinct permission scopes, or provider
credential routing inside OpenShell. Those checks were pending at the time of
this first test; later results are linked below.

Follow-up: [the live A/B result](NEMOTRON_HANDOFF_RESULT.md) documents durable
handoff and restart. Its filesystem denial used a planted canary, not a
meaningful real-work boundary. Figures below describe the initial test
allowance, before its later increase to 50 total calls.

## Model Verification

An authenticated `GET https://api.tokenfactory.nebius.com/v1/models` confirmed:

- Coding: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`.
- Explanation: `nvidia/nemotron-3-super-120b-a12b`.

The configured coding ID matched case-insensitively; the producer used the
canonical capitalization returned by the service. The env file was not modified.

Official catalog rates observed for this run, USD per million tokens:

| Model | Input | Output |
| --- | ---: | ---: |
| Nano | 0.06 | 0.24 |
| Super | 0.30 | 0.90 |

Sources:
- https://tokenfactory.nebius.com/models/catalog/text2text/nvidia%2FNVIDIA-Nemotron-3-Nano-30B-A3B
- https://tokenfactory.nebius.com/models/catalog/text2text/nvidia%2Fnemotron-3-super-120b-a12b

Costs below are token-based estimates at these observed rates, not a billing
statement. Recheck rates before future runs.

## Observed Result

The initial test suite ran four tests and failed
`test_verified_requires_evidence`: a claim without evidence was incorrectly
classified as verified.

Nano inspected source and tests, proposed an edit, and applied this change:

```diff
     if status == "verified":
-        return "verified"
+        return "unresolved" if not evidence_present else "verified"
```

Final test command inside OpenShell:

```text
python -m unittest -v test_workstate
```

Observed output:

```text
test_contradiction_is_preserved ... ok
test_supported_verified_claim ... ok
test_unverified_stays_unresolved ... ok
test_verified_requires_evidence ... ok
Ran 4 tests
OK
```

The producer independently ran the tests again and confirmed exit code 0.
Super then explained the supplied actual test output and diff.

The first attempt stopped after two calls because the model proposed an edit
before reading the tests. No edit was applied. The harness was updated to return
that rejection as feedback. The subsequent attempt completed; its costs were
added to the same ledger, not reset.

- Total inference calls, including the failed attempt: 9.
- Estimated total: USD 0.00145086.
- Approved limit: USD 5 and maximum 12 calls across this initial test allowance.
- Remaining calls: 3. The producer will not reset the ledger automatically.
- Final source SHA256: `d6f7ae64ddb09027eb675307e736ab83c2fddac883706b9176225ff56ec7796b`.
- `coding-result.json` SHA256: `dfa1664752de2e49f130e25e4933d7f805d62f28e881218926c430170a6cb964`.

Raw request/response metadata, actions, usage, diff, tests, and explanation are
stored locally in ignored `.tmp/nebius-first-test/`. No credentials enter model
prompts, sandbox uploads, or result files. The Token Factory requests originate
from the host controller; generated code executes inside OpenShell.

The supplied CockroachDB connection answered a read-only `SELECT 1`. This test
did not write or retrieve a Yare handoff.

## Setup and Commands

Requires Windows with Ubuntu WSL2, Docker, and the authenticated OpenShell
gateway `yare`. Windows support is experimental. The local pinned CLI is under
`.tmp/openshell-v0.1.2/`; local client configuration is under its `config/`
directory. The gateway is bound to `https://127.0.0.1:17671` with mTLS.

Official installation and gateway setup:
- https://docs.nvidia.com/openshell/latest/about/installation
- https://docs.nvidia.com/openshell/latest/how-it-works/gateways/container-deployment

Privately populate the ignored `.env.nebius` with `NEBIUS_API_KEY`,
`NEBIUS_MODEL_ID`, `NEBIUS_EXPLAIN_MODEL_ID`, and `YARE_DATABASE_URL`.
Do not commit this file.

Commands used after gateway setup; the local repository path is redacted as `<repo-root>`:

```powershell
python -m pytest -q tests/producers/test_nemotron.py tests/yare/test_yare_cli.py
python -m py_compile producers/nemotron.py
wsl -d Ubuntu -- env XDG_CONFIG_HOME=<repo-root>/.tmp/openshell-v0.1.2/config <repo-root>/.tmp/openshell-v0.1.2/openshell -g yare sandbox create --name yare-nemotron-first --from python:3.12-slim --detach -- python -c 'import time; time.sleep(3600)'
wsl -d Ubuntu -- env XDG_CONFIG_HOME=<repo-root>/.tmp/openshell-v0.1.2/config <repo-root>/.tmp/openshell-v0.1.2/openshell -g yare sandbox upload yare-nemotron-first <repo-root>/examples/nemotron-task /tmp/yare-task
python -m producers.nemotron --sandbox yare-nemotron-first
```

Fixture checks cover test-failure retry, rejected premature edits, unexecuted
success claims, call exhaustion across restart, dollar exhaustion, and missing
usage. Final combined verification: 42 tests passed (7 producer tests and 35
existing CLI tests). Doctor, Python syntax, and diff whitespace checks passed.
Fixture results are not live-model proof.

## Limitations

- This is a narrow smoke task, not a general coding benchmark.
- Model edits are restricted to `workstate.py`; tests cannot be edited through
  the producer tools. The sandbox uses its default policy for this smoke.
- The budget ledger supports one sequential controller. Parallel agents need
  coordinated accounting before they are enabled.
- Unknown charges retain the pre-request reservation and stop the test.
- Docker/workload images and the model service can change independently;
  the OpenShell components are pinned to v0.1.2.
- At the time of this first smoke, A/B policies, forbidden-access evidence,
  durable handoff, restart proof, and public judge access were pending. The
  later A/B and routed results cover handoff, restart, and a synthetic file
  denial; meaningful boundary proof and public upgrade access remain open.
