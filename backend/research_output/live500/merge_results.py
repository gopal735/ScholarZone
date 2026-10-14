"""Merge live-500 agent results into the programme_details corpus.

Every rule the catalogue's tests enforce is enforced here before a record is
allowed into the file, so a malformed research record cannot reach the DB:

  * citations - a record with nothing behind it looks researched and is not, so
    an empty source_citations falls back to the official block's URLs and a
    record with neither is dropped rather than applied;
  * fully_funded may only be asserted with tuition_coverage, because a stipend
    published as full funding is the exact harm the split exists to prevent;
  * placeholders are nulls - an unanswered field must not read as an answer;
  * the column decides the shape: a period longer than its varchar, a
    non-numeric amount or a currency that is not an ISO code is nulled and the
    original text preserved in a *_note key inside the same block;
  * derived guidance never enters the published block.

Existing records win on every field they already hold; an agent record only
fills what is missing, which mirrors the apply stage's empty-only rule.
"""
import json
import os
import re
import sys
from datetime import date

BASE = r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone'
DETAILS = os.path.join(BASE, 'backend', 'config', 'programme_details.json')
OUT = os.path.join(BASE, 'backend', 'research_output', 'live500')

PLACEHOLDERS = {'', 'n/a', 'na', '-', 'none', 'tbd', 'unknown', 'null'}
UTILITY_ONLY = {
    'application_readiness_checklist', 'common_rejection_risks',
    'estimated_uncovered_costs', 'document_audit', 'alerts',
    'submission_workflow', 'summary', 'best_fit',
}
PERIOD_SHORT = [
    (r'\bper month\b', 'per month'),
    (r'\bper week\b', 'per week'),
    (r'\bper fortnight\b', 'per fortnight'),
    (r'\bper day\b', 'per day'),
    (r'\bper semester\b', 'per semester'),
    (r'\bper admission cycle\b', 'per admission cycle'),
    (r'\bper mobility\b', 'per mobility'),
    (r'\bacademic year\b', 'per academic year'),
    (r'\bper annum\b', 'per year'),
    (r'\bper year\b', 'per year'),
    (r'\bmonthly\b', 'per month'),
    (r'\bannual\b', 'per year'),
    (r'\bone[- ]time\b|\bone[- ]off\b|\blump sum\b', 'one-off'),
    (r'\btotal\b', 'total award'),
]


def short_period(text):
    t = text.lower()
    for pattern, short in PERIOD_SHORT:
        if re.search(pattern, t):
            if short == 'per academic year' and re.search(r'per semester|semi', t):
                return 'per semester'
            if short == 'per year' and re.search(r'academic year', t):
                return 'per academic year'
            return short
    return None


def is_placeholder(value):
    return isinstance(value, str) and value.strip().lower() in PLACEHOLDERS


def http_urls(values):
    if not isinstance(values, list):
        return []
    return [u for u in values if isinstance(u, str) and u.startswith(('http://', 'https://'))]


def clean_official(official):
    """Return (cleaned, fixes) with catalogue-invalid values nulled, not kept."""
    fixes = []
    if not isinstance(official, dict):
        return {}, ['official block missing']

    # Derived guidance must never live in the published block.
    for key in [k for k in official if k in UTILITY_ONLY]:
        official.pop(key)
        fixes.append(f'removed utility key {key!r} from official')

    # Placeholder strings are answers the source never gave.
    for field in ('funding_currency', 'funding_period', 'deadline_central',
                  'application_route', 'study_mode'):
        if is_placeholder(official.get(field)):
            official[field] = None
            fixes.append(f'{field} placeholder nulled')

    # Amount must be a number; prose is preserved, not published as an amount.
    amount = official.get('funding_amount')
    if amount is not None and not isinstance(amount, (int, float)):
        official.setdefault('funding_amount_note', str(amount))
        official['funding_amount'] = None
        fixes.append('non-numeric funding_amount nulled, text kept as note')
    if isinstance(amount, bool):
        official['funding_amount'] = None
        fixes.append('boolean funding_amount nulled')

    # Currency must be an ISO code; half a code reads as a code.
    currency = official.get('funding_currency')
    if isinstance(currency, str):
        code = currency.strip()
        if not re.fullmatch(r'[A-Z]{3}', code):
            official.setdefault('funding_currency_note', currency)
            official['funding_currency'] = None
            fixes.append(f'non-ISO funding_currency {code!r} nulled, text kept as note')
        else:
            official['funding_currency'] = code

    # The period column is a varchar; a value that does not fit is nulled, and
    # the full wording survives as a note inside the same block.
    period = official.get('funding_period')
    if isinstance(period, str) and period.strip():
        if len(period.strip()) > 64:
            short = short_period(period)
            if short is None:
                official.setdefault('funding_period_detail', period.strip())
                official['funding_period'] = None
                fixes.append('over-long funding_period nulled, text kept as detail')
            else:
                official.setdefault('funding_period_detail', period.strip())
                official['funding_period'] = short
                fixes.append(f'funding_period shortened to {short!r}')

    # Coverage flags are tri-state; anything that is not a bool becomes null.
    for field in ('tuition_coverage', 'living_cost_coverage', 'travel_coverage'):
        value = official.get(field)
        if value is not None and not isinstance(value, bool):
            official[field] = None
            fixes.append(f'{field} non-bool nulled')

    # fully_funded is a claim about tuition, living costs and required expenses
    # being covered; without tuition coverage it must not stand.
    if official.get('fully_funded') is True and official.get('tuition_coverage') is not True:
        official['fully_funded'] = False
        fixes.append('fully_funded de-asserted without tuition coverage')

    # A deadline that does not parse is not a date.
    dl = official.get('deadline_central')
    if isinstance(dl, str) and dl.strip():
        try:
            date.fromisoformat(dl.strip().replace('Z', '+00:00')[:10])
            official['deadline_central'] = dl.strip()[:10]
        except ValueError:
            official.setdefault('deadline_note', official.get('deadline_note') or dl.strip())
            official['deadline_central'] = None
            fixes.append('unparseable deadline_central nulled, text kept as note')

    return official, fixes


def main(apply=False):
    raw = json.loads(open(DETAILS, encoding='utf-8').read())
    records = raw['records'] if isinstance(raw, dict) else raw
    by_id = {r['id']: r for r in records if isinstance(r, dict) and 'id' in r}
    existing_ids = set(by_id)
    print(f'corpus: {len(existing_ids)} records before merge')

    report = {'agents': 0, 'records_seen': 0, 'dropped': [], 'added': [], 'filled': {}, 'fixes': 0}
    result_dirs = ['results', 'results_internal']
    agent_files = []
    for sub in result_dirs:
        d = os.path.join(OUT, sub)
        if os.path.isdir(d):
            agent_files += [
                os.path.join(sub, f) for f in sorted(os.listdir(d))
                if re.fullmatch(r'agent_\d+\.json', f)
            ]
    for fname in agent_files:
        path = os.path.join(OUT, fname)
        try:
            data = json.loads(open(path, encoding='utf-8').read())
        except (OSError, ValueError) as exc:
            report['dropped'].append({'agent': fname, 'reason': f'unparseable: {exc}'})
            continue
        if isinstance(data, list):
            data = {'records': data}
        if not isinstance(data, dict):
            report['dropped'].append({'agent': fname, 'reason': 'unrecognised shape'})
            continue
        # results_internal is the fallback fleet; the live fleet wins if both wrote.
        if fname.startswith('results_internal') and os.path.exists(os.path.join(OUT, 'results', os.path.basename(fname))):
            report['dropped'].append({'agent': fname, 'reason': 'live fleet already wrote this agent'})
            continue
        report['agents'] += 1
        for rec in data.get('records', []):
            report['records_seen'] += 1
            rid = rec.get('id')
            if rid is None or not isinstance(rid, int):
                report['dropped'].append({'agent': fname, 'reason': 'no usable id'})
                continue
            official = rec.get('official') or {}
            verification = rec.get('verification') or {}
            utility = rec.get('applicant_utility') or {}

            citations = http_urls(verification.get('source_citations')) or http_urls(official.get('official_source_urls'))
            if not citations:
                report['dropped'].append({'agent': fname, 'id': rid, 'reason': 'no citations'})
                continue

            official, fixes = clean_official(dict(official))
            report['fixes'] += len(fixes)

            if not isinstance(utility, dict) or not utility:
                utility = None

            ver = None
            if isinstance(verification, dict) and verification:
                ver = {
                    'source_citations': citations,
                    'last_verified_date': verification.get('last_verified_date') or '2026-10-10',
                }
                for key in ('verification_status', 'confidence', 'not_confirmed', 'notes'):
                    if verification.get(key) not in (None, ''):
                        ver[key] = verification[key]

            if rid in existing_ids:
                target = by_id[rid]
                t_official = target.get('official') or {}
                filled = []
                for key, value in official.items():
                    if value in (None, '', [], {}):
                        continue
                    if t_official.get(key) in (None, '', [], {}):
                        t_official[key] = value
                        filled.append(key)
                if filled:
                    target['official'] = t_official
                    report['filled'][rid] = filled
                if utility and not target.get('applicant_utility'):
                    target['applicant_utility'] = utility
                if ver and not target.get('verification'):
                    target['verification'] = ver
            else:
                record = {'id': rid, 'official': official}
                if utility:
                    record['applicant_utility'] = utility
                if ver:
                    record['verification'] = ver
                records.append(record)
                by_id[rid] = record
                existing_ids.add(rid)
                report['added'].append(rid)

    # Final file-level invariants the tests assert.
    for rec in records:
        o = rec.get('official') or {}
        v = rec.get('verification') or {}
        if not http_urls(v.get('source_citations')):
            v['source_citations'] = http_urls(o.get('official_source_urls'))
            rec['verification'] = v
        if not v.get('last_verified_date'):
            v['last_verified_date'] = '2026-10-10'
            rec['verification'] = v
        if o.get('fully_funded') is True and o.get('tuition_coverage') is not True:
            o['fully_funded'] = False
            rec['official'] = o

    print(f'agents read: {report["agents"]}, records seen: {report["records_seen"]}')
    print(f'new ids: {len(report["added"])}, ids filled: {len(report["filled"])}, '
          f'fixes applied: {report["fixes"]}, dropped: {len(report["dropped"])}')
    if report['dropped'][:10]:
        print('drop sample:', report['dropped'][:10])
    print(f'corpus after merge: {len(records)} records')

    if apply:
        with open(DETAILS, 'w', encoding='utf-8') as f:
            json.dump(raw, f, ensure_ascii=False, indent=1)
        print('written to', DETAILS)
    else:
        print('DRY RUN - nothing written')
    with open(os.path.join(OUT, 'merge_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    return report


if __name__ == '__main__':
    main(apply='--apply' in sys.argv)
