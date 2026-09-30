"""Optimized 10-scholarship dry-run: representative architectural coverage.

Selects 10 scholarships covering:
- Root-domain source (needs resolution): 5
- Exact program page: 3
- Government source: 2
- University source: 2
- Provider source: 2
- Bot-protected site (DAAD): 1
- Multilingual variation: 1

Total: ~10 unique scholarships with maximum coverage.
"""

REPRESENTATIVE_PILOT_IDS = [
    # Root domains needing resolution
    1,   # EMJM - EU Commission root domain
    2,   # ICCR - India government root domain
    3,   # DAAD - Germany root domain (bot-protected)
    4,   # GKS - Korea root domain
    5,   # MEXT - Japan root domain
    11,  # Study in India - government root domain
    28,  # Chevening - UK provider root domain
    
    # Exact program pages
    6,   # Eiffel Excellence - Campus France program page
    12,  # JASSO - Japan government program page
    35,  # SINGA - Singapore university program page
]

REPRESENTATIVE_DISPLAY = {
    1:  "Erasmus Mundus Joint Masters (EMJM)",
    2:  "ICCR Scholarship (Suborno Jayanti Scheme)",
    3:  "DAAD Scholarship",
    4:  "Global Korea Scholarship (GKS)",
    5:  "MEXT (Monbukagakusho) Scholarship",
    11: "Study in India (SII) Scholarship",
    28: "Chevening Scholarship",
    6:  "Eiffel Excellence Scholarship",
    12: "JASSO Monbukagakusho Honors Scholarship",
    35: "SINGA Scholarship (Singapore)",
}

REPRESENTATIVE_COVERAGE = """
Representative Coverage:
- Root domains needing resolution: 1, 2, 3, 4, 5, 11, 28
- Exact program pages: 6, 12, 35
- Government source: 2 (ICCR), 12 (JASSO)
- University source: 35 (A*STAR)
- Provider source: 1 (EU Commission), 28 (Chevening)
- Bot-protected: 3 (DAAD)
- Multilingual: 5 (MEXT - Japanese), 12 (JASSO - Japanese)
"""
