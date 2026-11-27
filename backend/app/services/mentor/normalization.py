"""Bangla/Banglish normalization helpers for Mentor query understanding.

Preserves the original user query; produces a normalized form used for search
and slot extraction only. Normalization is idempotent.
"""

from __future__ import annotations

import unicodedata
import re

# Bengali -> ASCII digit mapping
_BN_TO_ASCII = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_ASCII_TO_BN = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def normalize_unicode(text: str) -> str:
    if not isinstance(text, str):
        return ""
    # NFC normalization; careful with ZWJ/ZWNJ (keep them, do not delete).
    return unicodedata.normalize("NFC", text)


def to_ascii_digits(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return text.translate(_BN_TO_ASCII)


def to_bengali_digits(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return text.translate(_ASCII_TO_BN)


def normalize_query(text: str) -> dict:
    original = text if isinstance(text, str) else ""
    nfc = normalize_unicode(original)
    ascii_digits = to_ascii_digits(nfc)
    # Lowercase ASCII portion only; keep Bengali script case-insensitive (no case).
    lowered = ascii_digits.lower()
    return {
        "original_query": original,
        "normalized_query": lowered,
        "nfc": nfc,
        "ascii_digits": ascii_digits,
    }


def is_idempotent(text: str) -> bool:
    r1 = normalize_query(text)["normalized_query"]
    r2 = normalize_query(r1)["normalized_query"]
    return r1 == r2
