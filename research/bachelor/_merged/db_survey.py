import sqlite3, glob, os, json

targets = []
for p in glob.glob('**/*.db', recursive=True):
    if 'worktrees' in p:
        continue
    targets.append(p)

print('=== sqlite files (excluding worktrees) ===')
for p in sorted(targets):
    if os.path.getsize(p) == 0:
        print('%-55s EMPTY' % p)
        continue
    try:
        c = sqlite3.connect(p)
        t = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        cnt = None
        cols = []
        if 'scholarships' in t:
            cnt = c.execute('SELECT COUNT(*) FROM scholarships').fetchone()[0]
            cols = [r[1] for r in c.execute('PRAGMA table_info(scholarships)')]
        print('%-55s rows=%-6s cols=%-3s is_archived=%-5s verified_status=%s' % (
            p, cnt, len(cols), 'is_archived' in cols, 'verification_status' in cols))
        c.close()
    except Exception as e:
        print('%-55s ERR %s' % (p, e))
