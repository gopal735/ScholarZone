"""Quick manual check of the section extractor."""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.services.section_extractor import extract_all

HTML = """
<html><body>
<nav>Home About Contact</nav>
<h2>Scholarship Benefits</h2>
<p>Living stipend: 800 EUR per month</p>
<p>Full tuition fees are covered for the duration of the award.</p>
<h2>Eligibility Criteria</h2>
<ul><li>Applicants must hold a Bachelor degree</li>
    <li>Nationality: citizens of eligible countries</li></ul>
<h2>How to apply</h2>
<p>Deadline: 15 March 2027</p>
<p>Apply through the official online portal.</p>
<h2>English Requirements</h2>
<p>IELTS 6.5 minimum is required.</p>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"EducationalOrganization",
 "description":"A graduate scholarship for students from developing countries."}
</script>
</body></html>
"""

for f in extract_all(HTML):
    print(f"{f.field_name:24s} [{f.structure:12s}] {f.value[:70]}")
    print(f"{'':24s}  evidence: {f.evidence[:80]}")
