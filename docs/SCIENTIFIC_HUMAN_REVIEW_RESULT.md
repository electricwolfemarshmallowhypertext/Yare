# Scientific Continuity and Human Review Result

November 24, 2026. Local branch `scientific-work-continuity`. Not published.

| Finding | Result |
| --- | --- |
| Work-state continuity | PASSED for these three bounded investigations |
| Scientific reasoning acceptance | FAILED |
| New model generations for D/review | 0 |

Yare preserved the investigation, including the participating model's errors.
Passing storage, provenance and continuity checks did not make those errors true.
The result is relevant to evidence challenge and continuity when collaborators
change. It does not establish scientific correctness or Stanford affiliation.

## Actual Human Decision

The owner supplied this decision in chat after reviewing the A/B/C outcome:

> Defer source classification. Retain the duplicated hypotheses, disputed unit statements, unresolved Gaia associations and unsupported trend claim. Request diagnostic follow-up only.

Three separately bound D records contain that exact text. D uses execution type
`human_decision` and tool `scientific-human-decision`; it is not labeled as a
model-generated agent. The operator-supplied decision is hash-bound to each C
receipt, not cryptographic authentication of the reviewer's identity.

## What Was Fixed

Review findings now identify duplicated hypothesis groups, unit-error statements,
unsupported trend wording and unresolved Gaia questions without changing the
original model statements or removing duplicate entries. The erroneous unit
statements remain disputed or unverified, alongside the authoritative correction.

The source reference is the frozen public
[Gaia DR3 column definition](https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_datamodel/sec_dm_main_source_catalogue/ssec_dm_gaia_source.html).
It identifies `ra_error` and `dec_error` as milliarcseconds (`mas`), not degrees.
The downloaded document SHA-256 is
`800bf953fa4d5b63c4f7dabe024753eb4fc987833b6265e57ec5030d9d558c0c`.
The bundle includes the original document, selected definitions and their hashes.
No attempt was made to improve Qwen's scientific reasoning or generate a better
hypothesis. No hypothesis was promoted to a verified scientific fact.

The deterministic path permits only D, an actual bound review and no new reasoning.
The loader checks its review findings. Altered findings fail even if an attacker
recalculates the outer packet and receipt hashes. Existing scripted fixtures
remain backward compatible and keep their original execution labels.

## Persistence and Retention

The original nine A/B/C run IDs, state hashes and receipt hashes were queried
again and matched the pre-review identities. Their saved files, all 24 original
local provider responses and negative attempts also matched the pre-review byte
fingerprints. Nothing was silently corrected in those records.

Each D was compiled through the existing Yare path, committed to CockroachDB and
loaded back with state, receipt, scientific provenance and parent verification.
All datasets, analysis, 100 observations with uncertainties, hypotheses,
disagreements and unresolved questions equal the corresponding C contents.
Diagnostic-only recommendations record the unresolved questions; they do not
schedule observations, execute diagnostics or authorize paid resources.

| D run ID | Receipt SHA-256 |
| --- | --- |
| `public-science-local-20261124-1-d` | `2978e766f4c68916bc8c6c59d88e5fb8e47cd4cae32bc8d6bad3eadee5714433` |
| `public-science-local-20261124-2-d` | `281e54ae7e08770171d22f5d9ed72514f673d181a82dd4987c47dca51caafa22` |
| `public-science-local-20261124-3-d` | `fcd56b85162729eb5daf286301f980b207d5bb844e491a8b564a8663e5e846a6` |

Final scoped database counts: 12 each in runs, artifacts, states, receipts,
snapshots and events; 81 section-vector rows. Nine live/human parent links were
verified. The original envelope remained unchanged: 75 SELECT statements,
153 INSERT statements and 10,213,440 bytes of inserted string parameters across
the entire live pilot and this review. No DDL, UPDATE, DELETE or grants ran.
The SELECT allowance is now exhausted; no further live query was issued.

D compile/commit/local-write timings were 1,270.957-1,314.311 ms; DB reload plus
verification took 459.034-479.275 ms. These are small-sample measurements, not
isolated persistence timing or scale/throughput guarantees.

## Regression Results

- Focused scientific/decision tests: 52 passed before live D execution.
- Complete supported Python suite (`tests/`, as configured in CI): 214 passed,
  2 skipped. The opt-in live integration test had no explicit test URL; the other
  skip is the existing Windows symlink limitation. The new live D evidence is
  separate from these fixtures.
- Complete supported Node suite (`tests/site/*.cjs`, `site/tests/*.test.js`):
  42 passed, no failures or skips.
- Legacy `apps/api/tests` collection remains blocked by missing `firebase_admin`.
  Its fixtures also use external Firebase and flush a Redis test database. They
  were not executed or repaired as part of this scientific review. No claim is
  made that every retained legacy-stack test passed.

Raw local test outputs are retained separately; the sanitized bundle includes
the result summary without machine names or private filesystem metadata.

## Evidence Bundle Scope

The combined review bundle includes the original offline bundle unchanged,
its extracted original files, all 12 new live/human handoffs, original rejected
provider responses, source/data fingerprints, human decisions, Gaia unit reference
and standalone verification code. Original receipts are copied, not redacted or
re-signed. Private configuration, the spending ledger itself, internal TODO,
host-specific diagnostic tracebacks and unrelated work are excluded. Their local
originals are preserved. Screening is not a universal secret-detection guarantee.

The verifier uses only Python's standard library, no Yare import or credentials.
It checks the 12 original offline records and 12 live/human records, both sets of
nine parent links, provider transcript bindings, D decisions, retained negative
evidence and frozen bytes. Optional calculation reproduction runs only the
separately inspectable pinned program, never code embedded inside a handoff.

A captured bundle does not itself contact CockroachDB, authenticate the model
provider or reviewer, or provide independent service attestation. Live read-back
is recorded evidence from this execution, not a claim that an offline verifier
can re-establish a current network connection.

## Unchanged Boundaries

The paid ledger remains byte-identical: 495/500 calls, USD 5 total cap and
2 million tokens. SHA-256:
`e3138784251046976ef395cf5e4060ed91912e9c0f770d7cd37b8c04973dcbb7`.
The local-generation count remains 24; D added zero. The local freeze tag still
points to `3d5a8d81297df52ad304a1062e0c0fc77a6269b0`.

No paid provider, AWS operation, model server, new database schema, frontend,
architecture expansion, commit, push, deployment or publication was introduced.
Stop for owner review. The earlier live-pilot report remains historical evidence
of the A/B/C phase before this explicit human decision.
