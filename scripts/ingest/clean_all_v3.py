"""
Clean all v3 parsed CSVs - fix diocese names, remove non-church entries.
"""
import re, csv
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading

PARSED_DIR = Path("E:/grid/data/denom/catholic_official_parsed_v3")
OUTPUT_DIR = Path("E:/grid/data/denom/catholic_official_parsed_clean")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Patterns to remove (non-church entries)
REMOVE_PATTERNS = [
    r'craftsman', r'candle', r'company$', r'association$', r'foundation$',
    r'nursery$', r'asylum$', r'shelter$', r'center$', r'bureau$',
    r'commission$', r'committee$', r'club$', r'llc$', r'inc\.?$',
]

def clean_line(line, year):
    """Clean a single CSV line."""
    parts = line.split(',')
    if len(parts) < 6:
        return None
    
    name = parts[4].strip()
    if not name or len(name) < 6:
        return None
    
    # Remove non-church entries
    name_lower = name.lower()
    for p in REMOVE_PATTERNS:
        if re.search(p, name_lower):
            return None
    
    # Must have church indicator
    church_indicators = ['st.', 'sts.', 'cathedral', 'church', 'mission', 'shrine', 'basilica', 'chapel']
    if not any(ind in name_lower for ind in church_indicators):
        return None
    
    return line

def process_file(cp):
    """Process a single year file."""
    year = int(cp.stem.split('_')[1])
    
    try:
        with open(cp, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.read().split('\n')
    except:
        return year, 0, 0
    
    header = lines[0]
    cleaned = []
    
    for line in lines[1:]:
        if line.strip():
            result = clean_line(line, year)
            if result:
                cleaned.append(result)
    
    if cleaned:
        out_path = OUTPUT_DIR / f"catholic_{year}.csv"
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(header + '\n')
            for line in cleaned:
                f.write(line + '\n')
    
    return year, len(cleaned), len(lines) - 1

def main():
    csvs = sorted(PARSED_DIR.glob("catholic_*.csv"))
    print(f"Processing {len(csvs)} files...")
    
    total_in = 0
    total_out = 0
    
    for cp in csvs:
        year, out, inp = process_file(cp)
        total_in += inp
        total_out += out
        print(f"  {year}: {out:,}/{inp:,}")
    
    print(f"\nTotal: {total_out:,}/{total_in:,}")

if __name__ == '__main__':
    main()