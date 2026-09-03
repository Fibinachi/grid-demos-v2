"""Rebuild WPA parser - filter out section headers, focus on actual church entries."""
import sqlite3, re, os
from pathlib import Path
from collections import defaultdict

WPA_DIR = Path('E:/grid/data/wpa')
WPA_DB = 'E:/grid/wpa.db'

# ── Better filters ──────────────────────────────────────────────────
# Lines that are definitely NOT individual churches
NON_CHURCH_PATTERNS = [
    r'^[A-Z\s]{10,}$',                 # ALL CAPS headers
    r'^THE\s+(?:ROMAN\s+)?CATHOLIC\s+CHURCH',  # Catholic header
    r'^INVENTORY\s+OF',                 # Title page
    r'^SURVEY\s+OF',                    # Title page  
    r'^HISTORICAL\s+RECORDS',           # Title page
    r'^WORKS?\s+PROGRESS',              # Title page
    r'^WORK\s+PROJECTS?',               # Title page
    r'^\d+\s*$',                        # Page numbers
    r'^\(?continued\)?$',              # Continuation markers
    r'^DISTRICT\s+(?:NO\.?\s*)?\d+',   # District headers
    r'^(?:NORTH|SOUTH|EAST|WEST|CENTRAL)\s+(?:SECTION|DISTRICT|REGION)',
    r'^NOTE:?\s',                       # Notes
    r'^(?:Preface|Foreword|Introduction|Table\s+of\s+Contents|Index|Bibliography|Appendix)',
    r'^(?:Prepared|Published|Sponsored|Compiled|Edited)\s+by',
    r'^(?:Copyright|All\s+rights|Printed\s+in)',
    r'^(?:Florence|Howard|John|William|Robert|James|Mary|Elizabeth)\s+\w+,\s+(?:Assistant\s+)?(?:Commissioner|Director|Supervisor|Editor)',
    r'^has\s+financed',                 # Narrative text
    r'^This\s+(?:inventory|volume|survey)', # Narrative text
    r'^The\s+(?:Inventory|Survey|Historical)', # Title references
    r'^[A-Z\s\-]{5,}:$',               # Labels with colons
]

# Patterns that indicate an actual church entry
CHURCH_ENTRY_PATTERNS = [
    r'\b(?:St\.|Saint|Ste\.)\s+\w+',    # Saint names
    r'\b(?:First|Second|Third|Fourth|Fifth)\s+\w+\s+Church',
    r'\b(?:Mt\.|Mount)\s+\w+',          # Mount names
    r'\b(?:Bethel|Calvary|Zion|Ebenezer|Shiloh|Antioch|Salem|Moriah|Carmel)\b',
    r'\b(?:Emmanuel|Immanuel|Trinity|Grace|Faith|Hope|Charity)\s+Church',
    r'\b(?:New\s+(?:Hope|Life|Bethel|Jerusalem|Zion)|Pleasant\s+(?:Hill|Grove|View))\b',
    r'\b(?:Church|Chapel|Mission|Tabernacle|Cathedral)\s+of\b',
    r'\b(?:Our\s+(?:Lady|Savior|Redeemer)|Sacred\s+Heart|Holy\s+(?:Cross|Trinity|Family|Name|Rosary|Ghost|Spirit))\b',
    r'\b(?:Bethlehem|Nazareth|Gethsemane|Olivet|Macedonia|Beulah|Rehoboth)\b',
    r'\b(?:Gospel|Bible|Community|Union|Free|Independent)\s+(?:Church|Chapel|Tabernacle|Hall)\b',
    r'\b(?:Friends?|Quaker)\s+Meeting',
    r'\bKingdom\s+Hall\b',
    r'\(.*?(?:Street|Avenue|Road|Drive|Lane|Route|R\.\s*F\.\s*D|RFD)',
]

def is_church_entry(line):
    """Check if a line is likely an actual church entry, not a header."""
    clean = line.strip()
    if len(clean) < 8 or len(clean) > 200:
        return False
    
    # Reject known non-church patterns
    for pat in NON_CHURCH_PATTERNS:
        if re.match(pat, clean, re.IGNORECASE):
            return False
    
    # Must match at least one church entry pattern
    for pat in CHURCH_ENTRY_PATTERNS:
        if re.search(pat, clean, re.IGNORECASE):
            return True
    
    # Also accept lines that look like: "Name, Town" or "Name Town County"
    # If it contains a known denominational keyword AND looks like a proper name
    denom_words = ['baptist', 'methodist', 'presbyterian', 'lutheran', 'catholic',
                   'episcopal', 'adventist', 'pentecostal', 'nazarene', 'holiness',
                   'reformed', 'mennonite', 'brethren', 'congregational',
                   'assembly of god', 'church of god', 'church of christ',
                   'disciples of christ', 'united brethren', 'salvation army']
    has_denom = any(d in clean.lower() for d in denom_words)
    
    # Must have at least one capitalized word that looks like a name
    words = clean.split()
    proper_names = [w for w in words if w[0].isupper() and len(w) > 1]
    
    if has_denom and len(proper_names) >= 2:
        return True
    
    return False

# ── Re-extract records ──────────────────────────────────────────────
def extract_ocr(filepath):
    text = filepath.read_text(encoding='utf-8', errors='replace')
    pre = re.search(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL)
    if not pre:
        return []
    ocr = pre.group(1).replace('&lt;','<').replace('&gt;','>').replace('&amp;','&').replace('&quot;','"')
    return [l.strip() for l in ocr.split('\n') if l.strip()]

def parse_record_from_line(line, state, denomination, volume_id, volume_year):
    """Extract structured data from a church entry line."""
    clean = line.strip()
    
    name = clean
    city = ''
    county = ''
    address = ''
    
    # Try splitting on 3+ spaces (column separator in original)
    parts = re.split(r'\s{3,}', clean)
    if len(parts) >= 2:
        name = parts[0].strip()
        city = parts[1].strip() if len(parts) > 1 else ''
        county = parts[-1].strip() if len(parts) > 2 else ''
    
    # Clean OCR noise
    name = re.sub(r'[|{}[\]~`@#$%^*+=/\\]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    city = re.sub(r'[^a-zA-Z\s\-.]', '', city).strip()
    county = re.sub(r'[^a-zA-Z\s\-.]', '', county).strip()
    
    # Extract address from name
    addr_match = re.search(r'\(([^)]*)\)', name)
    if addr_match:
        address = addr_match.group(1).strip()
        name = name.replace(f'({addr_match.group(1)})', '').strip()
    
    if len(name) < 4:
        return None
    
    return {
        'church_name': name[:200],
        'city': city[:100],
        'county': county[:100],
        'state': state or '',
        'denomination': denomination or '',
        'address_text': address[:200],
        'raw_text': clean[:500],
        'volume_id': volume_id,
        'volume_year': volume_year,
        'confidence': 0.6 if (city and county) else 0.4,
    }

def main():
    db = sqlite3.connect(WPA_DB)
    
    # Clear existing records for clean rebuild
    db.execute('DELETE FROM wpa_records')
    db.execute('DELETE FROM wpa_matches')
    db.execute('DELETE FROM wpa_locations')
    db.commit()
    
    # Get volumes
    volumes = db.execute('SELECT id, ia_id, state, volume_type, denomination, year, filename FROM wpa_volumes').fetchall()
    
    files = sorted(WPA_DIR.glob('*.txt'))
    file_map = {fp.name: fp for fp in files}
    
    print(f'Rebuilding WPA records from {len(volumes)} volumes...\n')
    
    total_records = 0
    record_batch = []
    
    RECORD_COLS = ['volume_id', 'page_num', 'line_num', 'raw_text', 'church_name',
                   'address_text', 'city', 'county', 'state', 'denomination',
                   'confidence', 'source_context']
    
    for vi, vol in enumerate(volumes):
        vid, ia_id, state, vtype, denom, year, filename = vol
        
        fp = file_map.get(filename)
        if not fp:
            continue
        
        lines = extract_ocr(fp)
        if not lines:
            continue
        
        vol_records = 0
        for line_num, line in enumerate(lines):
            if not is_church_entry(line):
                continue
            
            rec = parse_record_from_line(line, state, denom, vid, year)
            if rec:
                record_batch.append((
                    vid, 1, line_num, rec['raw_text'], rec['church_name'],
                    rec['address_text'], rec['city'], rec['county'], rec['state'],
                    rec['denomination'], rec['confidence'], ''
                ))
                vol_records += 1
                
                if len(record_batch) >= 1000:
                    placeholders = ', '.join(['?'] * len(RECORD_COLS))
                    db.executemany(
                        f'INSERT INTO wpa_records ({", ".join(RECORD_COLS)}) VALUES ({placeholders})',
                        record_batch
                    )
                    record_batch = []
        
        if record_batch:
            placeholders = ', '.join(['?'] * len(RECORD_COLS))
            db.executemany(
                f'INSERT INTO wpa_records ({", ".join(RECORD_COLS)}) VALUES ({placeholders})',
                record_batch
            )
            record_batch = []
        
        db.execute('UPDATE wpa_volumes SET record_count=? WHERE id=?', (vol_records, vid))
        db.commit()
        
        total_records += vol_records
        state_str = f'[{state}]' if state else ''
        print(f'  [{vi+1:3d}/{len(volumes)}] {filename[:45]:45s} {state_str:5s} {denom or "":20s} {vol_records:>6,d} records  (total: {total_records:,})')
    
    # Rebuild locations
    db.execute('DELETE FROM wpa_locations')
    db.execute('''
        INSERT OR IGNORE INTO wpa_locations (city, county, state)
        SELECT DISTINCT city, county, state FROM wpa_records
        WHERE city != '' AND state != ''
    ''')
    db.commit()
    
    total = db.execute('SELECT COUNT(*) FROM wpa_records').fetchone()[0]
    with_state = db.execute("SELECT COUNT(*) FROM wpa_records WHERE state != '' AND city != ''").fetchone()[0]
    
    print(f'\n{"="*60}')
    print(f'Rebuild complete: {total:,} records ({with_state:,} with city+state)')
    db.close()

if __name__ == '__main__':
    main()
