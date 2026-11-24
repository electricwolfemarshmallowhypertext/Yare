# Scientific Work Continuity Research Release

November 24, 2026. Release: `scientific-continuity-2026-11-24`.

[Release and downloads](https://github.com/electricwolfemarshmallowhypertext/Yare/releases/tag/scientific-continuity-2026-11-24) | [Evaluation report](SCIENTIFIC_HUMAN_REVIEW_RESULT.md) | [Technical architecture](ARCHITECTURE.md)

## Result

Yare preserved scientific work across replacement agents and an explicit human review. Work-state continuity passed for three bounded investigations; the participating model's scientific reasoning failed. Its duplicated hypotheses, disputed units, unsupported trend claim and unresolved Gaia associations remain in the evidence.

- Nine model-generated records and three deterministic human-review records were persisted in CockroachDB and read back. All 12 records and nine parent links were verified.
- The separate offline evaluation contains 12 scripted records and nine parent links. It is not live-agent evidence.
- Public ZTF and Gaia data, selected rows, measurement uncertainties, analysis parameters, source fingerprints and original receipts are included.
- D records the owner's diagnostic-only decision without another model generation or changes to the preceding evidence. It is not a fourth model-generated agent.
- The recorded supported regression suite passed 214 Python tests with two skips and 42 Node tests. Legacy Firebase/Redis tests were not executed; legacy collection was blocked by missing `firebase_admin`.
- The scientific evaluation used 24 local model generations and zero paid provider calls. Publication added no model generations, database operations or ledger changes.

The [offline report](SCIENTIFIC_EVALUATION_RESULT.md), [A/B/C live-pilot report](SCIENTIFIC_LIVE_PILOT_RESULT.md) and [human-review report](SCIENTIFIC_HUMAN_REVIEW_RESULT.md) are historical evaluation snapshots. Their original review-stage publication restrictions and test counts describe those stages, not a withdrawal of this approved release. The evidence archive preserves their original bytes.

## Evidence Download

[Download the combined evidence ZIP](https://github.com/electricwolfemarshmallowhypertext/Yare/releases/download/scientific-continuity-2026-11-24/yare-scientific-combined-review-20261124.zip) and its [SHA-256 file](https://github.com/electricwolfemarshmallowhypertext/Yare/releases/download/scientific-continuity-2026-11-24/yare-scientific-combined-review-20261124.zip.sha256).

ZIP SHA-256:

```text
74cce51671258c3070a7e2a10df0b2cd2c2255efdcdc1340e2dfedaa9bf26aaa
```

The original 3,406,233-byte archive is published unchanged. It includes retained failed responses and the unchanged original offline archive, not only successful records.

Inspect the bundled verifier and `offline/analysis.py` before executing them. With Python 3.11 or later, extract the archive and run from its directory:

```bash
python verify.py
python verify.py --reproduce
```

These standard-library commands require no credentials and make no network, model or database calls. Reproduction executes the inspectable pinned analysis program, not code embedded in a handoff. Expected coverage is 24 records, 18 parent links and 24 reproduced saved calculations across the two evaluations.

For the verifier from the tagged source export, run from the repository directory with the extracted evidence directory supplied explicitly:

```bash
python -I scripts/verify_scientific_review_bundle.py --root /path/to/extracted-evidence --reproduce
```

## Publication Checks

The standalone verifier passed from a clean Git source export. All 18 final controller fingerprints matched that export. Archive path/type checks and decoded-content privacy screening passed for 224 members, including the nested original archive. No original receipt was redacted or re-signed. Private configuration, credentials, the spending ledger, internal TODO and unrelated work are excluded from the evidence archive.

The publication PR's hosted CI run was canceled at the owner's request. GitHub Actions is disabled. The regression counts above are the recorded local evaluation results, not a claim that publication CI passed.

Screening is not a universal secret-detection guarantee. Hashes establish internal consistency, not third-party signatures. The offline verifier does not authenticate provider/reviewer identities or independently attest to historical CockroachDB access. No new live database check was performed for publication.

## Scope and Baselines

This release adds the optional scientific evidence contract, frozen public-data example, continuity producer, explicit human-decision recording path, regression coverage and standalone evidence verification. Yare remains general-purpose work-state memory; no astronomy platform, new database schema or frontend was added for the scientific pilot.

There is no claim of scientific correctness, improved discovery, autonomous scientific reliability, observatory-scale readiness, or Stanford affiliation or endorsement. Data time-scale interpretation and source classification remain unresolved. Small-sample timing measurements are not throughput guarantees.

`pre-Stanford-HAI` preserves baseline commit `3d5a8d81297df52ad304a1062e0c0fc77a6269b0`. `legacy-main-2026-11-24` preserves the previous public `main` tip, `0007821b06601aa85d7167e8185580c7fcbbfd67`. Both histories are retained by the merge. Paid public execution remains disabled; the existing website displays recorded coding evidence, not the scientific pilot.
