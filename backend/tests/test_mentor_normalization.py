"""Basic fuzz/property tests for Mentor normalization."""

import random
import string
import unicodedata

from app.services.mentor.normalization import normalize_query, normalize_unicode


def test_normalization_idempotent_ascii():
    cases = ["Find PhD scholarships in Europe", "phd stipend germany", "IELTS 6.5 GPA 3.0"]
    for c in cases:
        r1 = normalize_query(c)["normalized_query"]
        r2 = normalize_query(r1)["normalized_query"]
        assert r1 == r2


def test_normalization_does_not_crash_arbitrary():
    rng = random.Random(42)
    for _ in range(2000):
        n = rng.randint(0, 40)
        s = "".join(rng.choice(string.printable + "\u0985\u09be\u09c1") for _ in range(n))
        try:
            normalize_query(s)
            normalize_unicode(s)
        except Exception as e:
            raise AssertionError(f"crashed on {s!r}: {e}")


def test_original_query_preserved():
    q = "Find PhD scholarships"
    r = normalize_query(q)
    assert r["original_query"] == q
