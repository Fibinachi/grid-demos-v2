"""
Build wpa.db — parallel database for WPA Historical Records Survey church data.
96 volumes, 1939-1942, OCR from Internet Archive.

Schema:
  wpa_volumes    — one row per IA volume (metadata)
  wpa_pages      — raw OCR text per page
  wpa_records    — extracted church records (parsed from OCR)
  wpa_locations  — unique town/county/state tuples found
  wpa_matches    — links between wpa_records and churches.db
"""
import sqlite3, re, os, json
from pathlib import Path
from collections import defaultdict

WPA_DIR = Path('E:/grid/data/wpa')
WPA_DB = 'E:/grid/wpa.db'

# ── Schema ──────────────────────────────────────────────────────────
def create_schema(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS wpa_volumes (
            id INTEGER PRIMARY KEY,
            ia_id TEXT NOT NULL UNIQUE,
            title TEXT,
            state TEXT,
            volume_type TEXT,           -- 'directory' or 'inventory'
            year INTEGER,
            denomination TEXT,          -- for inventory volumes
            page_count INTEGER,
            total_lines INTEGER,
            record_count INTEGER DEFAULT 0,
            filename TEXT,
            file_size_kb INTEGER,
            metadata_json TEXT           -- any extra extracted metadata
        );

        CREATE TABLE IF NOT EXISTS wpa_pages (
            id INTEGER PRIMARY KEY,
            volume_id INTEGER REFERENCES wpa_volumes(id),
            page_num INTEGER,
            header_text TEXT,            -- OCR page header
            raw_text TEXT,               -- full OCR text for this page
            line_count INTEGER,
            has_church_entries INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS wpa_records (
            id INTEGER PRIMARY KEY,
            volume_id INTEGER REFERENCES wpa_volumes(id),
            page_num INTEGER,
            line_num INTEGER,
            raw_text TEXT,               -- original OCR line(s)
            church_name TEXT,
            address_text TEXT,
            city TEXT,
            county TEXT,
            state TEXT,
            denomination TEXT,
            pastor_name TEXT,
            race_label TEXT,             -- WPA often noted "White", "Colored", "Negro"
            membership_count INTEGER,
            year_built INTEGER,
            notes TEXT,
            confidence REAL DEFAULT 0.5, -- OCR extraction confidence
            source_context TEXT          -- surrounding lines for context
        );

        CREATE TABLE IF NOT EXISTS wpa_locations (
            id INTEGER PRIMARY KEY,
            city TEXT,
            county TEXT,
            state TEXT,
            record_count INTEGER DEFAULT 1,
            UNIQUE(city, county, state)
        );

        CREATE TABLE IF NOT EXISTS wpa_matches (
            id INTEGER PRIMARY KEY,
            wpa_record_id INTEGER REFERENCES wpa_records(id),
            church_id INTEGER,           -- churches.db id
            match_method TEXT,           -- 'name_city_exact', 'name_fuzzy', 'manual'
            match_score REAL,
            verified INTEGER DEFAULT 0,
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_wpa_records_volume ON wpa_records(volume_id);
        CREATE INDEX IF NOT EXISTS idx_wpa_records_city ON wpa_records(city, state);
        CREATE INDEX IF NOT EXISTS idx_wpa_records_denom ON wpa_records(denomination);
        CREATE INDEX IF NOT EXISTS idx_wpa_pages_volume ON wpa_pages(volume_id);
        CREATE INDEX IF NOT EXISTS idx_wpa_matches_church ON wpa_matches(church_id);
        CREATE INDEX IF NOT EXISTS idx_wpa_matches_wpa ON wpa_matches(wpa_record_id);
    ''')

# ── Metadata extraction ─────────────────────────────────────────────
US_STATES_MAP = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'district of columbia': 'DC', 'florida': 'FL', 'georgia': 'GA',
    'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
    'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME',
    'maryland': 'MD', 'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN',
    'mississippi': 'MS', 'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE',
    'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM',
    'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH',
    'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI',
    'south carolina': 'SC', 'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX',
    'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
    'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
}

STATE_ABBREV_FROM_FILENAME = {
    'cali': 'CA', 'dela': 'DE', 'dist': 'DC', 'idah': 'ID', 'newm': 'NM',
    'conn': 'CT', 'flor': 'FL', 'minn': 'MN', 'mich': 'MI', 'ohio': 'OH',
    'penn': 'PA', 'illin': 'IL', 'india': 'IN', 'iowa': 'IA', 'kans': 'KS',
    'kent': 'KY', 'loui': 'LA', 'mary': 'MD', 'mass': 'MA', 'miss': 'MS',
    'miso': 'MO', 'nebr': 'NE', 'newj': 'NJ', 'newy': 'NY', 'nort': 'NC',
    'okla': 'OK', 'oreg': 'OR', 'tenn': 'TN', 'texa': 'TX', 'virg': 'VA',
    'wash': 'WA', 'wisc': 'WI', 'west': 'WV', 'colo': 'CO', 'geor': 'GA',
    'main': 'ME', 'mont': 'MT', 'neva': 'NV', 'newh': 'NH', 'rhod': 'RI',
    'sout': 'SC', 'southd': 'SD', 'utah': 'UT', 'verm': 'VT', 'wyom': 'WY',
    'alas': 'AK', 'ariz': 'AZ', 'hawa': 'HI',
}

DENOM_KEYWORDS = [
    'adventist', 'advent christian', 'seventh-day adventist', 'seventh day adventist',
    'assemblies of god', 'assembly of god',
    'baptist', 'southern baptist', 'national baptist', 'primitive baptist',
    'free will baptist', 'missionary baptist', 'regular baptist', 'colored baptist',
    'catholic', 'roman catholic',
    'christian', 'disciples of christ', 'church of christ',
    'congregational', 'congregational christian',
    'episcopal', 'protestant episcopal', 'methodist episcopal',
    'evangelical', 'evangelical and reformed', 'evangelical lutheran',
    'evangelical united brethren', 'evangelical association',
    'lutheran', 'augustana', 'united lutheran', 'american lutheran',
    'methodist', 'african methodist episcopal', 'ame', 'ame zion', 'cme',
    'colored methodist episcopal', 'united methodist', 'free methodist',
    'wesleyan methodist', 'methodist protestant',
    'mormon', 'latter-day saints', 'latter day saints', 'lds', 'reorganized',
    'nazarene', 'church of the nazarene',
    'pentecostal', 'pentecostal holiness', 'pentecostal assemblies',
    'church of god', 'church of god in christ',
    'presbyterian', 'united presbyterian', 'cumberland presbyterian',
    'reformed', 'dutch reformed', 'reformed church', 'reformed presbyterian',
    'salvation army',
    'unitarian', 'universalist',
    'united brethren', 'church of the united brethren', 'evangelical united brethren',
    'friends', 'quaker',
    'menonnite', 'mennonite', 'amish',
    'moravian',
    'jewish', 'synagogue', 'hebrew',
    'greek orthodox', 'russian orthodox', 'eastern orthodox',
    'christian science',
    'jehovah', "jehovah's witnesses", 'jehovahs witnesses',
    'spiritualist',
    'holiness', 'pilgrim holiness',
    'brethren', 'church of the brethren', 'dunkard',
    'united church of christ', 'evangelical protestant',
    'swedenborgian', 'new jerusalem',
    'divine science', 'unity', 'new thought',
]

def detect_state(filename, text_first_1000):
    """Detect state from filename or content."""
    fname = filename.lower()
    for key, abbr in STATE_ABBREV_FROM_FILENAME.items():
        if key in fname:
            return abbr
    text_lower = text_first_1000.lower()
    for state_name, abbr in US_STATES_MAP.items():
        if state_name in text_lower[:500]:
            return abbr
    return None

def detect_denomination(text):
    """Detect primary denomination from text."""
    text_lower = text.lower()
    for denom in DENOM_KEYWORDS:
        if denom in text_lower:
            return denom.title()
    return None

def detect_volume_type(filename, text):
    """Classify as directory or inventory."""
    if 'directory' in filename.lower():
        return 'directory'
    if 'inventory' in filename.lower():
        return 'inventory'
    text_lower = text[:2000].lower()
    if 'directory of churches' in text_lower:
        return 'directory'
    if 'inventory of the church archives' in text_lower:
        return 'inventory'
    return 'other'

# ── OCR helpers ─────────────────────────────────────────────────────
def extract_ocr_text(filepath):
    """Extract OCR from IA djvu.txt HTML wrapper. Returns list of lines."""
    text = filepath.read_text(encoding='utf-8', errors='replace')
    pre_match = re.search(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL)
    if not pre_match:
        return [], {}
    
    ocr = pre_match.group(1)
    ocr = ocr.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    lines = ocr.split('\n')
    
    # Extract metadata from HTML
    metadata = {}
    title_match = re.search(r'<title>(.*?)</title>', text, re.DOTALL)
    if title_match:
        metadata['ia_title'] = title_match.group(1).strip()[:300]
    
    return [l.rstrip() for l in lines], metadata

def split_into_pages(lines):
    """Split OCR lines into pages based on page markers."""
    pages = []
    current_page = []
    current_header = ''
    
    for line in lines:
        # Detect page markers (various IA formats)
        if re.match(r'^\s*\d+\s*$', line.strip()) and len(current_page) > 5:
            # Possible page number
            pass
        # IA often has page separators
        if re.match(r'^\-{10,}$', line.strip()) or re.match(r'^_{10,}$', line.strip()):
            if current_page:
                pages.append((current_header, current_page))
                current_page = []
                current_header = ''
            continue
        
        stripped = line.strip()
        if stripped:
            current_page.append(line)
            # First few lines of a page are often the header
            if len(current_page) <= 3:
                current_header += ' ' + stripped
    
    if current_page:
        pages.append((current_header, current_page))
    
    return pages

# ── Record extraction ───────────────────────────────────────────────
CHURCH_INDICATORS = [
    'church', 'chapel', 'temple', 'synagogue', 'mosque', 'cathedral',
    'mission', 'tabernacle', 'assembly', 'fellowship', 'congregation',
    'parish', 'baptist', 'methodist', 'presbyterian', 'lutheran',
    'catholic', 'episcopal', 'adventist', 'pentecostal', 'nazarene',
    'holiness', 'reformed', 'mennonite', 'brethren', 'christian',
    'gospel', 'evangelical', 'union church', 'bethel', 'calvary',
    'zion', 'ebenezer', 'emmanuel', 'immanuel', 'trinity',
    'grace church', 'faith church', 'hope church',
    'st. ', 'saint ', 'first church', 'first baptist', 'first methodist',
    'mt. ', 'mount ', 'new hope', 'new life', 'new bethel',
    'pleasant hill', 'shiloh', 'mt zion', 'mount zion',
    'mt olive', 'mount olive', 'antioch', 'bethlehem',
    'salem', 'pisgah', 'moriah', 'carmel', 'lebanon', 'hermon',
    'bethesda', 'sharon', 'olivet', 'macedonia', 'beulah',
    'rehoboth', 'kingdom hall', 'meeting house', 'gurdwara',
    'church of christ', 'church of god', 'house of prayer',
    'gospel hall', 'gospel tabernacle', 'bible church',
    'community church', 'free church',
]

def is_church_line(line):
    """Check if a line likely contains a church reference."""
    clean = line.strip().lower()
    if len(clean) < 8 or len(clean) > 200:
        return False
    # Skip table of contents, index, etc.
    skip_words = ['page', 'table of', 'preface', 'foreword', 'chapter',
                  'index of', 'bibliography', 'appendix', 'introduction',
                  'survey of', 'works progress', 'project number',
                  'sponsored by', 'prepared by', 'published by',
                  'copyright', 'all rights', 'printed in']
    if any(w in clean for w in skip_words):
        return False
    
    for indicator in CHURCH_INDICATORS:
        if indicator in clean:
            return True
    return False

def extract_records_from_line(line, line_num, state, denomination, volume_id, page_num):
    """Try to extract structured data from an OCR line."""
    records = []
    clean = line.strip()
    
    # Skip very noisy lines (>60% non-alphanumeric)
    alpha_ratio = sum(c.isalpha() or c.isspace() for c in clean) / max(len(clean), 1)
    if alpha_ratio < 0.5:
        return records
    
    # Pattern 1: "Church Name, Town, County" or "Church Name (Address) Town"
    # Pattern 2: "Church Name  Town  County" (tab-separated in original)
    
    name = clean
    city = ''
    county = ''
    address = ''
    
    # Try to split on multiple spaces (indicating columns)
    parts = re.split(r'\s{3,}', clean)
    if len(parts) >= 2:
        name = parts[0].strip()
        city = parts[1].strip() if len(parts) > 1 else ''
        county = parts[-1].strip() if len(parts) > 2 else ''
    
    # Clean OCR artifacts from name
    name = re.sub(r'[|{}[\]~`@#$%^*+=/\\]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    if len(name) < 4:
        return records
    
    # Extract address patterns from name
    addr_match = re.search(r'\(([^)]+)\)', name)
    if addr_match:
        address = addr_match.group(1)
        name = name.replace(f'({address})', '').strip()
    
    # Try to extract pastor name
    pastor = ''
    pastor_match = re.search(r'(?:Pastor|Rev\.?|Rev\.?|Minister|Elder)\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s*[A-Z][a-z]+)', clean)
    if pastor_match:
        pastor = pastor_match.group(0)
    
    # Try to extract membership numbers
    membership = None
    mem_match = re.search(r'(?:members?|membership|communicants?)\s*:?\s*(\d[\d,]*)', clean, re.IGNORECASE)
    if mem_match:
        try:
            membership = int(mem_match.group(1).replace(',', ''))
        except:
            pass
    
    # Race/ethnicity labels (WPA era notation)
    race = ''
    if re.search(r'\b(?:colored|negro|african)\b', clean, re.IGNORECASE):
        race = 'Black'
    elif re.search(r'\b(?:white)\s+(?:church|congregation|baptist|methodist)\b', clean, re.IGNORECASE):
        race = 'White'
    elif re.search(r'\b(?:german|swedish|norwegian|danish|finnish|italian|polish|french|spanish|hungarian|slovak|czech|dutch|russian|greek)\b', clean, re.IGNORECASE):
        match = re.search(r'\b(german|swedish|norwegian|danish|finnish|italian|polish|french|spanish|hungarian|slovak|czech|dutch|russian|greek)\b', clean, re.IGNORECASE)
        race = match.group(1).title()
    
    # Build confidence
    confidence = 0.5
    if city and county:
        confidence = 0.7
    if denomination:
        confidence += 0.1
    if city and county and denomination:
        confidence = 0.85
    
    records.append({
        'volume_id': volume_id,
        'page_num': page_num,
        'line_num': line_num,
        'raw_text': clean[:500],
        'church_name': name[:200],
        'address_text': address[:200],
        'city': city[:100],
        'county': county[:100],
        'state': state or '',
        'denomination': denomination or '',
        'pastor_name': pastor[:100],
        'race_label': race,
        'membership_count': membership,
        'year_built': None,
        'notes': '',
        'confidence': min(confidence, 1.0),
        'source_context': '',
    })
    
    return records

# ── RECORD IMPORT BATCH ─────────────────────────────────────────────
RECORD_COLS = [
    'volume_id', 'page_num', 'line_num', 'raw_text', 'church_name',
    'address_text', 'city', 'county', 'state', 'denomination',
    'pastor_name', 'race_label', 'membership_count', 'year_built',
    'notes', 'confidence', 'source_context',
]

# ── Main pipeline ───────────────────────────────────────────────────
def main():
    db = sqlite3.connect(WPA_DB)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=NORMAL')
    create_schema(db)
    
    files = sorted(WPA_DIR.glob('*.txt'))
    print(f'Building wpa.db from {len(files)} WPA volumes...\n')
    
    total_records = 0
    total_pages = 0
    
    for idx, fp in enumerate(files):
        ia_id = fp.stem
        file_size_kb = fp.stat().st_size // 1024
        
        # Extract OCR
        lines, metadata = extract_ocr_text(fp)
        if not lines or len(lines) < 20:
            print(f'  [{idx+1:3d}/{len(files)}] SKIP {fp.name[:50]:50s} (no OCR)')
            continue
        
        # Metadata
        title = metadata.get('ia_title', fp.name)
        state = detect_state(fp.name, '\n'.join(lines[:20]))
        volume_type = detect_volume_type(fp.name, '\n'.join(lines[:50]))
        denomination = detect_denomination('\n'.join(lines[:200])) if volume_type == 'inventory' else None
        year_match = re.search(r'(193[0-9]|194[0-2])', '\n'.join(lines[:100]))
        year = int(year_match.group(1)) if year_match else None
        
        # Split into pages
        pages = split_into_pages(lines)
        
        # Insert volume
        db.execute(
            '''INSERT OR REPLACE INTO wpa_volumes 
               (ia_id, title, state, volume_type, year, denomination, 
                page_count, total_lines, filename, file_size_kb, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (ia_id, title, state, volume_type, year, denomination,
             len(pages), len(lines), fp.name, file_size_kb,
             json.dumps(metadata)[:2000])
        )
        volume_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Process pages and extract records
        vol_records = 0
        vol_pages = 0
        record_batch = []
        
        for page_idx, (header, page_lines) in enumerate(pages):
            if len(page_lines) < 3:
                continue
            
            page_text = '\n'.join(page_lines)
            has_churches = 1 if any(is_church_line(l) for l in page_lines) else 0
            
            db.execute(
                '''INSERT INTO wpa_pages (volume_id, page_num, header_text, raw_text, line_count, has_church_entries)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (volume_id, page_idx + 1, header[:200], page_text[:10000], len(page_lines), has_churches)
            )
            vol_pages += 1
            
            if not has_churches:
                continue
            
            # Extract records from this page
            for line_num, line in enumerate(page_lines):
                if not is_church_line(line):
                    continue
                
                recs = extract_records_from_line(line, line_num, state, denomination, volume_id, page_idx + 1)
                for r in recs:
                    record_batch.append(tuple(r[c] for c in RECORD_COLS))
                    vol_records += 1
                    
                    if len(record_batch) >= 500:
                        placeholders = ', '.join(['?'] * len(RECORD_COLS))
                        db.executemany(
                            f'INSERT INTO wpa_records ({", ".join(RECORD_COLS)}) VALUES ({placeholders})',
                            record_batch
                        )
                        record_batch = []
        
        # Flush remaining
        if record_batch:
            placeholders = ', '.join(['?'] * len(RECORD_COLS))
            db.executemany(
                f'INSERT INTO wpa_records ({", ".join(RECORD_COLS)}) VALUES ({placeholders})',
                record_batch
            )
        
        # Update volume record count
        db.execute('UPDATE wpa_volumes SET record_count=? WHERE id=?', (vol_records, volume_id))
        db.commit()
        
        total_records += vol_records
        total_pages += vol_pages
        
        state_str = f' [{state}]' if state else ''
        denom_str = f' {denomination[:20]}' if denomination else ''
        print(f'  [{idx+1:3d}/{len(files)}] {fp.name[:40]:40s}{state_str:5s}{denom_str:22s} {vol_pages:>4d}p  {vol_records:>6,d} records  (total: {total_records:,})')
    
    # Populate locations table
    print(f'\nBuilding location index...')
    db.execute('''
        INSERT OR IGNORE INTO wpa_locations (city, county, state)
        SELECT DISTINCT city, county, state FROM wpa_records
        WHERE city != '' AND state != ''
    ''')
    db.execute('''
        UPDATE wpa_locations SET record_count = (
            SELECT COUNT(*) FROM wpa_records 
            WHERE wpa_records.city = wpa_locations.city 
            AND wpa_records.state = wpa_locations.state
        )
    ''')
    db.commit()
    
    # Stats
    vol_count = db.execute('SELECT COUNT(*) FROM wpa_volumes').fetchone()[0]
    rec_count = db.execute('SELECT COUNT(*) FROM wpa_records').fetchone()[0]
    page_count = db.execute('SELECT COUNT(*) FROM wpa_pages').fetchone()[0]
    loc_count = db.execute('SELECT COUNT(*) FROM wpa_locations').fetchone()[0]
    size_mb = os.path.getsize(WPA_DB) / (1024*1024)
    
    # State breakdown
    print(f'\n{"="*60}')
    print(f'WPA Database Complete')
    print(f'  Volumes:  {vol_count}')
    print(f'  Pages:    {page_count:,}')
    print(f'  Records:  {rec_count:,}')
    print(f'  Locations:{loc_count:,}')
    print(f'  Size:     {size_mb:.1f} MB')
    
    print(f'\nRecords by state:')
    for state, count in db.execute(
        "SELECT state, COUNT(*) FROM wpa_records WHERE state != '' GROUP BY state ORDER BY COUNT(*) DESC"
    ).fetchall():
        print(f'  {state}: {count:>8,}')
    
    print(f'\nRecords by denomination (top 15):')
    for denom, count in db.execute(
        "SELECT denomination, COUNT(*) FROM wpa_records WHERE denomination != '' GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 15"
    ).fetchall():
        print(f'  {denom[:40]:40s} {count:>8,}')
    
    db.close()
    print(f'\nDone. wpa.db ready at {WPA_DB}')

if __name__ == '__main__':
    main()
