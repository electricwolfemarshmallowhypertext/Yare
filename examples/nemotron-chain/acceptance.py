"""Controller-only acceptance cases, not included in the agent image or prompt."""

import unittest

from workstate import classify_claim, choose_next_action, normalize_status, summarize_claims


class AcceptanceTests(unittest.TestCase):
    def test_normalize_tabs(self):
        self.assertEqual(normalize_status("\t UNRESOLVED \r\n"), "unresolved")

    def test_normalize_number(self):
        self.assertEqual(normalize_status(12), "unknown")

    def test_evidence_is_boolean(self):
        self.assertEqual(classify_claim("verified", 1), "unresolved")

    def test_contradiction_with_evidence(self):
        self.assertEqual(classify_claim("contradicted", True), "contradicted")

    def test_summary_unknowns(self):
        self.assertEqual(summarize_claims(["pending", "unresolved", "verified", "contradicted", "other"]),
                         {"verified": 1, "unresolved": 3, "contradicted": 1})

    def test_summary_no_mutation(self):
        claims = ["verified", "contradicted", "verified"]
        summarize_claims(claims)
        self.assertEqual(claims, ["verified", "contradicted", "verified"])

    def test_action_priority(self):
        self.assertEqual(choose_next_action({"verified": 20, "contradicted": 2, "unresolved": 3}),
                         "review contradictions")

    def test_action_zero(self):
        self.assertEqual(choose_next_action({"contradicted": 0, "unresolved": 0}), "complete")
