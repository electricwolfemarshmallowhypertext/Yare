# SWE-bench Verified A/B Result

Status: **heavily guided, 1/1 issue**. This is a real one-instance result, not a broad benchmark score or proof of autonomous general performance.

- Instance: `pytest-dev__pytest-10356`, pinned base `3c1534944cbd34e8a41bc9e76818018fadefc9a1`.
- Agent A produced a partial patch and failing test evidence. Yare stored its artifact in CockroachDB. A receipt: `7e2682b27df197ba97125f32a907260af2cf7dc4b30bce8119595cae65bec05f`.
- Fresh Agent B read A's stored handoff, edited its separate public pytest checkout, and passed the target test. B receipt: `48f114913b562cbea92cd1255a3028ae930d998394cdded425c7fa819c1474fe`.
- Official SWE-bench evaluation: patch applied; `1/1` instance resolved; `testing/test_mark.py::test_mark_mro` passed; no pass-to-pass failures. Test summary: `89 passed, 1 xfailed`. The expected failure is `TestKeywordSelection::test_keyword_extra_dash`, not the issue test.
- Shared Token Factory ledger after this run: `205/500` calls, `383173/2000000` charged tokens, estimated `$0.03923190` under the unchanged `$5` cap. The increase to 500 calls did not add model calls.

The source-boundary test used a snapshot of the public task checkout inside OpenShell. The official report, test output, and patch are retained in ignored local evidence under `.tmp/swebench-verified/swebench-pytest-10356-20261007/b/`; they are not included in this repository. No published fix was fed to the agent. Local diagnostic guidance was substantial.
