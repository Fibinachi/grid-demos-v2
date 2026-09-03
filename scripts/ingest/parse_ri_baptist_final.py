#!/usr/bin/env python3
"""
WPA Rhode Island Baptist Inventory Parser - Production.
Extracts churches with dates and locations for geographic/temporal linking.
"""
import re, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

def load_clean_text(filepath):
    text = filepath.read_text(encoding='utf-8', errors='replace')
    clean = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def parse_inventory(text):
    """
    Parse run-together numbered format.
    "73 First Baptist Church, 1805--, Pawtucket . . . 74 First Baptist..."
    """
    entries = []
    
    # Find inventory start (line 73)
    idx = text.find("73 First Baptist Church, 1805")
    if idx < 0:
        return entries
    
    content = text[idx:]
    
    # Split on " NUM " where NUM is a standalone number
    # Use negative lookbehind to ensure not preceded by digit
    # Split at every position between entries
    
    # Actually, just find all "NUMBER Church..." patterns
    # Dates pattern: years like 1805--, 1829--, 1701-1906, 1749? - about 1832
    
    pattern = r'(\d{1,3})\s+((?:[A-Z][^\d]{3,80}?Church|Congregation|Mission)[^,\d]{0,60})'
    
    for m in re.finditer(r'(\d{1,3})\s+((?:[A-Z][A-Za-z][^\d]{3,80}?)(?:,\s*([\d\-–]{1,20})(?:\s*,\s*([^\.]{3,40}))?)?', content):
        num = int(m.group(1))
        name = m.group(2).strip()
        dates = m.group(3).strip() if m.group(3) else None
        location = m.group(4).strip() if m.group(4) else None
        
        # Clean OCR artifacts
        if dates:
            dates = re.sub(r'\.{2,}', '-', dates)
            dates = dates.replace('—', '-').replace(' ', '')
        
        entries.append({
            'entry_number': num,
            'church_name': name,
            'dates': dates,
            'location': location
        })
    
    return entries

if __name__ == "__main__":
    text = load_clean_text(WPA_DIR / "inventoryofchurc00unse_0.txt")
    entries = parse_inventory(text)
    
    # Filter valid entries
    valid = []
    for e in entries:
        # Must have a year in dates (4 digits) or be a known church pattern
        if e['dates'] and re.search(r'\d{4}', e['dates']):
            valid.append(e)
        elif 'Church' in e['church_name'] and len(e['church_name']) > 10:
            valid.append(e)
    
    print(f"Found {len(valid)} valid entries")
    
    # Group by location
    by_loc = {}
    for e in valid:
        loc = e['location'] or 'Unknown'
        loc = loc.strip()
        by_loc[loc] = by_loc.get(loc, 0) + 1
    
    print("\n=== Locations with 3+ churches ===")
    for loc, count in sorted(by_loc.items(), key=lambda x: -x[1]):
        if count >= 3 and loc != 'Unknown':
            print(f"  {loc}: {count}")
    
    # Save to DB
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS wpa_baptist_ri (
        id INTEGER PRIMARY KEY,
        entry_number INTEGER,
        church_name TEXT,
        dates TEXT,
        location TEXT
    )""")
    conn.execute("DELETE FROM wpa_baptist_ri")
    for e in valid:
        conn.execute("INSERT INTO wpa_baptist_ri (entry_number, church_name, dates, location) VALUES (?,?,?,?)",
            (e['entry_number'], e['church_name'], e['dates'] or '', e['location'] or ''))
    conn.commit()
    
    print(f"\nSaved {len(valid)} entries to wpa_baptist_ri")
    
    # Show sample
    cur = conn.execute("SELECT * FROM wpa_baptist_ri ORDER BY entry_number LIMIT 15")
    for r in cur.fetchall():
        print(f"  {r[1]}: {r[2]} [{r[3]}] - {r[4]}")
    
    conn.close()