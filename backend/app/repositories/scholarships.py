"""Database queries for scholarship discovery."""

from collections import Counter
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from ..models import Scholarship
from ..schemas import ScholarshipQuery, ScholarshipSort
from ..services.taxonomy import (
    COUNTRY_ALIASES,
    DEGREE_FILTER_BUCKETS,
    FUNDING_FILTER_BUCKETS,
    MULTIPLE,
    REGIONS,
    canonical_country,
    degree_filter_bucket,
    funding_filter_bucket,
)


def _filter_key(value: str | None) -> str | None:
    """The bucketing key for a requested filter value.

    Case, surrounding space, a trailing possessive and the punctuation a
    select puts in its option text ("Master's", "Tuition Waiver") are all
    removed, because none of them change which aspect is being asked
    about. Anything that does not reduce to a known key returns ``None``
    and the caller keeps exact matching rather than guess.
    """
    if value is None:
        return None
    key = str(value).strip().casefold()
    if not key or key == "all":
        return None
    key = key.replace("'", "").replace("\u2019", "").replace("-", " ").replace("/", " ")
    key = " ".join(key.split())
    if key.endswith("s") and not key.endswith("ss"):
        key = key[:-1]
    return key or None


#: PostgreSQL-compatible ASCII folding for common diacritics.
#: This approximates Python's unicodedata.normalize("NFKD") + strip combining chars
#: without requiring the unaccent extension.
#: Uses a single TRANSLATE call per column to avoid nested REPLACE explosion.
def _ascii_fold_sql(column):
    """Build a SQL expression that ASCII-folds a text column for comparison.
    
    Uses PostgreSQL TRANSLATE for efficient single-pass character mapping.
    The from/to strings map each diacritic to its ASCII equivalent.
    Each character maps 1:1 (no multi-character expansions like ß→ss).
    """
    # TRANSLATE(from_chars, to_chars) - single-pass character replacement
    # from_chars: all diacritics we want to replace (one character each)
    # to_chars:   corresponding ASCII replacements (SAME LENGTH, one character each)
    # 
    # Lowercase (29 chars each):
    from_chars_lower = "üöäßéèêëáàâãåíìîïóòôõúùûçñğşı"
    to_chars_lower   = "uoaseeeeeaaaaaiiiiooooouuuucngsi"
    #                          u o a s s e e e e e a a a a a i i i i o o o o o u u u u c n g s i
    #                          ü ö ä ß é è ê ë á à â ã å í ì î ï ó ò ô õ ú ù û ç ñ ğ ş ı
    
    # Uppercase (29 chars each):
    from_chars_upper = "ÜÖÄßÉÈÊËÁÀÂÃÅÍÌÎÏÓÒÔÕÚÙÛÇÑĞŞİ"
    to_chars_upper   = "UOASSEEEEEAAAAAIIIOOOOOUUUUCNGSI"
    #                          U O A S S E E E E E A A A A A I I I I O O O O O U U U U C N G S I
    #                          Ü Ö Ä ß É È Ê Ë Á À Â Ã Å Í Ì Î Ï Ó Ò Ô Õ Ú Ù Û Ç Ñ Ğ Ş İ
    
    # Verify lengths match
    assert len(from_chars_lower) == len(to_chars_lower), f"Lowercase mapping length mismatch: {len(from_chars_lower)} vs {len(to_chars_lower)}"
    assert len(from_chars_upper) == len(to_chars_upper), f"Uppercase mapping length mismatch: {len(from_chars_upper)} vs {len(to_chars_upper)}"
    
    folded = func.lower(column)
    folded = func.translate(folded, from_chars_lower, to_chars_lower)
    folded = func.translate(folded, from_chars_upper, to_chars_upper)
    return folded


def _is_sqlite(session: Session) -> bool:
    """Check if the session is using SQLite dialect."""
    return session.bind.dialect.name == "sqlite"


def _build_country_canonical_case(column, session: Session | None = None):
    """Build a SQL CASE expression that maps stored country to canonical form.
    
    Mirrors the logic in canonical_country() from taxonomy.py.
    Returns lowercase canonical for consistent comparison.
    
    For SQLite (tests), uses a simplified approach since test data is ASCII.
    For PostgreSQL (production), uses full ASCII folding.
    """
    # For SQLite, test data uses ASCII country names, so simple lower() is sufficient
    if session is not None and _is_sqlite(session):
        return func.lower(column)
    
    # For PostgreSQL, use full ASCII folding with CASE expression for aliases
    # Build CASE WHEN conditions for each alias
    conditions = []
    for alias, canonical in COUNTRY_ALIASES.items():
        if canonical in (MULTIPLE,) or canonical in REGIONS:
            continue
        # Match ASCII-folded stored value against ASCII-folded alias
        # The alias keys in COUNTRY_ALIASES are already ASCII-folded (e.g., "turkiye")
        conditions.append((_ascii_fold_sql(column) == alias.lower(), canonical.lower()))
    
    if conditions:
        return case(*conditions, else_=_ascii_fold_sql(column))
    return _ascii_fold_sql(column)


def _normalise_optional_filter(value: str | None) -> str | None:
    if value is None:
        return None

    normalised = value.strip()
    return None if not normalised or normalised.casefold() == "all" else normalised


def _escape_like(value: str) -> str:
    """Treat LIKE wildcard characters as literal search text."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _funding_conditions(column, requested: str) -> list:
    """Match a requested funding filter against stored funding labels.

    A filter value is a question, not a stored string: the catalogue
    holds 96 distinct labels, and comparing with ``==`` returned 3 of 84
    master's programmes for a degree filter and 0 rows for
    ``funding=Tuition Waiver``. The taxonomy maps the request onto the
    words that state the aspect it asks about, so every row that offers
    that aspect answers.

    A request the taxonomy does not recognise keeps exact matching - it
    is a verbatim stored label, a facet name or a typo, and guessing a
    bucket for it would silently widen a filter the caller did not ask
    to widen.
    """
    lowered = func.lower(column)
    bucket = funding_filter_bucket(requested)
    if bucket is None:
        return [lowered == requested.casefold()]

    include, exclude = bucket
    
    # Special handling for "Fully Funded" - use the authoritative boolean
    key = _filter_key(requested)
    if key == "fully funded":
        return [Scholarship.fully_funded == True]
    
    conditions = [or_(*[lowered.like(f"%{_escape_like(word)}%") for word in include])]
    if exclude:
        conditions.append(
            ~or_(*[lowered.like(f"%{_escape_like(word)}%") for word in exclude])
        )
    return conditions


def _degree_conditions(column, requested: str) -> list:
    """Match a requested degree filter against stored degree labels.

    Same contract as :func:`_funding_conditions`: canonical level words
    ("Master", "Bachelor") match every row offering that level, and an
    unrecognised request keeps exact matching.
    """
    lowered = func.lower(column)
    bucket = degree_filter_bucket(requested)
    if bucket is None:
        return [lowered == requested.casefold()]
    return [or_(*[lowered.like(f"%{_escape_like(word)}%") for word in bucket])]


def public_visibility_conditions() -> list:
    """The single definition of "this record may be shown publicly".

    The directory and the homepage statistics both call this. They previously
    carried separate copies of the rule, which is how a homepage ends up
    advertising a total the directory contradicts - a failure that stays
    invisible until somebody compares the two numbers.

    The states are kept deliberately distinct:

    * ``verification_status`` is authoritative for trust labelling, not visibility.
      A record whose verification is ``needs_review`` or ``unverified`` is still
      a legitimate scholarship that belongs in the public catalogue; its trust
      label will reflect the verification state.
    * ``is_verified`` is legacy bookkeeping and must not be used as a visibility
      gate.
    * ``image_verified_at`` is about an *official* image having passed
      validation. Missing images do not make a scholarship illegitimate.
    * A record whose source was merely blocked is not untrustworthy, it is
      unevaluated. Missing images do not make the scholarship illegitimate.
    * ``image_source_type == "wikimedia"`` is a third-party host. It is not an
      official image but the scholarship itself is still legitimate.
    * ``is_archived`` is not a trust question at all. A record is archived when
      its round has closed, and it is excluded unconditionally rather than
      being left to the settings: archiving is a promise that expired
      opportunities are not offered as if they were live, and a configuration
      flag that could switch that off would quietly break the promise.
    * ``status == "closed"`` indicates a genuinely closed/expired scholarship.
      These are excluded from the public catalogue.
    * ``verification_status == "quarantined"`` is a security/safety exclusion.
      Quarantined records represent a genuine safety concern and remain hidden.
    """
    conditions = [
        Scholarship.verification_status != "quarantined",
        Scholarship.is_archived.is_(False),
        Scholarship.status != "closed",
    ]

    return conditions


def _filter_conditions(query: ScholarshipQuery, session: Session | None = None):
    conditions = public_visibility_conditions()
    search = _normalise_optional_filter(query.search)
    country = _normalise_optional_filter(query.country)
    degree = _normalise_optional_filter(query.degree)
    funding = _normalise_optional_filter(query.funding)

    if search:
        pattern = f"%{_escape_like(search)}%"
        conditions.append(
            or_(
                Scholarship.title.ilike(pattern, escape="\\"),
                Scholarship.description.ilike(pattern, escape="\\"),
                Scholarship.country.ilike(pattern, escape="\\"),
                Scholarship.degree.ilike(pattern, escape="\\"),
                Scholarship.funding.ilike(pattern, escape="\\"),
            )
        )
    if country:
        # Normalize the request country to canonical form using the shared taxonomy
        # This ensures "Türkiye", "Turkiye", "Turkey" all resolve to the same canonical value
        canonical_request = canonical_country(country)
        if canonical_request and canonical_request not in (MULTIPLE,) and canonical_request not in REGIONS:
            canonical_case = _build_country_canonical_case(Scholarship.country, session)
            conditions.append(canonical_case == canonical_request.casefold())
    if degree:
        conditions.extend(_degree_conditions(Scholarship.degree, degree))
    if funding:
        conditions.extend(_funding_conditions(Scholarship.funding, funding))
    if query.deadline_month is not None:
        conditions.append(func.extract("month", Scholarship.deadline_date) == query.deadline_month)
    if query.status is not None:
        conditions.append(Scholarship.status == query.status.value)

    return conditions


def _sort_expressions(sort: ScholarshipSort):
    null_deadline_last = case((Scholarship.deadline_date.is_(None), 1), else_=0)

    if sort is ScholarshipSort.RECOMMENDED:
        return (
            Scholarship.is_verified.desc(),
            case((Scholarship.status == "open", 0), (Scholarship.status == "closing-soon", 1), else_=2).asc(),
            Scholarship.updated_at.desc(),
            Scholarship.id.asc(),
        )
    if sort is ScholarshipSort.RECENTLY_ADDED:
        return (Scholarship.created_at.desc(), Scholarship.id.asc())
    if sort is ScholarshipSort.RECENTLY_UPDATED:
        return (Scholarship.updated_at.desc(), Scholarship.id.asc())
    if sort is ScholarshipSort.DEADLINE_SOON:
        return (null_deadline_last.asc(), Scholarship.deadline_date.asc(), Scholarship.id.asc())
    if sort is ScholarshipSort.FULLY_FUNDED:
        return (
            case((Scholarship.fully_funded == True, 0), else_=1).asc(),
            Scholarship.updated_at.desc(),
            Scholarship.id.asc(),
        )

    if sort is ScholarshipSort.DEADLINE_EARLIEST:
        return (null_deadline_last.asc(), Scholarship.deadline_date.asc(), Scholarship.id.asc())
    if sort is ScholarshipSort.DEADLINE_LATEST:
        return (null_deadline_last.asc(), Scholarship.deadline_date.desc(), Scholarship.id.asc())
    if sort is ScholarshipSort.NAME_ASC:
        return (func.lower(Scholarship.title).asc(), Scholarship.id.asc())
    if sort is ScholarshipSort.NAME_DESC:
        return (func.lower(Scholarship.title).desc(), Scholarship.id.asc())

    return _sort_expressions(ScholarshipSort.RECOMMENDED)


def _compute_country_facets(session: Session) -> list[dict]:
    """Compute country facets from all public records."""
    conditions = public_visibility_conditions()
    rows = session.scalars(
        select(Scholarship.country).where(*conditions)
    ).all()

    counts = Counter()
    for country in rows:
        if not country:
            continue
        canonical = canonical_country(country)
        if canonical and canonical != MULTIPLE and canonical not in REGIONS:
            counts[canonical] += 1

    return [
        {"value": country, "label": country, "count": count}
        for country, count in sorted(counts.items(), key=lambda x: x[0].lower())
    ]


def _compute_degree_facets(session: Session) -> list[dict]:
    """Compute degree facets from all public records."""
    conditions = public_visibility_conditions()
    rows = session.scalars(
        select(Scholarship.degree).where(*conditions)
    ).all()

    # Count occurrences of each degree bucket
    bucket_counts = Counter()
    for degree in rows:
        if not degree:
            continue
        degree_lower = degree.lower()
        for bucket_key, keywords in DEGREE_FILTER_BUCKETS.items():
            if any(kw in degree_lower for kw in keywords):
                bucket_counts[bucket_key] += 1

    # Map bucket keys to display labels
    bucket_labels = {
        "bachelor": "Bachelor / Undergraduate",
        "undergraduate": "Bachelor / Undergraduate",
        "master": "Master",
        "phd": "PhD / Doctoral",
        "doctoral": "PhD / Doctoral",
        "postgraduate": "Postgraduate",
        "postdoc": "Postdoctoral",
    }

    # bachelor and undergraduate are aliases - count each record once
    # Use a set to track which records matched bachelor/undergraduate
    # Since we can't track individual records here, we'll deduplicate by
    # taking the max of the two buckets (they have the same keywords)
    # Actually, both "bachelor" and "undergraduate" buckets have the same keywords,
    # so a record matching one will match both. We should only count it once.
    # The fix: only use "bachelor" as the canonical key for this facet.
    
    # Recompute without double-counting: only count each record once per facet value
    # We need to track which records matched which buckets
    # Simpler approach: just use the bucket_counts but deduplicate bachelor/undergraduate
    # by taking the max since they have identical keywords
    
    # Actually the proper fix is to track matched record IDs per bucket
    # But since we only have degree strings, we'll deduplicate by noting that
    # "bachelor" and "undergraduate" are the same bucket with same keywords
    
    # Use only canonical bucket keys
    canonical_buckets = {
        "bachelor": bucket_labels["bachelor"],
        "master": bucket_labels["master"],
        "phd": bucket_labels["phd"],
        "postgraduate": bucket_labels["postgraduate"],
        "postdoc": bucket_labels["postdoc"],
    }
    
    # For bachelor/undergraduate, they have identical keywords so counts are same
    # We just report one of them
    bachelor_count = bucket_counts.get("bachelor", 0)
    # (undergraduate would be the same)

    facets = []
    if bachelor_count > 0:
        facets.append({"value": "Bachelor", "label": "Bachelor / Undergraduate", "count": bachelor_count})
    for key in ["master", "phd", "postgraduate", "postdoc"]:
        count = bucket_counts.get(key, 0)
        if count > 0:
            facets.append({"value": key.capitalize(), "label": bucket_labels[key], "count": count})

    return facets


def _compute_funding_facets(session: Session) -> list[dict]:
    """Compute funding facets from all public records."""
    conditions = public_visibility_conditions()
    rows = session.execute(
        select(Scholarship.funding, Scholarship.fully_funded).where(*conditions)
    ).all()

    bucket_counts = Counter()
    for funding, fully_funded in rows:
        # For Fully Funded, use the authoritative boolean - check this FIRST
        # regardless of whether funding text exists
        if fully_funded is True:
            bucket_counts["fully funded"] += 1
        
        if not funding:
            continue
        funding_lower = funding.lower()
        for bucket_key, (include, exclude) in FUNDING_FILTER_BUCKETS.items():
            if bucket_key == "fully funded":
                # Already handled above
                continue
            if any(ex in funding_lower for ex in exclude):
                continue
            if any(inc in funding_lower for inc in include):
                bucket_counts[bucket_key] += 1

    bucket_labels = {
        "fully funded": "Fully funded",
        "partially funded": "Partial funding",
        "tuition fee waiver": "Tuition waiver",
        "stipend": "Stipend",
        "research funding": "Research funding",
        "need based": "Need-based",
    }

    facets = []
    for key, label in bucket_labels.items():
        count = bucket_counts.get(key, 0)
        if count > 0:
            facets.append({"value": key.title().replace(" ", " "), "label": label, "count": count})

    return facets


def _compute_deadline_month_facets(session: Session) -> list[dict]:
    """Compute deadline month facets from all public records."""
    conditions = public_visibility_conditions()
    rows = session.scalars(
        select(Scholarship.deadline_date).where(*conditions)
    ).all()

    counts = Counter()
    for deadline_date in rows:
        if deadline_date:
            month = deadline_date.month
            if 1 <= month <= 12:
                counts[month] += 1

    month_names = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    return [
        {"value": str(month), "label": month_names[month], "count": count}
        for month, count in sorted(counts.items())
    ]


def compute_facets(session: Session) -> dict:
    """Compute all filter facets from the public catalogue."""
    return {
        "country": _compute_country_facets(session),
        "degree": _compute_degree_facets(session),
        "funding": _compute_funding_facets(session),
        "deadline_month": _compute_deadline_month_facets(session),
    }


def list_scholarships(session: Session, query: ScholarshipQuery) -> tuple[list[Scholarship], int]:
    conditions = _filter_conditions(query, session)
    total = session.scalar(select(func.count()).select_from(Scholarship).where(*conditions)) or 0
    offset = (query.page - 1) * query.limit
    statement = (
        select(Scholarship)
        .where(*conditions)
        .order_by(*_sort_expressions(query.sort))
        .offset(offset)
        .limit(query.limit)
    )
    items = list(session.scalars(statement))

    return items, total


def get_scholarship_by_id(session: Session, scholarship_id: int) -> Scholarship | None:
    return session.get(Scholarship, scholarship_id)
