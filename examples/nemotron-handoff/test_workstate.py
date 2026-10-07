import unittest
from workstate import classify_claim


class ClaimTests(unittest.TestCase):
    def test_verified_requires_evidence(self):
        self.assertEqual(classify_claim("verified", False), "unresolved")

    def test_supported_verified_claim(self):
        self.assertEqual(classify_claim("verified", True), "verified")

    def test_unverified_stays_unresolved(self):
        self.assertEqual(classify_claim("unverified", True), "unresolved")

    def test_contradiction_is_preserved(self):
        self.assertEqual(classify_claim("contradicted", True), "contradicted")


class NormalizationTests(unittest.TestCase):
    def test_verified_case_and_whitespace(self):
        self.assertEqual(classify_claim(" VERIFIED ", True), "verified")

    def test_contradicted_case_and_whitespace(self):
        self.assertEqual(classify_claim(" CONTRADICTED ", True), "contradicted")
