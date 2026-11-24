import unittest

from workstate import classify_claim, choose_next_action, normalize_status, summarize_claims


class NormalizationTests(unittest.TestCase):
    def test_case(self):
        self.assertEqual(normalize_status("Verified"), "verified")

    def test_whitespace(self):
        self.assertEqual(normalize_status("  contradicted\n"), "contradicted")

    def test_empty(self):
        self.assertEqual(normalize_status("  "), "unknown")

    def test_non_string(self):
        self.assertEqual(normalize_status(None), "unknown")


class ClassificationTests(unittest.TestCase):
    def test_supported(self):
        self.assertEqual(classify_claim("verified", True), "verified")

    def test_unsupported(self):
        self.assertEqual(classify_claim("verified", False), "unresolved")

    def test_contradicted(self):
        self.assertEqual(classify_claim("contradicted", False), "contradicted")

    def test_unknown(self):
        self.assertEqual(classify_claim("unknown", True), "unresolved")


class SummaryTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(summarize_claims([]), {"verified": 0, "contradicted": 0, "unresolved": 0})

    def test_repeated(self):
        self.assertEqual(summarize_claims(["verified", "verified"]),
                         {"verified": 2, "contradicted": 0, "unresolved": 0})

    def test_mixed(self):
        self.assertEqual(summarize_claims(["verified", "contradicted", "unresolved"]),
                         {"verified": 1, "contradicted": 1, "unresolved": 1})

    def test_unknown(self):
        self.assertEqual(summarize_claims(["other"]), {"verified": 0, "contradicted": 0, "unresolved": 1})


class ActionTests(unittest.TestCase):
    def test_contradictions_first(self):
        self.assertEqual(choose_next_action({"contradicted": 1, "unresolved": 2}), "review contradictions")

    def test_unresolved(self):
        self.assertEqual(choose_next_action({"unresolved": 1}), "verify unresolved claims")

    def test_finished(self):
        self.assertEqual(choose_next_action({"verified": 4, "unresolved": 0}), "complete")

    def test_missing_counts(self):
        self.assertEqual(choose_next_action({}), "complete")
