# Scientific Work Continuity

Status: local implementation, not published. No Stanford affiliation, integration
or endorsement is implied. This example preserves Yare's general-purpose Lead
Artifact and existing CockroachDB tables. No frontend or new database schema.

## Evidence Boundaries

- `evidence.scientific` uses `scientific-evidence.v1`; other artifacts remain valid.
- Compiler normalization validates the contract and retains every scientific field.
- Verified loading checks the original state, packet and receipt, then dataset,
  selected-row and analysis-source/result hashes. It never executes embedded code.
- The example producer additionally verifies each exact parent and preserves prior
  observations, hypotheses, disagreements and open questions. The generic loader
  does not recursively query or authenticate the whole parent chain.
- Observations are separate from hypotheses. No hypothesis can carry `verified`
  status in this contract. A passing calculation is not a verified interpretation.
- Review is operator-supplied, bound to C's receipt, and not authenticated identity
  or a cryptographic signature. D refuses to run without that record.
- The producer in this pass records explicitly scripted fixture requests. It does
  not call a model or establish model-generated reasoning, even in Cockroach mode.

## Public Data

Frozen on November 24, 2026. Only public observations were downloaded:

- ZTF DR24 object `686103400034440`: original SNAD JSON, 724 light-curve rows.
  The analysis selects the first 100 rows in response order, in band `zg`.
  [SNAD API](https://db.ztf.snad.space/api/v3/help)
- Gaia DR3: original ESA CSV, three positional candidates in the recorded cone
  query. These are contextual candidates, not confirmed counterparts.
  [Gaia query documentation](https://docs.astropy.org/projects/astroquery/en/latest/gaia/gaia.html)

Exact endpoints, query parameters, releases, acquisition times and response hashes
are in `examples/scientific-handoff/data/manifest.json`. Each handoff embeds the
original bytes, row selectors, selected-row hashes, observation uncertainties,
analysis code, parameters and Python version. ZTF's MJD time scale remains labeled
`unverified`; no unsupported UTC label is introduced. Gaia epoch/proper-motion
matching is not implemented.

The primary IRSA light-curve endpoint timed out during acquisition; no data were
invented or silently substituted. The manifest explicitly identifies SNAD as the
ZTF access service. Archive byte hashes preserve integrity, not upstream scientific
validity or authenticated authorship. See the services' acknowledgment guidance
before redistributing a research publication.

## Offline Reproduction

Commands assume this unpublished implementation is available locally. They use
the bundled frozen public responses; no credentials, network or paid calls are
needed. Each output directory must be new to avoid overwriting evidence.

```powershell
python -m pytest -q tests/yare/test_scientific.py
python -m scripts.scientific_fixture --output .tmp/science-example
```

The second command runs three A/B/C repetitions in separate Python processes.
C restores its datasets and analysis parameters only from the verified parent
export, with the same fixed brief and pinned repository analysis program. D stops
pending an actual operator decision. These are local exports, not Cockroach proof.

After the operator provides a real decision:

```powershell
python -m scripts.scientific_fixture --output .tmp/science-example --reviewer OPERATOR --decision request_followup --review-note "ACTUAL OPERATOR DECISION"
python -m scripts.scientific_fixture --output .tmp/science-example --verify-only
```

Do not run the review command using an invented decision. It binds the supplied
decision separately to each C receipt and starts each D in a new process. A
diagnostic request does not settle hypotheses, close questions or schedule a
telescope. Reverification recomputes the analysis; it creates no new receipts.

To acquire a new snapshot, rather than reproduce this frozen one:

```powershell
python -m scripts.freeze_scientific_data --output .tmp/new-public-snapshot
python -m producers.scientific prepare --manifest .tmp/new-public-snapshot/manifest.json --output .tmp/new-analysis/bundle.json
```

Requests under `examples/scientific-handoff/requests/` are specific to the bundled
selection. New objects require reviewing the request references and science brief;
this example is not a general astronomy classifier.

## Cockroach Adapter, Not Run Live in This Pass

This explicitly enabled mode uses existing `YARE_DATABASE_URL`, compilation,
persistence and verified loading. It never reads a key file, changes the schema,
calls a model or invokes S3. The default remains offline. No live execution is
authorized by these instructions; the example below is for later approved use.

```powershell
python -m producers.scientific stage --storage cockroach --bundle .tmp/science-example/bundle.json --stage A --investigation-id UNIQUE_ID --run-id UNIQUE_ID-a --reasoning examples/scientific-handoff/requests/a.json --output .tmp/UNIQUE_ID/a
python -m producers.scientific stage --storage cockroach --stage B --investigation-id UNIQUE_ID --run-id UNIQUE_ID-b --parent-run-id UNIQUE_ID-a --reasoning examples/scientific-handoff/requests/b.json --output .tmp/UNIQUE_ID/b
```

C uses the same command shape with `--stage C`, B's run ID and `requests/c.json`.
Record the actual decision with `producers.scientific review --parent-run-id
UNIQUE_ID-c`; its help lists the required operator fields. D requires the resulting
`--human-review` file. Keep all stages in one investigation and use fresh run IDs.
The scientific adapter was validated against an explicitly fake DB-API driver,
not a new live Cockroach run. A future live-model producer must separately capture
provider metadata, preserve the shared budget, constrain its tools, and bind real
model reasoning to these records. None is claimed here.

## Acceptance and Limits

Offline acceptance: exact scientific-field retention through compiler, SQL
parameters, fake-driver reload and local exports; altered data/source/rows/results/
receipts rejected; calculation rows and units cannot silently change; all parent
links checked; disagreements/questions retained; D blocked without bound review.
Synthetic corruption and synthetic review unit tests are not real evidence or
actual approvals. The research fixture uses the owner's actual decision.

Descriptive statistics assume independent reported measurement errors and omit
systematics, correlations, calibration assessment and scientific classification.
Storage embeds snapshots repeatedly: measured export bytes are not physical
Cockroach size. Local timings are not database latency or throughput. Six fixed
question-routing checks use fake candidate rows, not ANN quality or semantic
accuracy. Live model reasoning, live science storage, survey-scale operation,
scientific correctness and discovery acceleration remain unverified.
