import os
for root, dirs, files in os.walk(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone"):
    for f in files:
        if f == "taxonomy.py":
            print(os.path.join(root, f))