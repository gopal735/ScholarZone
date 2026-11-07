import sqlite3
import json
import sys

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db')
cursor = conn.cursor()

# COUNTRY_REGION from taxonomy.py
COUNTRY_REGION = {
    "Austria": "Europe", "Belgium": "Europe", "Bulgaria": "Europe", "Croatia": "Europe",
    "Cyprus": "Europe", "Czech Republic": "Europe", "Denmark": "Europe",
    "Estonia": "Europe", "Finland": "Europe", "France": "Europe", "Germany": "Europe",
    "Greece": "Europe", "Hungary": "Europe", "Iceland": "Europe", "Ireland": "Europe",
    "Italy": "Europe", "Latvia": "Europe", "Liechtenstein": "Europe",
    "Lithuania": "Europe", "Luxembourg": "Europe", "Malta": "Europe",
    "Netherlands": "Europe", "Norway": "Europe", "Poland": "Europe",
    "Portugal": "Europe", "Romania": "Europe", "Slovakia": "Europe",
    "Slovenia": "Europe", "Spain": "Europe", "Sweden": "Europe",
    "Switzerland": "Europe", "United Kingdom": "Europe", "Ukraine": "Europe",
    "Moldova": "Europe", "Belarus": "Europe", "Serbia": "Europe",
    "North Macedonia": "Europe", "Albania": "Europe", "Montenegro": "Europe",
    "Bosnia and Herzegovina": "Europe", "Kosovo": "Europe",
    "Canada": "North America", "United States": "North America",
    "Mexico": "North America",
    "Argentina": "Latin America", "Brazil": "Latin America", "Chile": "Latin America",
    "Colombia": "Latin America", "Costa Rica": "Latin America", "Cuba": "Latin America",
    "Ecuador": "Latin America", "El Salvador": "Latin America",
    "Guatemala": "Latin America", "Honduras": "Latin America",
    "Jamaica": "Latin America", "Nicaragua": "Latin America",
    "Panama": "Latin America", "Paraguay": "Latin America", "Peru": "Latin America",
    "Uruguay": "Latin America", "Venezuela": "Latin America",
    "Bolivia": "Latin America", "Guyana": "Latin America",
    "Suriname": "Latin America", "Barbados": "Latin America",
    "Trinidad and Tobago": "Latin America", "Dominican Republic": "Latin America",
    "Haiti": "Latin America", "Belize": "Latin America",
    "Bahamas": "Latin America", "Puerto Rico": "Latin America",
    "Bangladesh": "Asia", "China": "Asia", "Hong Kong": "Asia", "Macao": "Asia",
    "India": "Asia", "Indonesia": "Asia", "Japan": "Asia", "Malaysia": "Asia",
    "Maldives": "Asia", "Mongolia": "Asia", "Myanmar": "Asia", "Nepal": "Asia",
    "Pakistan": "Asia", "Philippines": "Asia", "Singapore": "Asia",
    "South Korea": "Asia", "Sri Lanka": "Asia", "Taiwan": "Asia",
    "Thailand": "Asia", "Vietnam": "Asia", "Cambodia": "Asia", "Laos": "Asia",
    "Brunei": "Asia", "Timor-Leste": "Asia", "Kazakhstan": "Asia",
    "Uzbekistan": "Asia", "Kyrgyzstan": "Asia", "Tajikistan": "Asia",
    "Turkmenistan": "Asia", "Afghanistan": "Asia",
    "Australia": "Oceania", "New Zealand": "Oceania", "Fiji": "Oceania",
    "Samoa": "Oceania", "Tonga": "Oceania", "Papua New Guinea": "Oceania",
    "Solomon Islands": "Oceania", "Vanuatu": "Oceania",
    "Algeria": "Africa", "Botswana": "Africa", "Burundi": "Africa",
    "Cameroon": "Africa", "Congo": "Africa", "Democratic Republic of the Congo": "Africa",
    "Djibouti": "Africa", "Ethiopia": "Africa", "Ghana": "Africa",
    "Kenya": "Africa", "Lesotho": "Africa", "Liberia": "Africa",
    "Madagascar": "Africa", "Malawi": "Africa", "Mali": "Africa",
    "Mauritius": "Africa", "Mozambique": "Africa", "Namibia": "Africa",
    "Niger": "Africa", "Nigeria": "Africa", "Rwanda": "Africa",
    "Senegal": "Africa", "Seychelles": "Africa", "Sierra Leone": "Africa",
    "Somalia": "Africa", "South Africa": "Africa", "Tanzania": "Africa",
    "Togo": "Africa", "Tunisia": "Africa", "Uganda": "Africa",
    "Zambia": "Africa", "Zimbabwe": "Africa", "Eswatini": "Africa",
    "Gambia": "Africa", "Guinea": "Africa", "Ivory Coast": "Africa",
    "Burkina Faso": "Africa", "Benin": "Africa", "Chad": "Africa",
    "Equatorial Guinea": "Africa", "Gabon": "Africa", "Mauritania": "Africa",
    "Niger": "Africa", "Sudan": "Africa", "South Sudan": "Africa",
    "Egypt": "Middle East", "Iran": "Middle East", "Iraq": "Middle East",
    "Israel": "Middle East", "Jordan": "Middle East", "Kuwait": "Middle East",
    "Lebanon": "Middle East", "Morocco": "Middle East", "Oman": "Middle East",
    "Qatar": "Middle East", "Saudi Arabia": "Middle East",
    "Turkey": "Middle East", "United Arab Emirates": "Middle East",
    "Armenia": "Middle East", "Azerbaijan": "Middle East", "Georgia": "Middle East",
    "Yemen": "Middle East", "Syria": "Middle East", "Lebanon": "Middle East",
    "State of Palestine": "Middle East", "Bahrain": "Middle East",
    "Russian Federation": "Europe",
    "Russia": "Europe",
}

# Get all records
cursor.execute("SELECT id, title, country, fully_funded, funding_amount, funding_currency, funding_period, tuition_coverage, living_cost_coverage, travel_coverage, official_source_url, is_verified, verification_status, status, deadline_date, deadline_precision, academic_provenance, eligible_fields, eligible_programmes, departments, funding_details, notes FROM scholarships")
all_records = cursor.fetchall()

# Classify by region
included_regions = {"Europe", "North America", "Asia", "Oceania", "Africa"}
excluded_regions = {"Middle East", "Latin America"}

region_counts = {}
excluded_records = []
included_records = []
unresolved_records = []

for r in all_records:
    rid, title, country, fully_funded, funding_amount, funding_currency, funding_period, tuition_cov, living_cov, travel_cov, official_url, is_verified, ver_status, status, deadline_date, deadline_prec, acad_prov, elig_fields, elig_progs, depts, fund_details, notes = r
    region = COUNTRY_REGION.get(country, "UNKNOWN")
    region_counts[region] = region_counts.get(region, 0) + 1
    
    if region in excluded_regions:
        excluded_records.append((rid, title, country, region))
    elif region in included_regions:
        included_records.append((rid, title, country, region))
    else:
        unresolved_records.append((rid, title, country, region))

print("=== REGION CLASSIFICATION ===")
for region, count in sorted(region_counts.items(), key=lambda x: -x[1]):
    if region in included_regions:
        status = "[INCLUDED]"
    elif region in excluded_regions:
        status = "[EXCLUDED]"
    else:
        status = "[UNKNOWN]"
    print(f"  {region}: {count} {status}")

print(f"\nTotal included: {len(included_records)}")
print(f"Total excluded: {len(excluded_records)}")
print(f"Total unresolved: {len(unresolved_records)}")

print("\n=== EXCLUDED REGION RECORDS (should not be in catalogue) ===")
for r in excluded_records:
    safe_title = r[1].encode('ascii', 'replace').decode('ascii')
    print(f"  ID {r[0]}: {safe_title[:70]}... | {r[2]} -> {r[3]}")

print("\n=== UNRESOLVED COUNTRY RECORDS ===")
for r in unresolved_records:
    safe_title = r[1].encode('ascii', 'replace').decode('ascii')
    print(f"  ID {r[0]}: {safe_title[:70]}... | {r[2]} -> {r[3]}")

# Check funding contract compliance
print("\n=== FUNDING CONTRACT COMPLIANCE ===")
fully_funded_true = 0
fully_funded_false = 0
fully_funded_null = 0
tuition_true_with_funded_null = 0
funded_true_without_tuition = 0
funded_true_without_funding_details = 0

for r in all_records:
    rid, title, country, fully_funded, funding_amount, funding_currency, funding_period, tuition_cov, living_cov, travel_cov, official_url, is_verified, ver_status, status, deadline_date, deadline_prec, acad_prov, elig_fields, elig_progs, depts, fund_details, notes = r
    
    if fully_funded == 1:
        fully_funded_true += 1
        if tuition_cov != 1:
            funded_true_without_tuition += 1
            print(f"  VIOLATION: ID {rid} fully_funded=true but tuition_coverage={tuition_cov}")
        if not fund_details or fund_details == '' or fund_details == 'null':
            funded_true_without_funding_details += 1
    elif fully_funded == 0:
        fully_funded_false += 1
    else:
        fully_funded_null += 1
        if tuition_cov == 1:
            tuition_true_with_funded_null += 1

print(f"  fully_funded=true: {fully_funded_true}")
print(f"  fully_funded=false: {fully_funded_false}")
print(f"  fully_funded=null: {fully_funded_null}")
print(f"  fully_funded=true but tuition_coverage!=1: {funded_true_without_tuition}")
print(f"  fully_funded=true but no funding_details: {funded_true_without_funding_details}")
print(f"  tuition_coverage=1 but fully_funded=null: {tuition_true_with_funded_null}")

# Check data completeness for key fields
print("\n=== DATA COMPLETENESS ===")
fields = {
    'funding_amount': 0, 'funding_currency': 0, 'funding_period': 0,
    'tuition_coverage': 0, 'living_cost_coverage': 0, 'travel_coverage': 0,
    'academic_provenance': 0, 'eligible_fields': 0, 'eligible_programmes': 0,
    'departments': 0, 'funding_details': 0, 'deadline_date': 0, 'deadline_precision': 0,
    'official_source_url': 0, 'notes': 0
}

for r in all_records:
    rid, title, country, fully_funded, funding_amount, funding_currency, funding_period, tuition_cov, living_cov, travel_cov, official_url, is_verified, ver_status, status, deadline_date, deadline_prec, acad_prov, elig_fields, elig_progs, depts, fund_details, notes = r
    
    if funding_amount is not None: fields['funding_amount'] += 1
    if funding_currency: fields['funding_currency'] += 1
    if funding_period: fields['funding_period'] += 1
    if tuition_cov is not None: fields['tuition_coverage'] += 1
    if living_cov is not None: fields['living_cost_coverage'] += 1
    if travel_cov is not None: fields['travel_coverage'] += 1
    if acad_prov and acad_prov != '' and acad_prov != 'null': fields['academic_provenance'] += 1
    if elig_fields and elig_fields != '' and elig_fields != '[]': fields['eligible_fields'] += 1
    if elig_progs and elig_progs != '' and elig_progs != '[]': fields['eligible_programmes'] += 1
    if depts and depts != '' and depts != '[]': fields['departments'] += 1
    if fund_details and fund_details != '' and fund_details != 'null': fields['funding_details'] += 1
    if deadline_date: fields['deadline_date'] += 1
    if deadline_prec: fields['deadline_precision'] += 1
    if official_url: fields['official_source_url'] += 1
    if notes and notes != '': fields['notes'] += 1

total = len(all_records)
for field, count in fields.items():
    print(f"  {field}: {count}/{total} ({count/total*100:.1f}%)")

# Check verification status
print("\n=== VERIFICATION STATUS ===")
cursor.execute("SELECT is_verified, COUNT(*) FROM scholarships GROUP BY is_verified")
for row in cursor.fetchall():
    print(f"  is_verified={row[0]}: {row[1]}")

cursor.execute("SELECT verification_status, COUNT(*) FROM scholarships GROUP BY verification_status")
for row in cursor.fetchall():
    print(f"  verification_status={row[0]}: {row[1]}")

cursor.execute("SELECT last_verified_at, COUNT(*) FROM scholarships GROUP BY last_verified_at ORDER BY COUNT(*) DESC")
for row in cursor.fetchall():
    print(f"  last_verified_at={row[0]}: {row[1]}")

# Check IDs 1293-1352 specifically
print("\n=== RECORDS 1293-1352 DETAIL ===")
cursor.execute("SELECT id, title, country, fully_funded, funding_amount, funding_currency, funding_period, tuition_coverage, living_cost_coverage, travel_coverage, academic_provenance, eligible_fields, eligible_programmes, departments, funding_details, deadline_date, deadline_precision, official_source_url FROM scholarships WHERE id BETWEEN 1293 AND 1352 ORDER BY id")
for r in cursor.fetchall():
    rid, title, country, ff, fa, fc, fp, tc, lc, trc, ap, ef, ep, dept, fd, dd, dp, osu = r
    region = COUNTRY_REGION.get(country, "UNKNOWN")
    if region in excluded_regions:
        status_flag = "[EXCLUDED]"
    elif region in included_regions:
        status_flag = "[INCLUDED]"
    else:
        status_flag = "[UNKNOWN]"
    safe_title = title.encode('ascii', 'replace').decode('ascii')
    print(f"  ID {rid}: {safe_title[:50]}... | {country} ({region}) {status_flag} | ff={ff} | fa={fa} {fc}/{fp} | tc={tc} lc={lc} trc={trc} | ap={'Y' if ap else 'N'} ef={'Y' if ef else 'N'} ep={'Y' if ep else 'N'} dept={'Y' if dept else 'N'} fd={'Y' if fd else 'N'} | dd={dd} dp={dp}")