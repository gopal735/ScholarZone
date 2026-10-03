"""ScholarZone Match: a deterministic scholarship fit, eligibility and readiness
engine.

The engine answers three questions about a published scholarship record, each
with evidence, and never conflates them:

1. **Am I eligible?** A hard gate over explicitly published mandatory conditions.
   It is evaluated before any scoring and no scoring result can change it.
2. **How well does this fit?** A coverage-aware weighted average over seven
   dimensions, where a dimension that could not be evaluated is excluded rather
   than scored as zero.
3. **Can I trust this, and can I act on it?** Two further independent layers:
   confidence describes the record, and application readiness describes how much
   of the preparation the evidence covers.

It is not an admissions predictor, not a probability of winning and not a
language-model opinion. Every number it returns is produced by arithmetic over
stored facts, and every number is reproducible from the versions, the inputs and
the as-of date.

Module map, in dependency order:

``config``        Every weight, matrix, band and version, validated at import.
``constants``     Stable import surface over ``config``.
``types``         The typed request/response contract.
``normalize``     Profile normalisation and the Academic Profile Index.
``taxonomy``      The controlled programme/field taxonomy.
``requirements``  Conservative readers for explicitly published requirements.
``academic``      Academic comparison, refusing cross-scale conversion.
``components``    The seven fit dimensions.
``metrics``       The fit formula, coverage, contributions, sensitivity range.
``eligibility``   The hard gate.
``confidence``    Data trust, kept separate from fit.
``readiness``     Application readiness, a third independent layer.
``profile_strength`` Completeness of the student's own input.
``gaps``          What could not be evaluated, and why it matters.
``actions``       Grounded next steps, derived from the gaps.
``summaries``     The counting system and facets, with reconciliation asserted.
``nlp``           Optional deterministic natural-language profile input.
``explain``       Deterministic reason codes and templates.
``engine``        Pure orchestration and ranking.
``repository``    One bounded query.
``service``       Session and date injection.
"""

from .config import (
    CONFIDENCE_WEIGHTS,
    FIELD_TAXONOMY_VERSION,
    FIT_ENGINE_VERSION,
    FIT_WEIGHTS,
    READINESS_WEIGHTS,
    REQUIREMENT_READER_VERSION,
    SCORING_CONFIG_VERSION,
)

__all__ = [
    "CONFIDENCE_WEIGHTS",
    "FIELD_TAXONOMY_VERSION",
    "FIT_ENGINE_VERSION",
    "FIT_WEIGHTS",
    "READINESS_WEIGHTS",
    "REQUIREMENT_READER_VERSION",
    "SCORING_CONFIG_VERSION",
]