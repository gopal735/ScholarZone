"""Country Intelligence — sourced country intelligence merged with measured catalogue facts.

This package answers a question the catalogue alone cannot: not "what
scholarships exist in Germany" but "what does it cost, what does it pay, and can
I stay". Those three questions need three different kinds of answer, and the
package keeps them in three separate planes that are never merged into one number:

* ``RESEARCHED`` - figures a person read on an official page, stored as curated
  JSON under ``backend/config/country_intelligence/`` with a source, a retrieval
  date and a typed ``value_status``. Reviewed in code review, like the other
  curated config in this repository.
* ``MEASURED`` - counts of the live catalogue, computed per request from stored
  rows with the directory's own visibility predicate. Never stored, never cached,
  never carried over from a previous run.
* ``DERIVED`` - arithmetic over the two planes above, with a named, versioned
  formula that refuses to produce a figure when an input is missing.

A figure is never promoted from one plane to another. A researched salary does not
become a measured one because a scholarship exists that mentions it, and a
measured scholarship count is not evidence that a cost figure is correct.
"""

COUNTRY_INTELLIGENCE_VERSION = "1.0.0"

__all__ = ["COUNTRY_INTELLIGENCE_VERSION"]