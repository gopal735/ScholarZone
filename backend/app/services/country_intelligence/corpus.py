"""Loading and validating the researched country corpus.

The corpus is curated JSON, one file per country, under
``backend/config/country_intelligence/``. It is deliberately *files and not
tables*, for three reasons:

1. This repository has no Alembic and production startup deliberately refuses to
   migrate (``main.py`` logs "verifying database connectivity, not migrating
   schema"). A table added here would reach Neon only by a separate hand-run
   script, and the next person to look would not know it existed.
2. Every figure carries a source and a retrieval date. A diff of a JSON file
   shows a reviewer exactly which number changed, from what, and when. A diff of
   a table shows a hex dump.
3. The other curated research in this project already lives in ``backend/config``
   and is reviewed the same way. This is the same convention, not a new one.

## One bad file must not take the corpus down

A malformed country file excludes **that country** and publishes the reason. It
never raises, never returns a half-validated record, and never silently drops the
country from a count. A corpus of thirty where one file has a reversed range
should answer for twenty-nine countries and say something was wrong with the
thirtieth; failing the whole request would make a typo in one file look like a
broken feature.

## Two shapes of node, because researchers write two shapes

A mapping carrying a ``value`` is a **figure** and is validated on its own.

A mapping carrying a ``value_status`` but no ``value`` is a **context node**: a
group that declares currency, unit, ``as_of`` or sources for the figures beneath
it. This is how people naturally write research - one ``"currency": "EUR"`` at
the top of a block rather than repeated on every line - and supporting it removes
a great deal of repetition without weakening anything, because the context is
inherited by the figures below and each of those is still validated individually.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator, Mapping

from .formulas import verify_formula_claim
from .provenance import (
    SOURCE_TYPES,
    VALUE_STATUS,
    VALUE_STATUS_ALIASES,
    Claim,
    ClaimError,
    check_official_source_claim,
    normalise_source_type,
    parse_claim,
)

logger = logging.getLogger(__name__)

#: ``backend/config/country_intelligence``.
#:
#: Four parents, not three: this module lives inside the ``country_intelligence``
#: subpackage, so ``parents[2]`` is ``app`` rather than ``backend``. The path is
#: asserted rather than assumed, because a silent one-level error here would point
#: the loader at a directory that does not exist, produce an empty corpus, and be
#: indistinguishable from "no country has been researched yet".
CORPUS_DIR = Path(__file__).resolve().parents[3] / "config" / "country_intelligence"
assert CORPUS_DIR.parent.name == "config", (
    f"country intelligence corpus path resolved to {CORPUS_DIR}, which is not "
    f"inside a 'config' directory."
)

#: Sections a country file may carry. Declared so a typo in a section name is
#: visible rather than becoming a silently absent block.
SECTION_NAMES: tuple[str, ...] = (
    "education_costs",
    "living_costs",
    "one_time_costs",
    "career",
    "residency",
    "quality_of_life",
    "scholarship_landscape",
)

#: Keys a context node contributes to the figures beneath it.
#:
#: ``value_status`` is here and not in :data:`_CONTEXT_OWN_KEYS` because a block
#: declaring its evidence strength once is exactly how research is written -
#: ``"rent": {"value": 1600, "source_ids": [...]}`` under one
#: ``"value_status": "CROWDSOURCED"`` - and refusing that spelling meant every
#: figure under the block fell back to ``UNKNOWN`` while still carrying a value,
#: which excluded the whole country with a confusing error about a figure nobody
#: had questioned. A child that declares its own status overrides the block, so
#: the inherited value is a default rather than an assertion.
#:
#: The risk this opens - a block stamping an official status over a figure that
#: came from elsewhere - is closed by the source cross-check in
#: :func:`_check_sources_resolve`, which rejects an official-status claim whose
#: sources are secondary or unlabelled. Inheritance makes the block efficient; the
#: cross-check keeps it honest.
_CONTEXT_KEYS = frozenset(
    {
        "currency",
        "per",
        "as_of",
        "sample_size",
        "source_ids",
        "unit",
        "basis",
        "value_status",
    }
)

#: Keys that belong to the context node itself rather than to any child figure.
_CONTEXT_OWN_KEYS = frozenset({"note", "formula", "previous", "inputs", "min", "max"})

#: How deep a section tree may nest before it is treated as malformed. Real
#: sections nest about five levels; this is far above any shape a corpus file
#: needs and far below where the interpreter gives up. Without the bound, a
#: hand-edited file nests far enough to raise ``RecursionError``, which escapes
#: every ordinary handler and takes the request down instead of excluding one
#: country.
_MAX_SECTION_DEPTH = 32

#: Statuses that state a fact *about the absence or multiplicity of a value*, and
#: therefore carry no ``value`` of their own.
#:
#: These are terminal for :func:`_walk_claims`. Without that, a ``CONFLICTING``
#: node - which by contract carries ``value: null`` and a list of alternatives -
#: would fall through to the recursion branch and have each of its alternatives
#: validated as if it were a standalone claim. Each alternative would then inherit
#: the parent's ``CONFLICTING`` status, and validation would reject the country
#: for "a conflicting claim carrying a single value" - the exact contradiction the
#: status exists to express.
_VALUELESS_CLAIM_STATUSES = frozenset({"UNKNOWN", "CONFLICTING", "REFUSED"})

#: Structured sub-objects that belong to a claim rather than being nested claims.
#: Never descended into.
_CLAIM_PAYLOAD_KEYS = frozenset(
    {"conflicting", "refusal", "colliding_values", "net_income_profile"}
)


@dataclass(frozen=True)
class Source:
    """One page a researcher read.

    Carries more than a URL. ``retrieved_at`` and ``as_of`` are separate because
    they answer different questions and conflating them is how a two-year-old page
    ends up described as freshly checked: ``as_of`` is when the fact was true on
    the page, ``retrieved_at`` is when a person read it. ``confidence`` and
    ``notes`` are where methodology and caveats live, so a figure that rests on a
    single direct read can be distinguished from one inferred across five
    documents without a reader guessing from the URL.
    """

    id: str
    publisher: str
    title: str
    url: str
    accessed: str | None = None
    source_type: str | None = None
    retrieved_at: str | None = None
    as_of: str | None = None
    confidence: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "publisher": self.publisher,
            "title": self.title,
            "url": self.url,
        }
        for key, attr in (
            ("source_type", "source_type"),
            ("retrieved_at", "retrieved_at"),
            ("as_of", "as_of"),
            ("accessed", "accessed"),
            ("confidence", "confidence"),
            ("notes", "notes"),
        ):
            value = getattr(self, attr)
            if value:
                payload[key] = value
        return payload


@dataclass(frozen=True)
class Gap:
    """A figure that could not be established, and why."""

    field: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "reason": self.reason}


@dataclass(frozen=True)
class CountryRecord:
    """One validated country from the corpus.

    Excluded entirely if any figure in it failed validation: a country whose file
    contains one unsourceable number is not published partially, because a reader
    has no way to know which part is trustworthy.
    """

    iso2: str
    name: str
    currency: str | None
    researched_at: str | None
    sections: Mapping[str, Any]
    sources: tuple[Source, ...]
    gaps: tuple[Gap, ...]
    european_union: bool = False
    schengen: bool = False
    #: Every validated figure in the file, keyed by its walked path.
    #:
    #: Published separately from :attr:`sections` because the two answer different
    #: questions. ``sections`` is the research **as written** - what a reviewer
    #: reads to check the transcription, block-level declarations included and
    #: unmerged. ``claims`` is the same data **as validated**: block metadata
    #: inherited, aliases resolved, defaults applied.
    #:
    #: Consumers that do arithmetic must use ``claims``. Reading ``sections``
    #: directly and looking for ``value_status`` gets it wrong in exactly the
    #: case the inheritance feature exists for: a figure that inherits its status
    #: from its parent has no ``value_status`` of its own in the raw body, so a
    #: consumer that requires one sees no usable figure and silently drops it -
    #: turning a sourced rent into an absent rent.
    claims: Mapping[str, Claim] = field(default_factory=dict)

    def source(self, source_id: str) -> Source | None:
        for candidate in self.sources:
            if candidate.id == source_id:
                return candidate
        return None

    def section(self, name: str) -> Mapping[str, Any]:
        """A section, or an empty mapping when the country has none.

        Returning empty rather than raising keeps a caller from having to know in
        advance which countries were researched for which sections.
        """
        return self.sections.get(name) or {}

    def claim(self, *path: str) -> Claim | None:
        """A validated figure by its dotted path, or ``None``.

        The supported accessor for anything that reads a researched number.
        """
        return self.claims.get(".".join(path))

    def to_dict(self) -> dict[str, Any]:
        return {
            "iso2": self.iso2,
            "name": self.name,
            "currency": self.currency,
            "researched_at": self.researched_at,
            "european_union": self.european_union,
            "schengen": self.schengen,
            "sources": [source.to_dict() for source in self.sources],
            "gaps": [gap.to_dict() for gap in self.gaps],
        }


@dataclass(frozen=True)
class CorpusProblem:
    """Why a country is not in the published corpus."""

    iso2: str
    filename: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"iso2": self.iso2, "file": self.filename, "reason": self.reason}


@dataclass(frozen=True)
class Corpus:
    """The whole validated corpus, plus what was excluded and why."""

    records: tuple[CountryRecord, ...] = field(default_factory=tuple)
    problems: tuple[CorpusProblem, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __iter__(self) -> Iterator[CountryRecord]:
        return iter(self.records)

    def __len__(self) -> int:
        return len(self.records)

    def get(self, iso2: str) -> CountryRecord | None:
        for record in self.records:
            if record.iso2 == iso2:
                return record
        return None

    @property
    def iso2_codes(self) -> tuple[str, ...]:
        return tuple(record.iso2 for record in self.records)

    def has_section(self, iso2: str, section: str) -> bool:
        record = self.get(iso2)
        return bool(record and record.section(section))


def _walk_claims(
    node: Any, path: str, _depth: int = 0, _context: Mapping[str, Any] | None = None
) -> Iterator[tuple[str, Claim]]:
    """Yield ``(path, Claim)`` for every figure in a section tree."""
    if _depth > _MAX_SECTION_DEPTH:
        raise ClaimError(f"{path}: section nesting exceeds {_MAX_SECTION_DEPTH} levels.")

    if isinstance(node, Mapping):
        has_value = "value" in node
        is_valueless_claim = node.get("value_status") in _VALUELESS_CLAIM_STATUSES

        # A figure is a node carrying a number, or one explicitly declaring that
        # the figure could not be established, could not be computed, or that
        # credible sources disagree. A node with `value: null` under an
        # evidence status and nothing but prose is neither: it is a note about how
        # the country's system works, which is exactly the kind of context a reader
        # needs and which must not be mistaken for a published zero.
        if (has_value and node.get("value") is not None) or is_valueless_claim:
            inherited = {
                key: value
                for key, value in (_context or {}).items()
                if value is not None
            }
            inherited.update({k: v for k, v in node.items() if v is not None})
            yield path, parse_claim(inherited, path=path)
            return

        context = dict(_context or {})
        if "value_status" in node:
            for key in _CONTEXT_KEYS:
                if node.get(key) is not None:
                    context[key] = node[key]
        for key, child in node.items():
            if key in _CONTEXT_KEYS or key in _CONTEXT_OWN_KEYS:
                continue
            if key in _CLAIM_PAYLOAD_KEYS:
                continue
            yield from _walk_claims(child, f"{path}.{key}", _depth + 1, context)
        return

    if isinstance(node, list):
        for index, child in enumerate(node):
            yield from _walk_claims(child, f"{path}[{index}]", _depth + 1, _context)


def _validate_sections(
    raw: Mapping[str, Any], iso2: str
) -> tuple[dict[str, Any], list[str]]:
    """Validate every figure in a file's sections.

    Accepts two layouts, because research output arrives in both and rejecting one
    would discard good work over a wrapper key: sections either nested under a
    ``sections`` object, or sitting at the top level of the file.
    """
    if "sections" in raw:
        sections = raw.get("sections")
        if not isinstance(sections, Mapping):
            raise ClaimError(f"{iso2}: 'sections' must be an object.")
    else:
        sections = {name: raw[name] for name in SECTION_NAMES if name in raw}

    unknown = sorted(set(sections) - set(SECTION_NAMES))
    if unknown:
        raise ClaimError(
            f"{iso2}: unknown section(s) {', '.join(unknown)}. "
            f"Known sections: {', '.join(SECTION_NAMES)}."
        )

    parsed: dict[str, Any] = {}
    warnings: list[str] = []
    for name, body in sections.items():
        claims: dict[str, Claim] = {}
        for path, claim in _walk_claims(body, name):
            claims[path] = claim
            if claim.sample_size is None and claim.value_status == "CROWDSOURCED":
                warnings.append(
                    f"{iso2}: {path} is crowdsourced but records no contributor count."
                )
        parsed[name] = {"body": body, "claims": claims}
    return parsed, warnings


def _validate_sources(raw: Mapping[str, Any], iso2: str) -> tuple[Source, ...]:
    """Read the file's source list, normalising source types to canonical names.

    ``source_type`` is optional here on purpose - a source with no type may still
    back a claim whose status does not assert officiality. It is not optional for
    a source used to support an official claim, and that is enforced where the
    claim is validated rather than here, because the rule needs both pieces: the
    source list and the statuses that cite into it.
    """
    sources = raw.get("sources", [])
    if not isinstance(sources, list):
        raise ClaimError(f"{iso2}: 'sources' must be a list.")
    parsed: list[Source] = []
    seen: set[str] = set()
    for index, entry in enumerate(sources):
        if not isinstance(entry, Mapping):
            raise ClaimError(f"{iso2}: sources[{index}] must be an object.")
        missing = [k for k in ("id", "publisher", "title", "url") if not entry.get(k)]
        if missing:
            raise ClaimError(f"{iso2}: sources[{index}] missing {', '.join(missing)}.")
        if entry["id"] in seen:
            raise ClaimError(f"{iso2}: duplicate source id {entry['id']!r}.")
        seen.add(entry["id"])

        declared_type = entry.get("source_type")
        source_type: str | None = None
        if declared_type is not None:
            source_type = normalise_source_type(declared_type)
            if source_type is None:
                raise ClaimError(
                    f"{iso2}: sources[{index}] ({entry['id']!r}) declares source_type "
                    f"{declared_type!r}, which is not a recognised source type. Known "
                    f"types: {', '.join(SOURCE_TYPES)}. An unrecognised type cannot be "
                    f"treated as official."
                )

        parsed.append(
            Source(
                id=str(entry["id"]),
                publisher=str(entry["publisher"]),
                title=str(entry["title"]),
                url=str(entry["url"]),
                accessed=entry.get("accessed"),
                source_type=source_type,
                retrieved_at=entry.get("retrieved_at") or entry.get("accessed"),
                as_of=entry.get("as_of"),
                confidence=entry.get("confidence"),
                notes=entry.get("notes"),
            )
        )
    return tuple(parsed)


def _validate_gaps(raw: Mapping[str, Any], iso2: str) -> tuple[Gap, ...]:
    gaps = raw.get("gaps", [])
    if not isinstance(gaps, list):
        raise ClaimError(f"{iso2}: 'gaps' must be a list.")
    parsed: list[Gap] = []
    for index, entry in enumerate(gaps):
        if not isinstance(entry, Mapping) or not entry.get("field") or not entry.get("reason"):
            raise ClaimError(f"{iso2}: gaps[{index}] needs both 'field' and 'reason'.")
        parsed.append(Gap(field=str(entry["field"]), reason=str(entry["reason"])))
    return tuple(parsed)


def _check_sources_resolve(
    claims: Mapping[str, Claim], sources: tuple[Source, ...], iso2: str
) -> None:
    """Every citation must resolve, and an official claim must have an official source.

    Two independent failures, caught together because both are about the same
    join and checking them in one pass means a reviewer sees every citation
    problem in a file at once rather than one per reload:

    1. A claim citing ``de-s7`` when the file defines only ``de-s1`` and ``de-s2``
       is a broken citation: the reader follows it and finds nothing.
    2. A claim asserting an official status while citing only newspapers or
       crowdsourced pools is a mislabelled claim, and is the failure this whole
       module exists to prevent.
    """
    known = {source.id for source in sources}
    by_id = {source.id: source for source in sources}

    dangling = [
        f"{path} cites {source_id}"
        for path, claim in claims.items()
        for source_id in claim.source_ids
        if source_id not in known
    ]
    if dangling:
        preview = "; ".join(sorted(dangling)[:5])
        more = " ..." if len(dangling) > 5 else ""
        raise ClaimError(
            f"{iso2}: {len(dangling)} figure(s) cite a source not defined in the file: "
            f"{preview}{more}"
        )

    secondary: list[str] = []
    for path, claim in sorted(claims.items()):
        if not claim.source_ids:
            continue
        types = {
            source_id: by_id[source_id].source_type for source_id in claim.source_ids
        }
        try:
            check_official_source_claim(claim.value_status, types, path=f"{iso2}: {path}")
        except ClaimError as exc:
            secondary.append(str(exc))
    if secondary:
        raise ClaimError("; ".join(secondary))


def _verify_derived_claims(
    section_bodies: Mapping[str, Any], claims: Mapping[str, Claim], iso2: str
) -> None:
    """Every DERIVED figure must be reproducible from its own declared formula.

    ``parse_claim`` checks that a DERIVED figure *names* a formula; this checks
    that the formula, applied to the inputs the figure declares, actually
    produces the number printed beside it. That second check is the one that
    matters and the one that was missing: two research agents in the same build
    published totals their own arithmetic contradicted by four percent and by
    several thousand units respectively, each with a formula string that read
    correctly. Presence of a formula is not agreement with a formula.
    """
    problems: list[str] = []
    for path, claim in sorted(claims.items()):
        if claim.value_status != "DERIVED":
            continue
        node = _node_at_path(section_bodies, path)
        if node is None:
            problems.append(f"{iso2}: {path} is DERIVED but could not be located for formula verification.")
            continue
        try:
            verify_formula_claim(node, path=f"{iso2}: {path}")
        except ClaimError as exc:
            problems.append(str(exc))
    if problems:
        raise ClaimError("; ".join(problems))


def _node_at_path(sections: Mapping[str, Any], path: str) -> Mapping[str, Any] | None:
    """The raw claim body at a walked path, for checks ``parse_claim`` cannot do.

    ``parse_claim`` returns a typed :class:`Claim` and necessarily drops the keys
    it does not model. Formula verification needs the declaration exactly as
    written, so this re-walks the stored body rather than reconstructing it.
    """
    node: Any = sections
    for part in path.replace("[", ".").replace("]", "").split("."):
        if isinstance(node, Mapping):
            if part not in node:
                return None
            node = node[part]
        elif isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return node if isinstance(node, Mapping) else None


def _parse_file(path: Path) -> tuple[CountryRecord, list[str]]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, Mapping):
        raise ClaimError("File must contain an object.")

    country = raw.get("country")
    if not isinstance(country, Mapping) or not country.get("iso2") or not country.get("name_en"):
        raise ClaimError("'country' must be an object carrying 'iso2' and 'name_en'.")
    iso2 = str(country["iso2"]).upper()

    sources = _validate_sources(raw, iso2)
    parsed_sections, warnings = _validate_sections(raw, iso2)

    flat_claims = {
        path: claim
        for section in parsed_sections.values()
        for path, claim in section["claims"].items()
    }
    _check_sources_resolve(flat_claims, sources, iso2)

    section_bodies = {name: value["body"] for name, value in parsed_sections.items()}
    _verify_derived_claims(section_bodies, flat_claims, iso2)

    research = raw.get("research") or {}
    record = CountryRecord(
        iso2=iso2,
        name=str(country["name_en"]),
        currency=country.get("currency"),
        researched_at=research.get("researched_at") if isinstance(research, Mapping) else None,
        sections=section_bodies,
        claims=flat_claims,
        sources=sources,
        gaps=_validate_gaps(raw, iso2),
        european_union=bool(country.get("european_union", False)),
        schengen=bool(country.get("schengen", False)),
    )

    if not record.gaps:
        warnings.append(
            f"{iso2} declares no gaps. A country with no unresearched figure is "
            f"unusual; check that missing data was recorded rather than overlooked."
        )
    return record, warnings


def load_corpus(directory: Path | None = None) -> Corpus:
    """Load and validate every country file in the corpus.

    A missing directory is an empty corpus, not an exception: the feature must
    degrade to "no country intelligence available" rather than take down the
    scholarship catalogue that has nothing to do with it.
    """
    target = directory or CORPUS_DIR
    if not target.exists():
        logger.warning("country intelligence corpus not found at %s", target)
        return Corpus()

    records: list[CountryRecord] = []
    problems: list[CorpusProblem] = []
    warnings: list[str] = []

    for path in sorted(target.glob("*.json")):
        iso2 = path.stem.upper()
        try:
            record, file_warnings = _parse_file(path)
            records.append(record)
            warnings.extend(file_warnings)
        except (
            ClaimError,
            json.JSONDecodeError,
            OSError,
            UnicodeDecodeError,
            RecursionError,
        ) as exc:
            problems.append(CorpusProblem(iso2=iso2, filename=path.name, reason=str(exc)))
            logger.warning("excluding country corpus file %s: %s", path.name, exc)

    codes = [record.iso2 for record in records]
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        problems.append(
            CorpusProblem(
                iso2=",".join(duplicates),
                filename="(multiple)",
                reason="The same ISO code is defined by more than one file.",
            )
        )

    return Corpus(
        records=tuple(records), problems=tuple(problems), warnings=tuple(warnings)
    )


@lru_cache(maxsize=1)
def _cached_corpus() -> Corpus:
    return load_corpus()


def get_corpus() -> Corpus:
    """The process-wide corpus.

    Cached for the life of the process, like ``get_settings``. Editing the corpus
    therefore requires a restart, which is the intended workflow: the corpus is
    reviewed source, and a live reload would let a half-written file be served.
    """
    return _cached_corpus()


def reload_corpus() -> Corpus:
    """Drop the cache and reload. For tests and local authoring."""
    _cached_corpus.cache_clear()
    return get_corpus()


__all__ = [
    "CORPUS_DIR",
    "SECTION_NAMES",
    "VALUE_STATUS",
    "VALUE_STATUS_ALIASES",
    "Corpus",
    "CorpusProblem",
    "CountryRecord",
    "Gap",
    "Source",
    "get_corpus",
    "load_corpus",
    "reload_corpus",
]

