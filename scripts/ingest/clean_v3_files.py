"""
Clean v3 parsed CSVs - remove non-entries, fix diocese names, track places/times.
"""
import csv, re
from pathlib import Path
from collections import defaultdict

PARSED_DIR = Path("E:/grid/data/denom/catholic_official_parsed_v3")
OUTPUT_DIR = Path("E:/grid/data/denom/catholic_official_parsed_clean")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Patterns to remove (non-church entries)
REMOVE_PATTERNS = [
    r'guild$', r'craftsman', r'candle', r'company$', r'association$',
    r'foundation$', r'nursery$', r'asylum$', r'shelter$', r'center$',
    r'bureau$', r'commission$', r'committee$', r'club$', r'school$',
    r'hospital$', r'orphan', r'retreat$', r'inc\.?$', r'llc$',
]

def is_church_entry(name):
    """Check if name is a church/parish entry."""
    if not name or len(name) < 6:
        return False
    name_lower = name.lower()
    
    # Remove if matches bad patterns
    for p in REMOVE_PATTERNS:
        if re.search(p, name_lower):
            return False
    
    # Must have church indicator
    church_indicators = ['st.', 'sts.', 'cathedral', 'church', 'mission', 'shrine', 'basilica', 'chapel']
    return any(ind in name_lower for ind in church_indicators)

def clean_diocese(d):
    """Extract clean diocese name."""
    if not d:
        return d
    # Remove "to the Diocese of" patterns
    d = re.sub(r'^.*(diocese|archdiocese)\s+of\s+', '', d, flags=re.I)
    d = d.strip('.,;').strip()
    return d

def main():
    years_data = {}
    
    csvs = sorted(PARSED_DIR.glob("catholic_*.csv"))
    print(f"Processing {len(csvs)} files...")
    
    total_before = 0
    total_after = 0
    
    for cp in csvs:
        year = int(cp.stem.split('_')[1])
        
        with open(cp, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.read().split('\n')
        
        # Process lines
        cleaned = []
        header = lines[0] if lines else ''
        for line in lines[1:]:
            if not line.strip():
                continue
            
            # Parse CSV manually (handle commas in fields)
            parts = line.split(',')
            # Expected: year,diocese,state,city,name,source_file,source_line
            # But diocese may contain commas, so we need to be smarter
            # If 6+ parts, last three are source_file, source_line
            # name is 4th field, diocese is 2nd field
            
            if len(parts) >= 6:
                # name is field index 4
                name = parts[4].strip() if len(parts) > 4 else ''
                if is_church_entry(name):
                    cleaned.append(line)
        
        if cleaned:
            out_path = OUTPUT_DIR / f"catholic_{year}.csv"
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(header + '\n')
                for line in cleaned:
                    f.write(line + '\n')
            total_before += len(lines) - 1
            total_after += len(cleaned)
            print(f"  {year}: {len(cleaned):,}/{len(lines)-1}")
    
    print(f"\nTotal before: {total_before:,}")
    print(f"Total after: {total_after:,}")
    print(f"Removed: {total_before - total_after:,}")

if __name__ == '__main__':
    main()