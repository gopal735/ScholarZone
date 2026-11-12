## Summary

Complete data-driven filter remediation for the Scholarship Directory. All filters now accurately match the actual public scholarship catalogue.

## Changes

### Country Filter
- Options derived from actual catalogue data using canonical taxonomy (backend/app/services/taxonomy.py)
- Handles aliases: USA/United States, UK/United Kingdom, Republic of Korea/South Korea, Vietnam/Viet Nam, Türkiye/Turkey
- Excludes non-countries: Europe, International, Multiple, EU (multiple), Global
- Sorted alphabetically by canonical name

### Degree Filter
- Supports actual levels: Bachelor/Undergraduate, Master, PhD/Doctoral, Postgraduate, Postdoctoral, Associate
- Joint degrees handled correctly: "Master's, PhD" matches both Master and PhD filters
- Dynamic facet counts from complete catalogue

### Funding Filter
- Semantic matching with exclude lists: Fully Funded excludes "partially", "partial to full", "various"
- Respects tri-state fully_funded boolean: true=confirmed, false=explicitly not, null=unknown
- Supports: Fully Funded, Partially Funded, Tuition Fee Waiver, Stipend, Research Funding, Need-Based

### Deadline Filter
- Only shows months with actual records (dynamic from data)
- Unknown/invalid dates don't match any month filter
- Null dates sort last in both ascending and descending order

### Status/Lifecycle Filter
- Removed Closed option from status dropdown (public catalogue excludes closed/archived/quarantined)
- Removed Closed tab from lifecycle filter tabs

### Dynamic Facets Architecture
- New filterFacets.js derives all filter options from complete public catalogue
- Backend returns facets in ScholarshipListResponse
- Static service computes facets from full snapshot
- Frontend uses API facets when available, falls back to local derivation

### Sorting Fix
- Fixed compareNullableTimestamps to put unknown dates last in both directions

### Tests
- Updated ScholarshipList tests for new dynamic behavior
- All 507 frontend tests pass
- All 198 backend tests pass (1 skipped)

### Lint/Build
- Frontend lint passes (only pre-existing warnings)
- Production build succeeds