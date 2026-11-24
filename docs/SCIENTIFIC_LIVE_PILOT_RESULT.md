# Local Scientific Handoff Pilot

November 24, 2026. Local work on `scientific-work-continuity`; not published.

## Result

Three A -> B -> C sequences used actual local model generations and the existing
CockroachDB database. Nine records, six parent links, frozen observations and
calculation results were read back and checked. D did not run.

The continuity checks passed. Scientific reasoning acceptance did not pass.
All three B agents repeated A's hypothesis instead of supplying a genuinely
competing interpretation. Repetition two's B and C also described Gaia position
errors in degrees. The source columns use milliarcseconds, not degrees; see the
[Gaia DR3 column definitions](https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_datamodel/sec_dm_main_source_catalogue/ssec_dm_gaia_source.html).
These statements remain disputed or unverified, not confirmed observations.
Repetition three's C explicitly noticed that A and B had duplicate hypotheses
rather than a genuine disagreement. No stored record was rewritten to hide errors.

This is evidence of persisted work continuity across replacement sessions, not
scientific correctness, source classification, discovery, or an astronomy product.

## Execution

- Cached public `qwen3:4b`, via a dedicated loopback-only Ollama instance with
  `OLLAMA_NO_CLOUD=1`. The pinned manifest and all five referenced blobs were
  SHA-256 checked before inference. No model download or paid provider was used.
- Model digest: `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
- Nine distinct client processes and session IDs, empty message contexts per role.
  These are independent sessions of one model, not independent model families.
- Every model first requested the controller's pinned analysis, then supplied
  structured interpretation. The controller ran the real analysis program.
  Models did not write an analysis program or execute arbitrary shell commands.
- Context contained the fixed public brief, a bounded observation/provenance
  projection, actual analysis output, and verified parent hypotheses/questions.
  Replacements loaded their scientific data from CockroachDB, not an export or
  prior chat. Five ZTF rows were shown in the projection; all 100 selected rows
  and their uncertainties remained in each stored record and analysis input.
- Original frozen ZTF/Gaia bytes, analysis program, brief and parameters remained
  unchanged. No private project, credentials or host-directory mount was supplied
  to a model. This run did not use OpenShell sandboxes.

The first repetition was resumed after controller corrections. It is not an
uninterrupted first-attempt pass, and controller instructions/schema changed
during those corrections. The public investigation brief did not change.
The later two repetitions used the corrected controller without another retry.

## Failures Retained

1. A first produced a one-sided disagreement, rejected before any DB write.
2. A next reused an ID for a hypothesis and a question, also rejected. Execution
   stopped and the owner explicitly approved resuming after a controller fix.
3. A's third output was valid, but a relative artifact path broke compilation.
   Its captured response was reused after a path fix, with no new A generation.
4. B's first output again supplied one disagreement reference. Schema references
   were inlined so the local grammar could see the minimum cardinality.
5. C's output exposed status handling that marked disputes only at stage B.
   The controller was corrected for later stages. C's captured output was reused
   without a new generation. Scientific wording was not repaired by a human.

Raw requests, responses, tool results, rejected attempts and successful receipts
remain in the ignored local evidence directory. The original offline bundle and
its receipt identities were not replaced or relabeled.

## Measurements

| Measurement | Observed result |
| --- | --- |
| Local generations, including rejected attempts | 24 / 24 |
| Paid model calls | 0 |
| Provider-reported prompt/generated tokens, all attempts | 87,544 / 3,662 |
| Provider-reported total model duration, all attempts | 30.063 seconds; not total wall time |
| Durable runs/artifacts/states/receipts/snapshots/events | 9 in each table, scoped to this pilot |
| Section-vector rows | 60, scoped to this pilot |
| Parent links checked | 6 / 6 |
| Saved calculations reproduced | 9 / 9, at the existing tolerance |
| Predefined live section-routing questions | 6 / 6; not broad semantic-search quality |
| Compile, commit and local write | 1,293.222-1,672.114 ms per record; not DB-only latency |
| DB reload plus integrity validation | 453.034-513.726 ms per record |
| Serialized handoff exports | 3,589,946 bytes across nine exports |

The statement guard counted 114 INSERT statements, 56 SELECT statements and
7,941,101 bytes of inserted string payloads, within the declared statement/byte
bounds. No DDL, UPDATE, schema initialization or grants were performed.
All writes were confined to the nine new research run IDs; the public demo's
pinned coding records were not changed.

The cloud dashboard showed 48.44 thousand RUs and 30.82 MiB after the run, versus
13.1 thousand RUs and 22.37 MiB beforehand. This is an account-observed change,
not a perfectly isolated physical-size/RU attribution: monitoring, compaction and
other concurrent activity were not controlled. Configured limits stayed at
4 million RUs and 409 MiB. The earlier draft's 5-million-RU safety reserve was
not available under that configured limit; it was not represented as available.

Post-run billing for November 1-24 showed $0.02 gross usage, a matching $0.02 free
resource credit, and $0.00 net. Billing can lag; this is an observed total, not an
unlimited future no-charge guarantee. Local electricity was not measured.

The paid-provider ledger remained byte-identical at 495/500 calls, the USD 5 cap,
and the 2-million-token cap. SHA-256:
`e3138784251046976ef395cf5e4060ed91912e9c0f770d7cd37b8c04973dcbb7`.

## C Records for Review

| Run ID | Receipt SHA-256 |
| --- | --- |
| `public-science-local-20261124-1-c` | `10618ac22ba5808fb5d1c90275abcb0e24108ce90c5ebd2c9f6bd78482cfc4da` |
| `public-science-local-20261124-2-c` | `2deaaadaa313565b7d8349d065e023982889b1d3c138c368c591089f0f17eb9a` |
| `public-science-local-20261124-3-c` | `9ae03e77e83ba831c1ed17602fe597c9b18eb2d9c0c61e3068ed5c98ab6b0fe4` |

Each C retains 100 observations with uncertainties and three recorded open-question
entries. Those questions repeat the unresolved Gaia association question; entry
count does not mean three distinct research questions. Time scale remains
unverified. The source remains unclassified. A steady trend was not established
by the supplied descriptive calculations, regardless of the model's wording.

## Reproduction and Verification

The implementation is in [the local acquisition adapter](../producers/scientific_local.py),
[bounded runner](../scripts/scientific_live.py), and
[read-only reviewer](../scripts/review_scientific_live.py).
Actual execution used the runner, explicit resumed attempts, and captured-response
replay after controller-only failures. Do not rerun the same IDs or overwrite the
evidence directory. A future run needs new IDs and a separately reviewed local
generation allowance; all 24 generations in this pilot are consumed.

Focused offline checks: 44 passed, covering corruption, parent retention, provider
actions, trace hashes, the two schema failures, relative output and C's dispute
status. These fixtures do not establish model quality. The complete application
regression suite was not rerun for this live adapter change. Final controller
fingerprints were recorded; they are not fingerprints of every earlier revision
used before corrections. Provider transcripts are controller-captured, not signed
proof from an independent attestation service.

## Review Boundary

D has no execution path in the local entry point. No human decision has been
recorded for these three C receipts. The prior fixture decision was not reused.
The temporary local inference server and its model process are stopped. No
frontend, deployment, commit, push, release, or public publication occurred.

Before D, review the duplicated interpretations, unit errors and unsupported trend
claim. A scientific acceptance pass must not be inferred from transport/integrity
checks. Further model generations require a new local allowance; the paid ledger
and caps remain untouched.
