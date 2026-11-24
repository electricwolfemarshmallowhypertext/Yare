# Yare Scientific Evidence Review Bundle

Work-state continuity: **PASSED** for three bounded investigations.
Scientific reasoning acceptance: **FAILED**.

This local bundle preserves both the original offline evaluation and the later
captured local-model/Cockroach evaluation. D records the owner's explicit human
decision deterministically; it is not an additional model run. Bad model reasoning
was retained and flagged, not repaired into a passing scientific result.

Inspect `verify.py`, `shared_verifier.py` and `offline/analysis.py` before running:

```text
python verify.py
python verify.py --reproduce
```

Both commands require only Python's standard library. They make no network,
database or model call. `--reproduce` runs the separately bundled pinned
descriptive analysis. It does not execute source strings from a receipt.

Expected coverage: 12 offline fixture records, 9 live-model records, 3 deterministic
human D records, 9 offline and 9 live/human parent links, 24 retained original
local responses and zero further generations. Reproduction covers 24 saved
calculations. This does not establish scientific correctness or broad autonomy.

Contents:

- `original-offline-bundle.zip` and `offline/`: exact original accepted bundle and
  its files, including original source fingerprints, records and fixture decisions.
- `live/records/`: original receipt-bearing Cockroach handoff exports, including D.
- `live/originals/`: byte-identical prior transcripts, rejected attempts and handoffs.
- `live/reviews/`: the actual human decision, separately bound to each live C receipt.
- `live/unit-reference/`: public ESA Gaia document, unit definitions and hashes.
- `source/`: final controller source for inspection, not a claim that each earlier
  resumed attempt used that final revision.
- `docs/`: results and limitations. Private logs/configuration are not included.

Each receipt and transcript is checked against its recorded hash. The original
offline ZIP is also checked against its previously recorded SHA-256. Checksums
are not third-party signatures. Model/reviewer identities and historical database
access are not independently authenticated by this offline bundle.

The owner deferred source classification, retained duplicates, disputed unit
statements, unresolved Gaia associations and the unsupported trend claim, and
requested diagnostic follow-up only. No observations, spending or publication
were authorized. Further work stops for review.
