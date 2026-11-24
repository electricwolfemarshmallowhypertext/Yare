# Yare Scientific Continuity: Offline Evidence Bundle

This private review package contains **scripted offline evidence only**. It does
not prove live model reasoning, live CockroachDB persistence, scientific correctness
or Stanford affiliation. No upload, release or publication has been authorized.

## Verify Without Yare or Network

Inspect `verify.py` first. It uses Python 3.11+ and the standard library only.
No packages, credentials, model, server or network connection are required.

```powershell
python verify.py
```

After reviewing the separately bundled analysis source, independently reproduce
the calculations as well:

```powershell
python verify.py --reproduce
```

The second command runs only the separately inspectable, hash-pinned `analysis.py`
with temporary input files. It never executes code embedded in a receipt. Neither
command runs agents, queries a database, changes the ledger or calls a provider.

Expected scope: **12 original records, 9 parent links, 3 scripted repetitions**.
Optional reproduction checks all 12 descriptive calculations. Hypotheses remain
unverified/disputed, and the actual recorded diagnostic-only decision does not
settle the scientific questions or authenticate a reviewer identity.

## Contents and Integrity

- `manifest.json`: SHA-256 allowlist of every other bundle file.
- `checkpoint.json`: original run/state/receipt identities and source fingerprints.
- `records/`: original receipt-bearing exports, copied byte-for-byte, without
  redaction or rehashing. Hashes alone do not authenticate their creator.
- `data/`: original public ZTF/Gaia response bytes and acquisition manifest.
- `analysis.py`, `brief.md`, `scientific-evidence.schema.json`: pinned calculation,
  brief and full schema for inspection. The standalone verifier checks critical
  bindings, not every JSON Schema keyword.
- `source/`: the 19 fingerprinted implementation/data inputs, including focused
  test source. No private configuration, ledger, TODO, unrelated experiments,
  dependency caches or host-directory listing is included.
- `docs/SCIENTIFIC_EVALUATION_RESULT.md`, `docs/SCIENTIFIC_REPORT_REVIEW.md`:
  reported results and their evidence boundaries.
- `docs/SCIENTIFIC_LIVE_VALIDATION_PLAN.md`: proposed zero-new-bill method; not executed.

The accompanying ZIP checksum protects transport only. A self-generated manifest
is not an external signature, scientific certification or proof of model execution.
Recorded test counts are historical command results, not established by the bundle
verifier; independently rerun tests using the source if those counts matter.

## Inspect or Rebuild the Source

The baseline is public commit `3d5a8d81297df52ad304a1062e0c0fc77a6269b0` of
`https://github.com/electricwolfemarshmallowhypertext/Yare`. The scientific changes
remain local and unpublished. To reconstruct the reviewed implementation, obtain
that baseline and overlay `source/` at its repository root. It contains the changed
runtime files, scientific schema/producer/tests, example requests and frozen data.
Then install the baseline CLI requirements plus pytest and run:

```powershell
python -m pytest -q tests/yare/test_scientific.py
```

The two original skipped baseline cases were a deliberately unconfigured live DB
test and an unavailable Windows symlink capability. The local artifact bundle
does not convert either skipped check into a pass.

Data services: `https://db.ztf.snad.space/api/v3/help` and the Gaia DR3 public TAP
interface recorded in `data/manifest.json`. Frozen bytes support exact arithmetic
reproduction; fresh upstream responses can change and must not silently replace
the recorded inputs. No source classification or confirmed Gaia match is claimed.
