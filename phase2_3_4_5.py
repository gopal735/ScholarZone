import json
import os
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

WAVE4_OUT = r"C:\Users\GopaL\AppData\Local\Temp\kilo\sz-wave4\backend\research\wave4\out"

# Read all output files
shard_files = sorted(os.listdir(WAVE4_OUT))
all_records = []

for fname in shard_files:
    fpath = os.path.join(WAVE4_OUT, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    shard_id = data.get('shard_id', fname.replace('.json', ''))
    topic = data.get('topic', 'unknown')
    records = data.get('records', [])
    
    for rec in records:
        all_records.append({
            'shard_id': shard_id,
            'topic': topic,
            **rec
        })

# Build mutation tables
deadline_mutations = []
logo_mutations = []

for rec in all_records:
    if rec['topic'] == 'deadline':
        # Determine mutation classification
        outcome = rec.get('outcome')
        deadline_date = rec.get('deadline_date')
        deadline_precision = rec.get('deadline_precision')
        deadline_display = rec.get('deadline_display')
        deadline_semantics = rec.get('deadline_semantics')
        source_url = rec.get('source', {}).get('url') if isinstance(rec.get('source'), dict) else None
        rejected_sources = rec.get('rejected_sources', [])
        
        # Check for source URL correction
        old_url = None
        new_url = None
        correction_reason = None
        for r in rejected_sources:
            reason = r.get('reason', '').lower()
            if '404' in reason or 'wrong' in reason or 'not the live' in reason or 'superseded' in reason or 'stale' in reason or 'error page' in reason:
                old_url = r.get('url')
                new_url = source_url
                correction_reason = r.get('reason')
                break
        
        if outcome == 'recovered' and deadline_date:
            mutation_type = 'DEADLINE_FILL'
        elif outcome == 'recovered' and not deadline_date and deadline_semantics in ['ANNUAL', 'ROLLING', 'MONTH']:
            mutation_type = 'DEADLINE_SEMANTIC_UPDATE'
        elif outcome == 'expired_mismatch':
            mutation_type = 'STALE_VALUE_PRESERVED'
        elif outcome == 'unknown':
            mutation_type = 'NO_CHANGE'  # No write
        elif outcome == 'conflicting':
            mutation_type = 'DEADLINE_SEMANTIC_UPDATE'  # precision=varies
        elif outcome == 'rejected':
            mutation_type = 'NO_CHANGE'
        else:
            mutation_type = 'NO_CHANGE'
        
        deadline_mutations.append({
            'scholarship_id': rec['scholarship_id'],
            'title': rec['title'],
            'shard_id': rec['shard_id'],
            'current_outcome': outcome,
            'proposed_deadline_date': deadline_date,
            'proposed_deadline_precision': deadline_precision,
            'proposed_deadline_display': deadline_display,
            'proposed_deadline_semantics': deadline_semantics,
            'source_url': source_url,
            'mutation_type': mutation_type,
            'confidence': rec.get('confidence'),
            'notes': rec.get('source', {}).get('notes', ''),
            'old_url': old_url,
            'new_url': new_url,
            'correction_reason': correction_reason,
        })
    
    elif rec['topic'] == 'logo':
        outcome = rec.get('outcome')
        image_url = rec.get('image_url')
        image_source_url = rec.get('image_source_url')
        image_source_type = rec.get('image_source_type')
        confidence = rec.get('confidence')
        validation = rec.get('validation', {})
        
        if outcome == 'recovered' and image_url:
            mutation_type = 'LOGO_FILL'
        elif outcome == 'not_found':
            mutation_type = 'LOGO_NOT_FOUND_CONFIRMED'
        elif outcome == 'rejected':
            mutation_type = 'NO_CHANGE'
        else:
            mutation_type = 'NO_CHANGE'
        
        logo_mutations.append({
            'scholarship_id': rec['scholarship_id'],
            'title': rec['title'],
            'shard_id': rec['shard_id'],
            'current_outcome': outcome,
            'proposed_image_url': image_url,
            'proposed_image_source_url': image_source_url,
            'proposed_image_source_type': image_source_type,
            'mutation_type': mutation_type,
            'confidence': confidence,
            'validation': validation,
            'source_url': rec.get('source', {}).get('url') if isinstance(rec.get('source'), dict) else None,
            'notes': rec.get('source', {}).get('notes', '') if isinstance(rec.get('source'), dict) else '',
        })

# Save mutation tables
with open(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\wave4_deadline_mutations.json", 'w', encoding='utf-8') as f:
    json.dump(deadline_mutations, f, indent=2, ensure_ascii=False)

with open(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\wave4_logo_mutations.json", 'w', encoding='utf-8') as f:
    json.dump(logo_mutations, f, indent=2, ensure_ascii=False)

# Summary counts
dl_fills = sum(1 for m in deadline_mutations if m['mutation_type'] == 'DEADLINE_FILL')
dl_semantic = sum(1 for m in deadline_mutations if m['mutation_type'] == 'DEADLINE_SEMANTIC_UPDATE')
dl_stale = sum(1 for m in deadline_mutations if m['mutation_type'] == 'STALE_VALUE_PRESERVED')
dl_no_change = sum(1 for m in deadline_mutations if m['mutation_type'] == 'NO_CHANGE')
dl_corrections = sum(1 for m in deadline_mutations if m['old_url'])

lg_fills = sum(1 for m in logo_mutations if m['mutation_type'] == 'LOGO_FILL')
lg_not_found = sum(1 for m in logo_mutations if m['mutation_type'] == 'LOGO_NOT_FOUND_CONFIRMED')
lg_no_change = sum(1 for m in logo_mutations if m['mutation_type'] == 'NO_CHANGE')

print("=== PHASE 2: DEADLINE CONSOLIDATION - PROPOSED MUTATION TABLE ===")
print(f"Records considered: {len(deadline_mutations)}")
print(f"DEADLINE_FILL (exact date written): {dl_fills}")
print(f"DEADLINE_SEMANTIC_UPDATE (recurring/rolling/month/varies): {dl_semantic}")
print(f"STALE_VALUE_PRESERVED (expired_mismatch): {dl_stale}")
print(f"NO_CHANGE (unknown/rejected): {dl_no_change}")
print(f"SOURCE_URL_REANCHOR corrections: {dl_corrections}")

print("\n=== PHASE 3: LOGO CONSOLIDATION - PROPOSED MUTATION TABLE ===")
print(f"Records considered: {len(logo_mutations)}")
print(f"LOGO_FILL: {lg_fills}")
print(f"LOGO_NOT_FOUND_CONFIRMED: {lg_not_found}")
print(f"NO_CHANGE: {lg_no_change}")

print("\n=== PHASE 4: SOURCE URL REANCHORING ===")
corrections_by_record = defaultdict(list)
for m in deadline_mutations:
    if m['old_url']:
        corrections_by_record[m['scholarship_id']].append(m)

for sid, muts in sorted(corrections_by_record.items()):
    for m in muts:
        print(f"  Record {sid} ({m['shard_id']}):")
        print(f"    OLD: {m['old_url']}")
        print(f"    NEW: {m['new_url']}")
        print(f"    WHY: {m['correction_reason']}")

print(f"\nTotal records needing URL reanchor: {len(corrections_by_record)}")

# Phase 5: Systemic findings
print("\n=== PHASE 5: SYSTEMIC FINDINGS ===")
print("1. Stale verification_status=open/active while official deadline has passed:")
print(f"   {dl_stale} records with expired_mismatch - deadlines in past but record status open/upcoming")
print("2. Cached deadline strings contradicted by live evidence:")
print(f"   {dl_corrections} records where official_source_url was 404/wrong/superseded")
print("3. Dead official URLs:")
print(f"   {dl_corrections} source URL corrections needed")
print("4. WAF/browser-only hosts: Multiple (royalsociety.org.nz returned 403, in.emb-japan.go.jp 403)")
print("5. Binary-PDF extraction limitations: Multiple (DAAD, ICCR, NAWA call PDFs)")
print("6. Provider/source semantic ambiguity: NAWA programmes on study.gov.pl vs nawa.gov.pl, Chinese Government Scholarships Type A vs Type B")

PYEOF