"""The single authoritative rule for public verification semantics.

``Scholarship.verification_status`` is the source of truth for whether a record
may be presented publicly as verified. The stored ``is_verified`` column is a
legacy boolean kept for internal bookkeeping and for Match evidence scoring; it
is never the semantic authority for a public claim.

Every public surface that needs a boolean must derive it here so there is exactly
one mapping, and so a contradictory legacy boolean can never reach a client.
"""

from __future__ import annotations

#: The only stored verification status that may be presented publicly as verified.
AUTHORITATIVE_VERIFIED_STATUS = "active"

#: The existing uncertainty status used when a record carries no usable status.
#: Reused rather than invented, so the public contract gains no new state.
UNCERTAIN_VERIFICATION_STATUS = "needs_review"


def public_verified_from_status(verification_status: object) -> bool:
    """Return the public ``verified`` boolean for a stored verification status.

    Deterministic and total: only the exact authoritative status is verified.
    ``None``, missing, blank, non-string, and every other status are unresolved
    and therefore never publicly verified.
    """
    if not isinstance(verification_status, str):
        return False
    return verification_status == AUTHORITATIVE_VERIFIED_STATUS


def normalize_public_verification_status(verification_status: object) -> str:
    """Coerce an absent or unusable stored status to a reportable public value.

    A null or missing status must not be published as authoritative, and must not
    raise: a single bad record would otherwise fail serialisation for the whole
    page. Unrecognised non-empty values are passed through unchanged so real data
    problems stay visible instead of being masked.
    """
    if isinstance(verification_status, str) and verification_status.strip():
        return verification_status
    return UNCERTAIN_VERIFICATION_STATUS
