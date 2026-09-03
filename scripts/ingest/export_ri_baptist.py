#!/usr/bin/env python3
"""
Extract Rhode Island Baptist inventory entries from wpa_records.

The data is parsed by OCR line. Some lines have complete entries:
"Church Name, dates, location. page_refs"

We need to:
1. Extract valid entries from lines
2. Parse dates and locations
3. Create structured output for geographic/temporal linking
"""
import re, sqlite3
from pathlib import Path

WPA_DB = Path("E:/grid/wpa.db")

def extract_ri_entries():
    wpa = sqlite3.connect(WPA_DB)
    wpa.row_factory = sqlite3.Row
    
    # Get all lines from vol 38
    rows = wpa.execute("SELECT id, line_num, church_name, raw_text FROM wpa_records WHERE volume_id=38 ORDER BY line_num").fetchall()
    
    entries = []
    current_entry = None
    
    for r in rows:
        line = (r['church_name'] or r['raw_text'] or '').strip()
        if not line:
            continue
        
        # Clean up
        line = re.sub(r'\s+', ' ', line).strip()
        # Remove trailing page numbers and dots
        line = re.sub(r'\.{2,}\s*\d+\s*$', '', line)
        
        # Check if this line starts a numbered entry
        # Pattern: "NUM Church Name, dates" where NUM is 1-3 digits
        m = re.match(r'^(\d{1,3})\s+(.+)$', line)
        if m:
            # New numbered entry
            if current_entry:
                entries.append(current_entry)
            num = m.group(1)
            content = m.group(2)
            
            # Parse content: "First Baptist Church, 1805--, Pawtucket"
            m2 = re.match(r'^([A-Z][^\d,]{5,100}?),\s*([\d\-–\?\.\s]{1,30})(?:,\s*([^\.]{3,60}))?', content)
            if m2:
                current_entry = {
                    'entry_num': int(num),
                    'church_name': m2.group(1).strip(),
                    'dates': m2.group(2).strip(),
                    'location': m2.group(3).strip() if m2.group(3) else None,
                    'raw': line[:150]
                }
            else:
                current_entry = None
        else:
            # Continuation of previous entry or narrative
            if current_entry and len(current_entry['church_name']) < 50:
                # Could be continuation
                pass
    
    if current_entry:
        entries.append(current_entry)
    
    wpa.close()
    return entries

def clean_dates(dates):
    """Normalize date string to year range."""
    if not dates:
        return None, None
    dates = re.sub(r'\.{2,}', '-', dates)
    dates = re.sub(r'—', '-', dates)
    years = re.findall(r'(\d{4})', dates)
    if years:
        founding = int(years[0])
        closing = int(years[-1]) if len(years) > 1 else None
        return founding, closing
    return None, None

if __name__ == "__main__":
    entries = extract_ri_entries()
    print(f"Found {len(entries)} numbered entries")
    
    # Group by location
    by_loc = {}
    for e in entries:
        loc = e['location'] or 'Unknown'
        # Clean OCR
        loc = re.sub(r'\s+\.\s*$', '', loc)
        by_loc[loc] = by_loc.get(loc, 0) + 1
    
    print("\n=== Churches by location (top 15) ===")
    for loc, count in sorted(by_loc.items(), key=lambda x: -x[1])[:15]:
        print(f"  {loc}: {count}")
    
    # Count with dates
    with_dates = [e for e in entries if e['dates']]
    print(f"\nEntries with dates: {len(with_dates)}")
    
    print("\n=== Sample entries ===")
    for e in entries[:10]:
        founding, closing = clean_dates(e['dates'])
        print(f"  {e['entry_num']}. {e['church_name']}")
        print(f"     Years: {e['dates']} = {founding}-{closing}")
        print(f"     Location: {e['location']}")