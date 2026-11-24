# Scientific Continuity: Offline Evaluation Result

Date: November 24, 2026. Status: **PASS for the implemented offline scope only.**
This is not a live scientific-agent result, Cockroach science smoke, scientific
certification, observatory-scale benchmark or Stanford endorsement. Nothing was
pushed, released or deployed. See [setup and limitations](SCIENTIFIC_WORK_CONTINUITY.md).

## Freeze and Scope

Local annotated tag `pre-Stanford-HAI` points to published baseline
`3d5a8d81297df52ad304a1062e0c0fc77a6269b0` (tree
`0207bf426308ad48778547da15e612616baf4d79`). Work is isolated on local branch
`scientific-work-continuity`; the legacy and published upgrade branches are
unchanged. Five earlier untracked experiments were retained outside this worktree,
not deleted or included. Baseline: **157 Python passed, 2 skipped; 42 Node passed**.

The owner explicitly selected implementation/offline validation only. No model
calls, live Cockroach operations or AWS calls occurred. The existing ledger remained
byte-for-byte unchanged: **495/500 calls, 2,000,000-token ceiling, USD 5 total cap**.

## Genuine Public Inputs

Original response bytes and their acquisition manifests are bundled. ZTF DR24 via
SNAD supplied 724 photometric rows; the example selected the first 100 response
rows in the same `zg` band. Gaia DR3 supplied three positional candidates. No
counterpart identification is asserted. [SNAD API](https://db.ztf.snad.space/api/v3/help),
[Gaia query interface](https://docs.astropy.org/projects/astroquery/en/latest/gaia/gaia.html).

| Input | SHA-256 |
| --- | --- |
| ZTF original JSON | `dae88cb94a72315c3977e3035ec9f3284705b27fb2329848c9923782988a7abd` |
| Gaia original CSV | `232b0343642941f8a9dd5dfe62d595681b8014dc7de01d4e511a95c0bab46f5e` |
| Analysis source | `71273444a6e5f2981a1526a6c5f6e4798d758fa98136e340214c71179b51a240` |

Primary IRSA acquisition timed out; the final manifest explicitly records SNAD,
not IRSA, as the data access service. Observation time-scale interpretation remains
unverified. Source fingerprints, 12 state/receipt identities, timings and exact
parameters are preserved in [evaluation-checkpoint.json](../examples/scientific-handoff/evaluation-checkpoint.json).
Raw exports and the detailed evaluation manifest remain in the ignored local
`.tmp/scientific-evaluation-final-20261124/` directory. The checkpoint is not a
self-contained replacement for those raw receipts and snapshots.

## Observed Offline Results

| Check | Actual result |
| --- | --- |
| Scripted repetitions | Three A -> B -> C -> D repetitions; each role used a fresh Python process |
| Record verification | 12 exact state/receipt identities; 9 exact parent links |
| Replacement context | C recovered frozen data and parameters from its verified predecessor, not earlier process memory |
| Preserved state | 100 measurements with uncertainties; two competing hypotheses; one open disagreement; three open questions |
| Human gate | D blocked before a real decision; three review records later bound separately to C's receipts |
| Actual owner decision | "Request diagnostic follow-up only; keep classification unverified" |
| D output | Diagnostic recommendations only; disagreement/questions retained; no observing action authorized |
| Persistence adapter | Existing SQL write/read functions passed fake DB-API roundtrips; no new schema |
| Question routing | 6/6 predefined section-routing checks using fake candidate rows from real compiled exports |
| Regression | 189 Python passed, 2 skipped; 42 Node passed; 32 scientific cases included |
| Other checks | Python syntax, doctor, tracked diff whitespace and final saved-export reverification passed |

The six routing questions cover human review, changed files, unfinished work,
unverified claims, contradictions and next action. Candidate distances are synthetic
in the fake driver: this is not ANN recall, semantic quality or live retrieval
accuracy. Corruption checks cover datasets, selected rows, analysis source/results,
observations and uncertainties, references, parent changes, vanished evidence and
invalid reviews. Existing generic receipt-integrity regressions also passed.

The two skips are the explicitly opt-in live integrity test and a Windows symlink
test unavailable on this machine. They are not counted as passing checks.

## Descriptive Calculation, Not Scientific Conclusion

Across 100 measurements, the weighted mean magnitude was 17.63221564042117 with
reported-error-only standard error 0.0028572491721974166 mag. The endpoint change
was 0.022276000000001517 +/- 0.04178694528491688 mag. Constant-model chi-squared
was 262.3120756345987 with 99 degrees of freedom. These calculations motivate the
scripted disagreement between endpoint-only and whole-series interpretations.
They do not identify the source class or distinguish intrinsic variation from
systematics. Correlated errors and calibration effects are not modeled.

Python was 3.12.10. Reproduction tolerance was 1e-12 relative and absolute; all
12 saved analyses reverified against the pinned repository program. Embedded
source strings were not executed.

## Measured Limits

Offline compile plus internal local-output writes took **150.117-272.251 ms**
(excluding the final handoff export write); local JSON reload plus
verification ranged **8.675-9.441 ms** across the 12 records. Exports occupied
**325,433-334,603 bytes each**, totaling **3,967,578 bytes**. These figures exclude
other artifact files and are not physical Cockroach storage, database latency,
concurrent-load results or a throughput guarantee. Snapshots duplicate data; this
example should not ingest a survey-wide alert stream.

## Reproduction Commands

```powershell
python -m pytest -q -rs tests/
python -m scripts.scientific_fixture --output .tmp/scientific-evaluation-final-20261124
python -m scripts.scientific_fixture --output .tmp/scientific-evaluation-final-20261124 --reviewer user-in-chat --decision request_followup --review-note "Request diagnostic follow-up only; keep classification unverified"
python -m scripts.scientific_fixture --output .tmp/scientific-evaluation-final-20261124 --verify-only
python -m cli.yare doctor
```

The first fixture command requires a new output directory. The review command
above documents the actual decision authorized for this evaluation; it is not
standing authorization for other investigations. For a new investigation, obtain
a new operator decision before D. Run Node coverage with the same `node --test`
file list used by `.github/workflows/ci.yml` and already-installed site dependencies.

## Remaining Unverified

Live scientific model-generated reasoning and three live-agent repetitions were
not authorized and were not run. Live science persistence/read-back, database
latency, physical database storage growth and live retrieval accuracy are also
unmeasured. The adapter is implemented, but its fake-driver tests do not establish
those properties. There is no scientific correctness, discovery acceleration,
Stanford affiliation, observatory integration or scale claim. Stop for review.
