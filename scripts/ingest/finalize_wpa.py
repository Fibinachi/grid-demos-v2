#!/usr/bin/env python3
"""
Finalize WPA entries - import corrected data.
"""
import json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

entries = json.loads((WPA_DIR / "wpa_manually_corrected.json").read_text())

# Clean again - remove very short entries
clean = []
for e in entries:
    name = e.get('church_name', '').strip()
    if len(name) >= 8 and not name.lower().startswith(('rt.', 'church name')):
        clean.append(e)

print(f"Clean entries: {len(clean)}")

# Import to DB
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute("DELETE FROM wpa_churches")

for e in clean:
    cur.execute("INSERT INTO wpa_churches (state, church_name) VALUES (?, ?)", (e['state'], e['church_name']))

conn.commit()
conn.close()
print("Updated wpa.db")