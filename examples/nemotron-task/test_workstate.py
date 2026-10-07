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


if __name__ == "__main__":
    unittest.main()
