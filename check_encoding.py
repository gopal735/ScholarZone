# Check file encoding
with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\base_snapshot.json', 'rb') as f:
    header = f.read(10)
    print(f"Header bytes: {header}")

# Try different encodings
for enc in ['utf-8', 'utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'latin-1', 'cp1252']:
    try:
        with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\base_snapshot.json', 'r', encoding=enc) as f:
            content = f.read(100)
            print(f"Encoding {enc}: OK - {content[:50]}")
            break
    except Exception as e:
        print(f"Encoding {enc}: {e}")