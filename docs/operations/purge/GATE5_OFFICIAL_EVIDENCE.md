# GATE 5: Official Source Classification

## Overview
Each of the 34 target records must be classified with official source evidence.

## Classification Categories

### Category A: Previously "Closed" (19 records)
*Already excluded from public snapshot via status="closed" filter*

| ID | Scholarship | Country | Deadline | Cycle | Official Source |
|----|-------------|---------|----------|-------|-----------------|
| 2 | ICCR Scholarship | India | 2026-04-22 | Annual (ICCR) | https://www.iccr.gov.in/ |
| 62 | Knight-Hennessy Scholars | USA | 2026-10-06 | Annual (Stanford) | https://knight-hennessy.stanford.edu/ |
| 103 | Commonwealth Scholarship | UK | 2026-10-20 | Annual (CSC) | https://cscuk.fcdo.gov.uk/ |
| 492 | SA-TIED Research Proposals | South Africa | 2026-10-15 | Recurring (UNU-WIDER) | https://www.wider.unu.edu/ |
| 496 | Chevening SIDS Scholarship | UK | 2026-10-06 | Annual (Chevening) | https://www.chevening.org/ |
| 497 | Chevening Defence Fellowship | UK | 2026-10-12 | Annual (Chevening) | https://www.chevening.org/ |
| 510 | Nordic Scholarship Programme | Sweden | 2026-10-11 | Annual (NAI) | https://www.nai.uu.se/ |
| 521 | Mandela Washington Fellowship | USA | 2026-10-13 | Annual (State Dept) | https://mandela-washington-fellowship.state.gov/ |
| 556 | OEA-UNIR Scholarships | Spain | 2026-10-19 | Annual (OAS) | https://www.oas.org/ |
| 563 | UNESCO/Japan Young Researchers | Japan | 2026-10-15 | Annual (UNESCO) | https://www.unesco.org/ |
| 587 | Killam Predoctoral Scholarship | Canada | 2026-10-16 | Annual (Killam Trusts) | https://www.killamtrusts.ca/ |
| 588 | Dalhousie Research Excellence | Canada | 2026-10-16 | Annual (Dalhousie) | https://www.dal.ca/ |
| 662 | Swinburne Research Stipend | Australia | 2026-10-09 | Annual (Swinburne) | https://www.swinburne.edu.au/ |
| 666 | Western Sydney Research | Australia | 2026-10-18 | Annual (WSU) | https://www.westernsydney.edu.au/ |
| 788 | Eiffel Excellence Scholarship | France | 2026-01-08 | Annual (Campus France) | https://www.campusfrance.org/ |
| 1216 | DAAD Study Scholarships STEM | Germany | 2026-08-31 | Annual (DAAD) | https://www.daad.de/ |
| 1218 | Chevening Scholarship | UK | 2026-10-06 | Annual (Chevening) | https://www.chevening.org/ |
| 1278 | Czech Government Scholarships | Czech Republic | 2026-09-30 | Annual (MSMT) | https://www.msmt.cz/ |
| 496 | Chevening SIDS Scholarship | UK | 2026-10-06 | Annual (Chevening) | https://www.chevening.org/ |
| 497 | Chevening Defence Fellowship | UK | 2026-10-12 | Annual (Chevening) | https://www.chevening.org/ |

### Category B: Past-Deadline "Closing-Soon" (15 records)

| ID | Scholarship | Country | Deadline | Cycle | Official Source |
|----|-------------|---------|----------|-------|-----------------|
| 54 | U Miami Stamps Scholarship | USA | 2026-11-01 | Annual (U Miami) | https://www.miami.edu/ |
| 59 | U Minnesota Global Excellence | USA | 2026-11-01 | Annual (UMN) | https://twin-cities.umn.edu/ |
| 382 | VU Fellowship (VUFP) | Netherlands | 2026-11-01 | Annual (VU Amsterdam) | https://www.vu.nl/ |
| 583 | EMBO Science Journalism Fellowships | Multiple | 2026-10-30 | Annual (EMBO) | https://www.embo.org/ |
| 592 | Building Brighter Futures (Indspire) | Canada | 2026-11-01 | Annual (Indspire) | https://indspire.ca/ |
| 594 | OAS-AUWCL Scholarship | USA | 2026-11-01 | Annual (OAS) | https://www.oas.org/ |
| 624 | Cusanuswerk Promotionsstipendium | Germany | 2026-11-01 | Annual (Cusanuswerk) | https://www.cusanuswerk.de/ |
| 626 | ERS VISIT Grant | Switzerland | 2026-10-31 | Annual (ERS) | https://www.ersnet.org/ |
| 642 | Chile Gov Cooperation | Chile | 2026-10-30 | Annual (Gov Chile) | https://www.gob.cl/ |
| 652 | Chula LINK Scholarship 2026 | Thailand | 2026-10-31 | Annual (Chulalongkorn) | https://www.chula.ac.th/ |
| 655 | SEARCA Master's/PhD | Philippines | 2026-10-31 | Annual (SEARCA) | https://www.searca.org/ |
| 657 | AICTE Pragati Scholarship | India | 2026-10-31 | Annual (AICTE) | https://www.aicte-india.org/ |
| 677 | Mastercard Foundation at UCT | South Africa | 2026-10-31 | Annual (Mastercard/UCT) | https://www.mastercardfdn.org/ |
| 711 | Sonja Davies Peace Award | New Zealand | 2026-10-30 | Annual (New Horizons) | https://www.newhorizons.org.nz/ |
| 724 | Mastercard Foundation at AUC | Egypt | 2026-11-02 | Annual (Mastercard/AUC) | https://www.mastercardfdn.org/ |

### ID 651 Reconciliation
| Property | Value |
|----------|-------|
| ID | 651 |
| Title | Fu Jen Catholic University Scholarship for New International Students |
| Country | Taiwan |
| Deadline | 2026-10-14 |
| Precision | exact |
| Status (Pre-Purge) | closing-soon |
| Cycle Type | Annual (FJCU) |
| In Snapshot Pre-Purge | YES (status=closing-soon) |
| In Backup | YES (confirmed) |
| Deleted | YES (correctly purged as expired cycle) |
| Official Source | https://www.fju.edu.tw/ |
| Cycle Evidence | Annual FJCU scholarship cycle, 2026 closed |

## Verification Rules
- Each record must have verified official source URL
- Deadline must be confirmed past as of 2026-11-03
- Cycle identity must be specific (not evergreen programme)
- Official source must be programme-specific, not just homepage

## Evidence Format
For each ID, record:
- ID
- Exact scholarship title
- Country
- Deadline (ISO format)
- Deadline precision (exact/month/year/unknown)
- Cycle identity
- Official source URL
- Evidence of deadline
- Evidence cycle has ended
- Checked timestamp
- Classification decision