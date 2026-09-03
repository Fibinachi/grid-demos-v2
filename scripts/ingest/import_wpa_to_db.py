#!/usr/bin/env python3
"""
Import clean WPA entries to database (wpa.db).
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

def clean_name(name):
    """Clean church name."""
    # Remove leading junk
    name = re.sub(r'^[A-Z]{2,}\s*', '', name)
    name = re.sub(r'^CHURCH\s*N[ZA]*ME\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s{2,}.*$', '', name)
    return name.strip('. ,;')

def main():
    # Load entries
    entries = json.loads((WPA_DIR / "clean_wpa_entries.json").read_text())
    
    # Clean names
    for e in entries:
        e['church_name'] = clean_name(e['church_name'])
    
    # Remove duplicates
    seen = set()
    clean = []
    for e in entries:
        name = e['church_name']
        if name and len(name) > 3 and name not in seen:
            seen.add(name)
            clean.append(e)
    
    print(f"After dedup: {len(clean)} entries from {len(entries)} original")
    
    # Create DB
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    
    cur.execute("""CREATE TABLE IF NOT EXISTS wpa_churches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state TEXT,
        church_name TEXT,
        source_file TEXT
    )""")
    
    # Insert
    for e in clean[:2000]:  # Limit for demo
        cur.execute("INSERT INTO wpa_churches (state, church_name, source_file) VALUES (?, ?, ?)",
                   (e.get('state', ''), e.get('church_name', ''), 'WPA'))
    
    conn.commit()
    conn.close()
    
    print(f"Imported to {DB_PATH}")

if __name__ == "__main__":
    main()