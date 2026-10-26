def extract_faculty_candidates(html: str, base_url: str, seed_host: str) -> list[FacultyCandidate]:
    """Extract faculty candidates from a faculty listing page.

    This function applies the two-gate personhood pipeline:
    1. _looks_like_a_person_name - filters anchor text for person-like names
    2. _verify_profile_url_evidence - verifies the profile page contains the person

    Returns a list of FacultyCandidate objects that passed both gates.
    """
    soup = BeautifulSoup(html[:MAX_HTML_BYTES], "html.parser")
    candidates: list[FacultyCandidate] = []
    seen_urls: set[str] = set()

    # Find all anchor tags that look like faculty listings
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        if not href:
            continue

        absolute = urljoin(base_url, href)
        if not _same_site(absolute, base_url):
            continue

        anchor_text = _clean_text(anchor.get_text())
        if not anchor_text:
            continue

        # Gate 1: Person name check on anchor text
        if not _looks_like_a_person_name(anchor_text):
            continue

        profile_url = absolute

        # Gate 2: Verify the profile URL contains evidence for this person
        if not _verify_profile_url_evidence(profile_url, anchor_text, urlparse(base_url).netloc):
            continue

        # Avoid duplicates
        if profile_url in seen_urls:
            continue
        seen_urls.add(profile_url)

        # Create candidate
        candidate = FacultyCandidate(
            name=anchor_text,
            profile_url=profile_url,
        )

        # Try to extract additional info from the anchor's context
        parent = anchor.find_parent()
        if parent:
            context_text = _clean_text(parent.get_text())
            if context_text:
                # Try to extract title from context
                title_match = _TITLE_PATTERN.search(context_text)
                if title_match:
                    candidate.title = title_match.group(1)

        candidates.append(candidate)

        if len(candidates) >= MAX_CANDIDATES_PER_SCHOLARSHIP:
            break

    return candidates


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    collapsed = _WHITESPACE.sub(" ", value).strip()
    return collapsed or None


def _extract_email(html: str, host: str) -> str | None:
    """Return an address published on the page for this host, if any.

    Only an address on the institution's own domain is accepted, and one
    containing a ``+`` tag or an obfuscation is skipped rather than cleaned up:
    rewriting an address is how a guess becomes an official-looking one.
    """
    for match in _EMAIL_PATTERN.finditer(html or ""):
        email = match.group(0)
        if "@" not in email:
            continue
        email_host = email.split("@")[1].lower()
        if email_host != host.lower() and not email_host.endswith("." + host.lower()):
            continue
        if "+" in email or "%" in email:
            continue
        return email
    return None


def _extract_research_areas(html: str) -> list[str]:
    """Extract research areas from a faculty profile page.

    Looks for sections labelled with research-related labels and extracts
    the following text up to the next heading or section.
    """
    soup = BeautifulSoup(html[:MAX_HTML_BYTES], "html.parser")
    areas: list[str] = []

    for label_match in _RESEARCH_LABEL.finditer(html or ""):
        start = label_match.end()
        # Extract text up to next heading or section break
        end = start + 500
        snippet = html[start:end]
        # Clean up and split on common delimiters
        cleaned = _clean_text(snippet)
        if cleaned:
            # Split on common delimiters
            parts = re.split(r"[;,\n]", cleaned)
            for part in parts:
                part = part.strip()
                if len(part) > 10 and len(part) < 200:
                    areas.append(part)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for area in areas:
        if area not in seen:
            seen.add(area)
            unique.append(area)
    return unique[:10]  # Cap at 10 areas


def _same_site(candidate_url: str, seed_host: str) -> bool:
    host = (urlparse(candidate_url).netloc or "").lower()
    seed = (seed_host or "").lower()
    if not host or not seed:
        return False
    return host == seed or host.endswith("." + seed)