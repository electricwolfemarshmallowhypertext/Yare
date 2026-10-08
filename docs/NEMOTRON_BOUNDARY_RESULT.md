# Nemotron Task-Source Boundary Result

Status on October 7, 2026: **PASS for a same-file OpenShell denial in the
sandboxed task-source snapshot, durable A/B handoff, and B's final tests.**

## Source and Policy Preflight

The source was the existing `examples/nemotron-handoff/workstate.py` from this
checkout, not a newly written brief or canary. The image was built with only
`examples/nemotron-handoff` as Docker context. Both sandboxes used image
`yare-nemotron-boundary:local` (`sha256:f6d040df1adc800a00a577cb2c1d030ab921a3be521772b67739467b4b929a37`).
It contains the original task-source snapshot at
`/opt/yare-original-checkout/workstate.py` and a separate writable task copy.
Outside OpenShell, the original file existed in that image with mode `0644`
and SHA256 `b095a4c7fc1e9b7873cbf45090f463ef7c7dda2e0549eeb591f679a66581df4c`.

Before any new model call, `openshell policy get <sandbox> --full -o json` showed
both effective policies using UID 1000 and Landlock `hard_requirement`. A's
effective read-only paths included `/opt/yare-original-checkout`; B's did not.
The effective policy hashes were:

| Sandbox policy | Hash | Same-file `sha256sum` |
| --- | --- | --- |
| A | `263fed37d61729688dbe56c4df6b155b74d71e3d9da2a82cdc258b64575593b1` | exit 0, expected source hash |
| B | `45e15682ad3c3ca30caa7919390be94e2b0f975f56889ecef3dde310d98200d2` | exit 1, `Permission denied` |

The identical world-readable file was present in the common image. This is a
policy denial for the sandboxed snapshot, not an absent file or Unix mode
denial. The tested boundary is the sandboxed snapshot.

## Live Handoff

Commands used for the coding phases:

```powershell
python -m producers.handoff --phase a --run-id nebius-boundary-20261007 --sandbox yare-boundary-a --routed --stop-on-refresh --boundary-original
python -m producers.handoff --phase b --run-id nebius-boundary-20261007 --sandbox yare-boundary-b2 --routed --stop-on-refresh --boundary-original
```

A read the original source snapshot, wrote the evidence check in its task copy,
passed four targeted tests, and left two normalization failures in the six-test
full suite. Its artifact, including the observed source-access result and
effective policy hash, was compiled through Yare and read back from CockroachDB.
A was stopped before a fresh B sandbox was created. B's editable `workstate.py`
was then loaded from A's stored Lead Artifact, not A's process or sandbox.

B's first attempt assessed the handoff and read its working file, then stopped
*before* another model request: the next reservation required 23,519 tokens,
but only 21,686 remained under the 200,000-token ledger allowance. No edit or
B receipt resulted. With user approval, only the token ceiling was raised to
250,000; the 67 existing calls, 100-call limit, and USD 5 cap were preserved.
B retried in the same still-unedited sandbox, correctly distinguished A's
partial pass from its failed full suite, normalized case and whitespace, and
passed all six full-suite tests. After coding, B could read its working copy
but still received `Permission denied` on the original snapshot path.

The live-run state/receipt hashes were:

| Run | Live state hash | Live receipt hash |
| --- | --- | --- |
| `nebius-boundary-20261007-a` | `8a6f90ebc335e2c4aa2910891cb57880b0b142bc1b6b81963292c6b369bdbda8` | `8f14d646417e3f699ad19cbe8c2bc187cb453786a5a067b44650a23a7e893105` |
| `nebius-boundary-20261007-b` | `d25e52c520b663e9f1eed870e04a47ed6f15ee36a8fec0daa95210fb8ab12c35` | `0a647a9b8eb37a21872a20d989115549d2270bdd1228cdba753efb4006aaa104` |

The original receipts named the access-bearing artifact paths but did not
directly hash the access payloads. An optional receipt evidence field was then
added without changing the default CLI format. The saved A/B artifacts were
recompiled **after the live run, without model calls**, producing these additional
access-bearing receipts:

| Run | Post-run state hash | Access-bearing receipt hash |
| --- | --- | --- |
| A | `5e53bbe6a5cae1a2ac56b2b810a95bd287026bca568cb551dd9024c7b69e4a41` | `65258c13083e38c77dc1b3077b0e18f0041abb434d8aa1a65c98a21e434eab2e` |
| B | `b141e9a891c620a82d05b6cb3c5bf369fad3bd1d1a046664f9da7d0972490762` | `ce666bf4e2f546fb451408ade4c76ac0a43357dd1b51db146614010d0d67cee8` |

CockroachDB now has two exact-run rows each in `yare_runs` and
`yare_lead_artifacts`, and four each in `yare_current_states` and
`yare_receipts` (two historical plus two post-run). Each new receipt's
`access_evidence` equals its stored artifact's access result; recomputing the
receipt hash including that field matches the stored hash.

The shared ledger ended at **74/100 calls**, **USD 0.02180184 conservatively
charged** under the unchanged USD 5 cap, and **203285/250000** charged tokens.
The first 67 call records were unchanged by the token-ceiling increase. Of all
74 calls, 73 have observed usage and one older call retains its reservation.

## Limit

The original task source was copied into both sandbox images. This verifies a
filesystem distinction over the same existing task source *inside the sandboxes*.
No distinct process or network permissions were tested. The task remains a
narrow isolated coding exercise, not a general repository benchmark.

Verification: `python -m pytest -q tests/producers tests/yare/test_yare_cli.py`
passed (56 tests); `python -m py_compile producers/nemotron.py producers/handoff.py cli/yare.py`
and `git diff --check` passed. No credentials are in this document or the
recorded access results.
