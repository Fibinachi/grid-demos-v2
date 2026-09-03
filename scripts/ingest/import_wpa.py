"""
WPA Historical Records Survey — Church Directory Importer
Imports all 96 WPA volumes: 12 state/county directories + 84 denomination inventories.
Source: Internet Archive, OCR via djvu.txt (~85-90% accurate), 1939-1942.

Strategy per format:
  directory: Tabular — church name, address, town, county columns. Parse column alignment.
  inventory: Denomination sections with CHURCH NAME/TOWN/COUNTY sub-columns.
             Extract church-denomination-location triples.
"""
import sqlite3, re, os, sys
from pathlib import Path
from collections import defaultdict

WPA_DIR = Path('E:/grid/data/wpa')
DB_PATH = 'E:/grid/churches.db'

# ── File classification ──────────────────────────────────────────────
def classify_file(filepath):
    """Determine if file is directory-format or inventory-format."""
    name = filepath.name.lower()
    if 'directory' in name:
        return 'directory'
    if 'inventory' in name:
        return 'inventory'
    # Check content for directory markers
    text = filepath.read_text(encoding='utf-8', errors='replace')[:5000]
    if 'directory of churches' in text.lower():
        return 'directory'
    if 'inventory of the church archives' in text.lower():
        return 'inventory'
    return 'unknown'

# ── OCR extraction ───────────────────────────────────────────────────
def extract_ocr(filepath):
    """Extract OCR text from IA djvu.txt HTML wrapper."""
    text = filepath.read_text(encoding='utf-8', errors='replace')
    pre_match = re.search(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL)
    if not pre_match:
        return ''
    ocr = pre_match.group(1)
    ocr = ocr.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    return ocr

# ── State/county detection ──────────────────────────────────────────
US_STATES = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'district of columbia': 'DC', 'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI',
    'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
    'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
    'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
    'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI',
    'south carolina': 'SC', 'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX',
    'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
    'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
}

def detect_state(filename, text):
    """Try to identify which state this WPA volume covers."""
    fname = filename.lower()
    text_lower = text[:3000].lower()
    # Check filename for state abbreviations
    state_abbrev_map = {
        'cali': 'CA', 'dela': 'DE', 'dist': 'DC', 'idah': 'ID', 'newm': 'NM',
        'unse': 'US', 'conn': 'CT', 'flor': 'FL', 'vari': 'US',
        'arkansas': 'AR', 'california': 'CA', 'delaware': 'DE',
        'idaho': 'ID', 'new mexico': 'NM', 'florida': 'FL',
        'connecticut': 'CT', 'minnesota': 'MN', 'michigan': 'MI',
        'new york': 'NY', 'pennsylvania': 'PA', 'ohio': 'OH',
        'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
        'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA',
        'maryland': 'MD', 'massachusetts': 'MA', 'missouri': 'MO',
        'nebraska': 'NE', 'new jersey': 'NJ', 'north carolina': 'NC',
        'oklahoma': 'OK', 'oregon': 'OR', 'tennessee': 'TN',
        'texas': 'TX', 'virginia': 'VA', 'washington': 'WA',
        'wisconsin': 'WI', 'west virginia': 'WV', 'colorado': 'CO',
        'georgia': 'GA', 'maine': 'ME', 'mississippi': 'MS',
        'montana': 'MT', 'nevada': 'NV', 'new hampshire': 'NH',
        'north dakota': 'ND', 'rhode island': 'RI',
        'south carolina': 'SC', 'south dakota': 'SD', 'utah': 'UT',
        'vermont': 'VT', 'wyoming': 'WY',
    }
    for key, abbr in state_abbrev_map.items():
        if key in fname:
            return abbr
    # Check content for state name
    for state_name, abbr in US_STATES.items():
        if state_name in text_lower[:500]:
            return abbr
    return None

# ── Denomination detection ──────────────────────────────────────────
# Common denominational keywords from WPA era
DENOM_KEYWORDS = [
    'adventist', 'advent christian', 'seventh-day adventist',
    'assemblies of god', 'assembly of god',
    'baptist', 'southern baptist', 'national baptist', 'primitive baptist',
    'free will baptist', 'missionary baptist', 'regular baptist',
    'catholic', 'roman catholic',
    'christian', 'disciples of christ', 'church of christ',
    'congregational', 'congregational christian',
    'episcopal', 'protestant episcopal',
    'evangelical', 'evangelical and reformed', 'evangelical lutheran',
    'evangelical united brethren',
    'lutheran', 'augustana', 'united lutheran', 'american lutheran',
    'methodist', 'methodist episcopal', 'african methodist episcopal',
    'ame', 'ame zion', 'cme', 'colored methodist episcopal',
    'united methodist', 'free methodist', 'wesleyan methodist',
    'mormon', 'latter-day saints', 'lds', 'reorganized',
    'nazarene', 'church of the nazarene',
    'pentecostal', 'pentecostal holiness', 'pentecostal assemblies',
    'church of god', 'church of god in christ',
    'presbyterian', 'united presbyterian', 'cumberland presbyterian',
    'reformed', 'dutch reformed', 'reformed church',
    'salvation army',
    'unitarian', 'universalist',
    'united brethren', 'church of the united brethren',
    'friends', 'quaker',
    'menonnite', 'amish',
    'moravian',
    'jewish', 'synagogue', 'hebrew',
    'greek orthodox', 'russian orthodox', 'eastern orthodox',
    'christian science',
    'jehovah', "jehovah's witnesses",
    'spiritualist',
    'holiness',
]

def detect_denom_from_header(header_text):
    """Match a section header to a denomination."""
    header_lower = header_text.lower().strip()
    # Remove OCR artifacts
    header_lower = re.sub(r'[^a-z\s]', '', header_lower).strip()
    for denom in DENOM_KEYWORDS:
        if denom in header_lower:
            return denom.title()
    return None

# ── Directory format parser ─────────────────────────────────────────
def parse_directory_format(ocr_text, state, filename):
    """
    Parse tabular directory format.
    These have 3-4 columns: Church Name | Address | Town | County
    """
    records = []
    lines = [l.strip() for l in ocr_text.split('\n') if l.strip()]
    
    # Skip header/frontmatter — look for the first data section
    # Directory format typically has headers like "CHURCH", "ADDRESS", "TOWN", "COUNTY"
    in_data = False
    current_town = ''
    current_county = ''
    
    for i, line in enumerate(lines):
        # Skip very noisy lines
        if len(line) < 3:
            continue
        # Detect column headers
        if re.match(r'^(CHURCH|NAME|ADDRESS|TOWN|COUNTY|CITY|LOCATION)\b', line, re.IGNORECASE):
            in_data = True
            continue
        if not in_data:
            continue
        
        # Try to parse as: Name, Address, Town, County
        # Directory format often has commas or multiple spaces as delimiters
        parts = re.split(r'\s{2,}|\t|,\s*', line)
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) >= 2 and len(parts[0]) > 2:
            name = parts[0]
            # Clean OCR noise from name
            name = re.sub(r'[^\w\s.\-()\'"&]', '', name).strip()
            if len(name) < 3:
                continue
            
            town = ''
            county_str = ''
            address = ''
            
            if len(parts) >= 3:
                town = parts[1] if len(parts[1]) > 2 else parts[2] if len(parts) > 2 else ''
                county_str = parts[-1] if len(parts[-1]) > 2 else ''
            elif len(parts) == 2:
                town = parts[1]
            
            # Clean town/county
            town = re.sub(r'[^\w\s.\-]', '', town).strip()
            county_str = re.sub(r'[^\w\s.\-]', '', county_str).strip()
            
            records.append({
                'name': name,
                'address': address,
                'city': town,
                'county': county_str,
                'state': state or '',
                'denomination': '',
                'source_file': filename,
            })
    
    return records

# ── Inventory format parser ─────────────────────────────────────────
def parse_inventory_format(ocr_text, state, filename):
    """
    Parse inventory format: denomination sections with CHURCH NAME/TOWN/COUNTY columns.
    Multi-column layout where columns appear sequentially, not side-by-side.
    """
    records = []
    lines = [l.strip() for l in ocr_text.split('\n') if l.strip()]
    
    current_denom = None
    in_church_col = False
    in_town_col = False
    in_county_col = False
    churches = []
    towns = []
    counties = []
    
    for i, line in enumerate(lines):
        upper = line.upper().strip()
        
        # Detect denomination headers (all-caps, 3-40 chars, preceded by blank-ish context)
        is_section_header = (
            len(line) > 3 and len(line) < 60 and
            line == line.upper() and
            not line.startswith('PAGE') and
            not line.startswith('TABLE') and
            not line.startswith('FOREWORD') and
            not line.startswith('PREFACE') and
            not line.startswith('INTRODUCTION') and
            not any(w in upper for w in ['SURVEY', 'PROJECT', 'WORKS', 'RECORDS',
                   'ARKANSAS', 'DIRECTORY', 'HISTORICAL', 'ADMINISTRATION',
                   'PROGRESS', 'BIBLIOGRAPHY', 'INDEX', 'APPENDIX', 'CHAPTER',
                   'SECTION', 'DISTRICT', 'CONFERENCE', 'NOTE', 'SERVICE',
                   'STATE OF', 'COUNTY', 'TOWN', 'CITY OF'])
        )
        
        if is_section_header and i > 10:
            denom = detect_denom_from_header(line)
            if denom:
                # Flush previous section
                if churches:
                    records.extend(align_columns(churches, towns, counties, current_denom, state, filename))
                current_denom = denom
                churches, towns, counties = [], [], []
                in_church_col = in_town_col = in_county_col = False
                continue
        
        # Detect column headers
        if re.match(r'^(CHURCH\s*NAME|CHURCH|NAME\s*OF\s*CHURCH)\b', upper):
            in_church_col = True
            in_town_col = in_county_col = False
            continue
        elif re.match(r'^(TOWN|CITY|POST\s*OFFICE|LOCATION)\b', upper):
            in_town_col = True
            in_church_col = in_county_col = False
            continue
        elif re.match(r'^(COUNTY|COUNTY\s*NAME)\b', upper):
            in_county_col = True
            in_church_col = in_town_col = False
            continue
        
        # Collect data
        if in_church_col and len(line) > 3:
            name = re.sub(r'[^\w\s.\-()\'"&]', '', line).strip()
            if len(name) > 2 and not name.startswith('('):
                churches.append(name)
        elif in_town_col and len(line) > 2:
            town = re.sub(r'[^\w\s.\-]', '', line).strip()
            if len(town) > 1 and not town.startswith('~'):
                towns.append(town)
        elif in_county_col and len(line) > 2:
            county = re.sub(r'[^\w\s.\-]', '', line).strip()
            if len(county) > 2 and not county.startswith('-'):
                counties.append(county)
    
    # Flush last section
    if churches:
        records.extend(align_columns(churches, towns, counties, current_denom, state, filename))
    
    return records

def align_columns(churches, towns, counties, denomination, state, filename):
    """Align the three columns by index position."""
    records = []
    max_len = max(len(churches), len(towns), len(counties))
    for j in range(max_len):
        name = churches[j] if j < len(churches) else ''
        town = towns[j] if j < len(towns) else ''
        county = counties[j] if j < len(counties) else ''
        if name and len(name) > 2:
            records.append({
                'name': name,
                'address': '',
                'city': town,
                'county': county,
                'state': state or '',
                'denomination': denomination or '',
                'source_file': filename,
            })
    return records

# ── Simple line-by-line fallback parser ─────────────────────────────
def parse_fallback(ocr_text, state, filename):
    """Fallback: extract any line that looks like a church name with location."""
    records = []
    lines = ocr_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if len(line) < 10 or len(line) > 200:
            continue
        # Look for patterns like "Name, Town" or "Name (Address) Town County"
        # Clean OCR noise
        clean = re.sub(r'[|{}[\]~`@#$%^*+=/\\<>]', ' ', line)
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        # Skip obvious non-church lines
        skip_words = ['page', 'table', 'preface', 'foreword', 'chapter', 'index',
                      'bibliography', 'appendix', 'introduction', 'survey of',
                      'works progress', 'historical records', 'project number',
                      'sponsored by', 'supervisor', 'director', 'secretary',
                      'commissioner', 'prepared by', 'published by']
        if any(w in clean.lower() for w in skip_words):
            continue
        
        words = clean.split()
        if len(words) < 3:
            continue
        
        # Try to extract: church name has key denominational terms
        has_denom = any(d in clean.lower() for d in ['church', 'chapel', 'temple',
                        'synagogue', 'mosque', 'cathedral', 'mission', 'tabernacle',
                        'assembly', 'fellowship', 'congregation', 'parish',
                        'baptist', 'methodist', 'presbyterian', 'lutheran',
                        'catholic', 'episcopal', 'adventist', 'pentecostal',
                        'nazarene', 'holiness', 'reformed', 'congregational',
                        'mennonite', 'brethren', 'christian', 'gospel',
                        'evangelical', 'union', 'bethel', 'calvary', 'zion',
                        'ebenezer', 'emmanuel', 'immanuel', 'trinity', 'grace',
                        'faith', 'hope', 'charity', 'st. ', 'saint ', 'first ',
                        'second ', 'third ', 'mt. ', 'mount ', 'new hope',
                        'new life', 'new bethel', 'pleasant', 'shiloh',
                        'mt zion', 'mount zion', 'mt olive', 'mount olive',
                        'antioch', 'bethlehem', 'salem', 'pisgah', 'moriah',
                        'carmel', 'lebanon', 'hermon', 'tabernacle',
                        'bethesda', 'sharon', 'olivet', 'macedonia',
                        'beulah', 'rehoboth', 'hesperia'])
        
        if has_denom and len(clean) > 15:
            records.append({
                'name': clean[:200],
                'address': '',
                'city': '',
                'county': '',
                'state': state or '',
                'denomination': '',
                'source_file': filename,
            })
    
    return records

# ── Deduplication ────────────────────────────────────────────────────
def deduplicate(records):
    """Remove obvious duplicates within the same file."""
    seen = set()
    unique = []
    for r in records:
        key = (r['name'].lower().strip(), r['city'].lower().strip(), r['state'])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique

# ── Main import pipeline ────────────────────────────────────────────
def main():
    db = sqlite3.connect(DB_PATH)
    
    # Get max id for new records
    max_id = db.execute('SELECT MAX(id) FROM churches').fetchone()[0] or 5000000
    next_id = max_id + 1
    
    files = sorted(WPA_DIR.glob('*.txt'))
    print(f'Processing {len(files)} WPA files...\n')
    
    all_records = []
    stats = {'directory': 0, 'inventory': 0, 'fallback': 0, 'unknown': 0}
    file_counts = {}
    
    for i, fp in enumerate(files):
        ftype = classify_file(fp)
        state = detect_state(fp.name, fp.read_text(encoding='utf-8', errors='replace')[:2000])
        ocr = extract_ocr(fp)
        
        if not ocr or len(ocr) < 100:
            continue
        
        if ftype == 'directory':
            records = parse_directory_format(ocr, state, fp.name)
            records += parse_fallback(ocr, state, fp.name)
        elif ftype == 'inventory':
            records = parse_inventory_format(ocr, state, fp.name)
            if len(records) < 5:
                records += parse_fallback(ocr, state, fp.name)
        else:
            records = parse_fallback(ocr, state, fp.name)
            # Try inventory format too
            inv_records = parse_inventory_format(ocr, state, fp.name)
            if len(inv_records) > len(records):
                records = inv_records
        
        records = deduplicate(records)
        file_counts[fp.name] = len(records)
        all_records.extend(records)
        stats[ftype] += len(records)
        
        if (i + 1) % 10 == 0:
            print(f'  [{i+1}/{len(files)}] {fp.name[:50]:50s} → {len(records):>5} records  (total: {len(all_records):,})')
    
    print(f'\n{"="*60}')
    print(f'Total raw records: {len(all_records):,}')
    print(f'  Directory: {stats["directory"]:,}')
    print(f'  Inventory: {stats["inventory"]:,}')
    print(f'  Fallback:  {stats["fallback"]:,}')
    
    # Deduplicate globally
    all_records = deduplicate(all_records)
    print(f'After global dedup: {len(all_records):,}')
    
    # Top files by record count
    print(f'\nTop 10 files by records:')
    for fname, count in sorted(file_counts.items(), key=lambda x: -x[1])[:10]:
        print(f'  {fname[:60]:60s} {count:>6}')
    
    # ── Import into churches.db ─────────────────────────────────────
    print(f'\n{"="*60}')
    print('Importing into churches.db...')
    
    source = 'wpa_historical_records_survey'
    
    imported = 0
    batch = []
    for r in all_records:
        rid = next_id
        next_id += 1
        batch.append((
            rid, r['name'], r['address'], r['city'], r['state'],
            r['county'], source, 'church', r['denomination'],
            r.get('source_file', ''),
        ))
        if len(batch) >= 500:
            db.executemany(
                '''INSERT INTO churches (id, name, address, city, state, county, source, 
                   landmark_type, tradition, notes) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                batch
            )
            db.commit()
            imported += len(batch)
            print(f'  Imported: {imported:,}', end='\r')
            batch = []
    
    if batch:
        db.executemany(
            '''INSERT INTO churches (id, name, address, city, state, county, source, 
               landmark_type, tradition, notes) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            batch
        )
        db.commit()
        imported += len(batch)
    
    # Log provenance
    db.execute(
        "INSERT INTO provenance_log (source, description, row_count) VALUES (?, ?, ?)",
        (source, f'WPA Historical Records Survey import: {len(files)} volumes, {imported} churches (1939-1942)', imported)
    )
    db.commit()
    
    final_count = db.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
    db.close()
    
    print(f'\n{"="*60}')
    print(f'IMPORT COMPLETE')
    print(f'  Files processed: {len(files)}')
    print(f'  Records extracted: {len(all_records):,}')
    print(f'  Imported: {imported:,}')
    print(f'  Final DB count: {final_count:,}')

if __name__ == '__main__':
    main()
