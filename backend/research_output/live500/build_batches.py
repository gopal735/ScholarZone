import glob, json, os, re

OUT = r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research_output\live500'
BATCHES = os.path.join(OUT, 'batches')
os.makedirs(BATCHES, exist_ok=True)
os.makedirs(os.path.join(OUT, 'results_internal'), exist_ok=True)

have = set()
for f in glob.glob(os.path.join(OUT, 'results', 'agent_*.json')):
    have.add(int(re.search(r'agent_(\d+)', os.path.basename(f)).group(1)))
missing = [i for i in range(500) if i not in have]
print('missing assignments:', len(missing))

CHUNK = 7
chunks = [missing[i:i + CHUNK] for i in range(0, len(missing), CHUNK)]
manifest = []
for n, chunk in enumerate(chunks, 1):
    name = f'batch_{n:02d}'
    payload = {
        'batch': name,
        'agents': chunk,
        'assignment_files': [f'assignments/agent_{i:03d}.json' for i in chunk],
        'result_files': [f'results_internal/agent_{i:03d}.json' for i in chunk],
    }
    with open(os.path.join(BATCHES, f'{name}.json'), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    manifest.append({'batch': name, 'agents': chunk})
with open(os.path.join(BATCHES, 'manifest.json'), 'w', encoding='utf-8') as f:
    json.dump({'total_batches': len(manifest), 'missing': missing, 'batches': manifest}, f, ensure_ascii=False, indent=1)
print('batches written:', len(manifest), 'sizes:', [len(m['agents']) for m in manifest])
