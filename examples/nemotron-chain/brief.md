# Work-state utilities

Complete the four functions in workstate.py according to these contracts:

- normalize_status(value): strip surrounding whitespace and lowercase strings. Return "unknown" for non-strings or an empty result.
- classify_claim(status, evidence_present): canonical "contradicted" stays contradicted. Canonical "verified" is verified only when evidence_present is exactly True. Otherwise return "unresolved". Inputs here are already normalized.
- summarize_claims(claims): return counts for "verified", "contradicted", and "unresolved", including zero counts. Each unknown classification counts as unresolved. An empty list gives all zero counts.
- choose_next_action(counts): return "review contradictions" when the contradicted count is positive; otherwise "verify unresolved claims" when unresolved is positive; otherwise "complete". Missing counts are zero.

Inspect the code and tests. Choose the next failing behavior yourself. During this turn, implement exactly one function, verify it, and leave an evidence-backed handoff for the next agent. Do not change signatures, other functions, or tests. The controller will check the full suite after every turn and run separate acceptance cases at the end.

Do not treat a focused test pass as a full-suite pass. Do not claim any result without observed test evidence. Do not request human repair instructions. This is a bounded exercise, not an open-ended agent service.
