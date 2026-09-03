"""
Final clean - remove OCR artifacts and non-church entries.
"""
import csv, re

INPUT = 'E:/grid/data/denom/catholic_directories_final_clean.csv'
OUTPUT = 'E:/grid/data/denom/catholic_directories_clean_v2.csv'

# Remove patterns
BAD_PATTERNS = [
    r'^\d+\s*(mile|mi|m) from', r'county$', r'once a month', r'once a week',
    r'quarterly', r'monthly', r'st\.?\s*$', r'ann arundel', r'nelson co',
    r'perry co', r'fred erick',
]

def clean_name(name):
    """Clean OCR artifacts from name."""
    if not name:
        return name
    # Fix common OCR patterns
    name = re.sub(r'[|#{}[\]]', '', name)
    name = re.sub(r'\s{2,}', ' ', name)
    return name.strip()

def is_church(name):
    """Check if entry is a church."""
    if not name or len(name) < 5:
        return False
    # Remove bad patterns
    for p in BAD_PATTERNS:
        if re.search(p, name, re.I):
            return False
    # Must have church indicator OR be short (parish name)
    indicators = ['st.', 'sts.', 'cathedral', 'church', 'mission', 'shrine', 'basilica', 'chapel', 'parish', 'our lady']
    name_lower = name.lower()
    if any(ind in name_lower for ind in indicators):
        return True
    # Short names without indicators might still be valid parishes
    if len(name) <= 20 and not any(x in name_lower for x in ['county', 'mile', ',', ';', '—', '(', ')']):
        return True
    return False

def main():
    kept = 0
    removed = 0
    
    with open(INPUT, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['year', 'name', 'diocese', 'state', 'city', 'grid_church_id'])
        w.writeheader()
        
        for r in rows:
            name = clean_name(r['name'])
            if is_church(name):
                r['name'] = name
                w.writerow(r)
                kept += 1
            else:
                removed += 1
    
    print(f"Kept {kept:,}, removed {removed:,}")

if __name__ == '__main__':
    main()