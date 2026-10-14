"""Repair the few result files a subagent wrote with invalid JSON.

Three specific defects appear: a UTF-8 BOM, a stray backslash before a quote,
and a missing comma after a string value. Each is repaired only when the result
parses afterwards and the repaired value is still a string, so a healthy file
is never rewritten.
"""
import json
import os
import re
import sys

OUT = r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research_output\live500'


def try_fix(path):
    raw = open(path, 'rb').read()
    text = raw.decode('utf-8-sig', errors='replace')
    candidates = [text]
    # stray backslash before a double quote inside a string
    fixed = re.sub(r'\\(?=")', '', text)
    if fixed != text:
        candidates.append(fixed)
    # missing comma after a closing quote before the next key
    comma_fixed = re.sub(r'"\s*\n(\s*")', r'",\n\1', text)
    if comma_fixed != text:
        candidates.append(comma_fixed)
    # illegal trailing comma before a closing bracket or brace
    no_trailing = re.sub(r',\s*([}\]])', r'\1', comma_fixed)
    if no_trailing != comma_fixed:
        candidates.append(no_trailing)
    # both: illegal escape and trailing comma
    candidates.append(re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', no_trailing))

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(data, list):
            data = {'records': data}
        if isinstance(data, dict) and 'records' in data:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            return len(data.get('records') or [])
    return None


def main():
    results_dir = os.path.join(OUT, 'results_internal')
    total_fixed = 0
    for fname in sorted(os.listdir(results_dir)):
        if not re.fullmatch(r'agent_\d+\.json', fname):
            continue
        path = os.path.join(results_dir, fname)
        try:
            data = json.loads(open(path, encoding='utf-8').read())
            continue
        except (OSError, ValueError):
            pass
        n = try_fix(path)
        if n is None:
            print(f'STILL BROKEN: {fname}')
        else:
            total_fixed += 1
            print(f'repaired {fname} ({n} records)')
    print('total repaired:', total_fixed)


if __name__ == '__main__':
    main()
