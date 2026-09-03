#!/usr/bin/env python3
"""
Comprehensive OCR cleanup for WPA entries.
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

# Load entries
entries = json.loads((WPA_DIR / "wpa_all_final.json").read_text())

# Extensive OCR fix patterns
FIXES = [
    # Character fixes
    (r'#', 't'),
    (r'vv', 'w'),
    
    # Word fixes
    (r'\bAssombly\b', 'Assembly'),
    (r'\bAssembly\s+ef\s+God\b', 'Assembly of God'),
    (r'\bAssembly\s+of\s+\-God\b', 'Assembly of God'),
    (r'\bCedar\s+Glede\b', 'Cedar Grove'),
    (r'\bCppelo\b', 'Cedar Plantation'),
    (r'\bCole\s+tission\b', 'Cole Mission'),
    (r'\bMmethodist\b', 'Methodist'),
    (r'\bPleasant\s+Eome\b', 'Pleasant Home'),
    (r'\bChapol\b', 'Chapel'),
    (r'\bChureh\b', 'Church'),
    (r'\bTho\s+Coo?r\b', 'Three Cross'),
    (r'\bBethel\s+Springs\b', 'Bethel Springs'),
    (r'\bGlefasant\b', 'Pleasant'),
]

def fix_entry(name):
    for pat, repl in FIXES:
        if isinstance(repl, str):
            name = re.sub(pat, repl, name, flags=re.IGNORECASE)
        else:
            name = re.sub(pat, repl, name)
    return name.strip()

# Apply fixes
fixed_count = 0
for e in entries:
    original = e['church_name']
    fixed = fix_entry(original)
    if fixed != original:
        e['church_name'] = fixed
        fixed_count += 1

# Save cleaned
output_path = WPA_DIR / "wpa_cleaned_final.json"
output_path.write_text(json.dumps(entries, indent=2), encoding='utf-8')
print(f"Fixed {fixed_count} entries")
print(f"Total: {len(entries)} entries saved to wpa_cleaned_final.json")

# Import to DB
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute("DELETE FROM wpa_churches")

for e in entries:
    cur.execute("INSERT INTO wpa_churches (state, church_name) VALUES (?, ?)", (e['state'], e['church_name']))

conn.commit()
conn.close()
print("Updated wpa.db")