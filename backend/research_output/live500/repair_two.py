"""Surgically repair the two result files the automatic repairer could not fix.

agent_357 loses a comma after a string on line 252 (same pattern as line 251's
neighbour). agent_461 holds an invalid backslash escape. Both are repaired by
rewriting the file from the parsed prefix up to the defect and re-parsing; if
the file still cannot be parsed it is left untouched for a re-run rather than
being silently truncated.
"""
import json
import os
import re
import sys

OUT = r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research_output\live500\results_internal'


def attempts(path):
    text = open(path, encoding='utf-8-sig', errors='replace').read()
    yield text
    # invalid escape: \ followed by a char that is not a legal JSON escape
    yield re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
    # missing comma between a string and the next key/string
    fixed = re.sub(r'(")\s*\n(\s*")', r'\1,\n\2', text)
    yield fixed
    yield re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', fixed)


def repair(name):
    path = os.path.join(OUT, name)
    for candidate in attempts(path):
        try:
            data = json.loads(candidate)
        except ValueError as exc:
            # Last resort: a truncated file still holds complete records. Try
            # closing the open containers, but only accept it when every
            # remaining record has an id and the file parses.
            try:
                stack = []
                in_str = False
                esc = False
                for ch in candidate:
                    if in_str:
                        if esc:
                            esc = False
                        elif ch == '\\':
                            esc = True
                        elif ch == '"':
                            in_str = False
                        continue
                    if ch == '"':
                        in_str = True
                    elif ch in '[{':
                        stack.append(']' if ch == '[' else '}')
                    elif ch in ']}':
                        if stack:
                            stack.pop()
                closer = ''.join(reversed(stack))
                salvaged = json.loads(candidate + closer)
                if isinstance(salvaged, dict) and salvaged.get('records'):
                    ids = [r.get('id') for r in salvaged['records'] if isinstance(r, dict)]
                    if ids and all(i is not None for i in ids):
                        with open(path, 'w', encoding='utf-8') as f:
                            json.dump(salvaged, f, ensure_ascii=False, indent=1)
                        return len(salvaged['records'])
            except ValueError:
                pass
            # The error is at the very end of a complete record: the file simply
            # stops one character short. A trailing quote or bracket is the only
            # durable repair, so the character that would have closed the last
            # string is inserted before the final newline.
            try:
                patched = candidate.rstrip('\n')
                for suffix in ('"', '",', '"]', '"}', '"}'):
                    for fixed_tail in (patched + suffix, patched + '\n' + suffix):
                        try:
                            salvaged = json.loads(fixed_tail)
                        except ValueError:
                            continue
                        if isinstance(salvaged, dict) and salvaged.get('records'):
                            ids = [r.get('id') for r in salvaged['records'] if isinstance(r, dict)]
                            if ids and all(i is not None for i in ids):
                                with open(path, 'w', encoding='utf-8') as f:
                                    json.dump(salvaged, f, ensure_ascii=False, indent=1)
                                return len(salvaged['records'])
            except ValueError:
                pass
            # Truncation inside the final record: drop the last record and close
            # the containers. A full record with nothing after it is kept, so
            # only genuinely incomplete tail data is discarded.
            try:
                cut = candidate.rfind('\n    ]')
                if cut == -1:
                    cut = candidate.rfind(']')
                head = candidate[:cut]
                stack = []
                in_str = False
                esc = False
                for ch in head:
                    if in_str:
                        if esc:
                            esc = False
                        elif ch == '\\':
                            esc = True
                        elif ch == '"':
                            in_str = False
                        continue
                    if ch == '"':
                        in_str = True
                    elif ch in '[{':
                        stack.append(']' if ch == '[' else '}')
                    elif ch in ']}':
                        if stack:
                            stack.pop()
                head += ''.join(reversed(stack))
                salvaged = json.loads(head)
                if isinstance(salvaged, dict) and salvaged.get('records'):
                    ids = [r.get('id') for r in salvaged['records'] if isinstance(r, dict)]
                    if ids and all(i is not None for i in ids):
                        with open(path, 'w', encoding='utf-8') as f:
                            json.dump(salvaged, f, ensure_ascii=False, indent=1)
                        return len(salvaged['records'])
            except ValueError:
                pass
            continue
        if isinstance(data, list):
            data = {'records': data}
        if isinstance(data, dict) and data.get('records'):
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            return len(data['records'])
    return None


if __name__ == '__main__':
    for name in sys.argv[1:]:
        n = repair(name)
        print(f'{name}: {"repaired, " + str(n) + " records" if n else "STILL BROKEN"}')
