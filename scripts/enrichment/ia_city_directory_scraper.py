"""
ia_city_directory_scraper.py
=============================
Extract church listings from city directories on Internet Archive (1960-1980)
and match against GRID for ground truth.

Pipeline:
  1. Search IA API for city directories
  2. Download DJVU OCR text
  3. Extract "CHURCHES AND SYNAGOGUES" section (block-based parser)
  4. Parse individual church entries (name + address + denomination)
  5. Match against GRID by city + normalized name similarity
  6. Store in city_directory_churches table

Usage:
  python ia_city_directory_scraper.py              # Full run
  python ia_city_directory_scraper.py --dry-run 3  # Test with 3 directories
  python ia_city_directory_scraper.py --limit 10   # Process 10 directories
"""

import json, os, re, sys, time, sqlite3
from difflib import SequenceMatcher
from datetime import datetime, timezone

import requests

# ── Config ──────────────────────────────────────────────────────────
DB = 'e:/grid/churches.db'
DATA_DIR = 'e:/grid/data/directories/city'
os.makedirs(DATA_DIR, exist_ok=True)

IA_SEARCH_URL = 'https://archive.org/advancedsearch.php'
IA_DOWNLOAD_TMPL = 'https://archive.org/download/{0}/{0}_djvu.txt'

YEAR_RANGE = (1960, 1980)
MAX_RESULTS = 500
REQUEST_DELAY = 1.0

# State abbreviation normalization
STATE_MAP = {'N.C.': 'NC', 'S.C.': 'SC', 'Va.': 'VA', 'Calif.': 'CA',
             'Mass.': 'MA', 'Mich.': 'MI', 'Ill.': 'IL', 'Fla.': 'FL',
             'Tex.': 'TX', 'Ohio': 'OH', 'Ont.': 'ON', 'Ontario': 'ON',
             'Ga.': 'GA', 'Ala.': 'AL', 'Miss.': 'MS', 'Tenn.': 'TN',
             'Ky.': 'KY', 'Ind.': 'IN', 'Wis.': 'WI', 'Minn.': 'MN',
             'Mo.': 'MO', 'Ark.': 'AR', 'La.': 'LA', 'Okla.': 'OK',
             'Neb.': 'NE', 'Kans.': 'KS', 'Colo.': 'CO', 'Wyo.': 'WY',
             'Mont.': 'MT', 'Idaho': 'ID', 'Oreg.': 'OR', 'Wash.': 'WA',
             'Ariz.': 'AZ', 'N.M.': 'NM', 'Conn.': 'CT', 'R.I.': 'RI',
             'Vt.': 'VT', 'N.H.': 'NH', 'Me.': 'ME', 'Del.': 'DE',
             'Md.': 'MD', 'W.Va.': 'WV', 'N.J.': 'NJ', 'Pa.': 'PA',
             'N.Y.': 'NY', 'Nev.': 'NV', 'N.D.': 'ND', 'S.D.': 'SD'}

# ── Regex patterns ──────────────────────────────────────────────────
CHURCH_KW = re.compile(
    r'\b(?:church|chapel|temple|synagogue|mosque|tabernacle|ministry|'
    r'fellowship|worship|assembly|congregation|cathedral|parish|'
    r'mission\b|sanctuary|presbyterian|methodist|baptist|lutheran|'
    r'episcopal|catholic|pentecostal|holiness|nazarene|adventist|'
    r'apostolic|gospel\b|calvary|bethel|bethlehem|zion|shiloh|'
    r'ebenezer|emmanuel|trinity|grace\b|faith\b|hope\b|love\b|'
    r'first\b|redeemer|savior|christian|jesus\b|god\b|'
    r'mormon|latter.day|jehovah|house of|interdenominational|'
    r'wesleyan|freewill|foursquare|covenant|full gospel|kingdom hall|'
    r'pilgrim|new hope|new life|word of|living water|cross road|'
    r'good shepherd|holy (?:spirit|trinity|cross|family|communion)|'
    r'st\.?\s+(?:john|paul|peter|james|mark|luke|matthew|mary|joseph|'
    r'patrick|michael|andrew|thomas|philip|stephen|francis|anthony|'
    r'augustine|theresa|monica|anne|rose|cecelia|bridget|bernadette|'
    r'ignatius|dominic|xavier|basil|nicholas|george|david|martin)|'
    r'mount\s+(?:zion|calvary|olive|pisgah|hebron|pleasant|sinai|'
    r'moriah|tabor|carmel|hermon|gerald|gallant))\b',
    re.IGNORECASE
)

AD_KW = re.compile(
    r'\b(?:DRUG|WRECKER|AUTO\s+REPAIR|WELL\s+BORING|PUMP\s+SERVICE|'
    r'SALES\b|RENTAL\b|DELIVER|INSURANCE|PLUMBING|ELECTRIC|HEATING|'
    r'CLEANER|TAVERN|RESTAURANT|MOTEL|HOTEL|FLORIST|HARDWARE|'
    r'CONTRACTOR|CONSTRUCTION|EXCAVAT|PAVING|ROOFING|PAINTING|'
    r'FUNERAL\s+HOME|CEMETERY|MONUMENT|MARKET|GROCERY|PHARMACY|'
    r'LAUNDRY|DRY\s+CLEAN|PRINTING|PUBLISHING|REAL\s+ESTATE|'
    r'ATTORNEY|LAWYER|ACCOUNTANT|DENTIST|PHYSICIAN|SURGEON|CLINIC)\b',
    re.IGNORECASE
)

ADDR_PAT = re.compile(
    r'(.*?)(\d+\s+(?:[NSEW]\s+)?[A-Z][a-z]+(?:\s+(?:St|Av|Ave|Rd|Dr|Blvd|'
    r'Ln|Way|Cir|Ct|Pl|Hwy|Pkwy|Trl|Ter|Run|Row|Al|Aly|Cres|Plz|Xing|Cv|'
    r'Bnd|La))\.?)'
)

# ── IA API ──────────────────────────────────────────────────────────
def search_ia(query, rows=500):
    params = {'q': query, 'output': 'json', 'rows': rows, 'sort': 'date'}
    r = requests.get(IA_SEARCH_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json()['response']['docs']


def download_ocr(identifier):
    url = IA_DOWNLOAD_TMPL.format(identifier, identifier)
    try:
        r = requests.get(url, timeout=60)
        if r.status_code == 200 and '<html' not in r.text[:200].lower():
            return r.text
    except requests.Timeout:
        print(f'  ⚠️  Download timeout for {identifier}')
    except Exception as e:
        print(f'  ⚠️  Download error: {e}')
    return None


def extract_city_state(title):
    """Extract city and state from various IA directory title formats.
    
    Formats seen:
      - 'City (County, N.C.) city directory'
      - 'Hill's City (County, N.C.) City Directory [YEAR]'
      - 'Polk's City (County, Ind.) city directory, YEAR'
      - 'YEAR Vernon's City City Directory'
      - 'City, State City Directory, YEAR-YEAR'
      - 'Miller's City, N.C. City Directory [YEAR]'
    """
    # Format: 'City (County, ST) ...' or "Name's City (County, ST) ..."
    m = re.search(r'([A-Z][a-z]+(?:[\s-][A-Z][a-z]+)*)\s*\([^)]*,\s*([A-Z]{2}|[A-Z][a-z]+\.)\s*\)', title)
    if m:
        return m.group(1), STATE_MAP.get(m.group(2), m.group(2))
    
    # Format: 'City, ST ...' or "Name's City, ST ..."
    m = re.search(r'([A-Z][a-z]+(?:[\s-][A-Z][a-z]+)*),\s*([A-Z]{2}|[A-Z][a-z]+\.)\b', title)
    if m:
        city = m.group(1)
        st = m.group(2)
        # Filter false positives: city should not be a year or publisher
        if not city.isdigit() and city.lower() not in ('vol', 'inc', 'co'):
            return city, STATE_MAP.get(st, st)
    
    # Format: 'YEAR Vernon's City City Directory' or 'YEAR City City Directory'
    m = re.match(r'\d{4}\s+(?:Vernon.s|Polk.s|Hill.s|Might.s|Miller.s)?\s*([A-Z][a-z]+(?:[\s-][A-Z][a-z]+)*)\s+City\s+Directory', title)
    if m:
        return m.group(1), None  # State unknown from title alone
    
    return None, None


# ── Church Section Parser ────────────────────────────────────────────
def extract_churches_section(text):
    """Find the CHURCHES AND SYNAGOGUES section. Returns text slice or None."""
    m = re.search(r'CHURCHES\s+AND\s+SYNAGOGUES', text, re.IGNORECASE)
    if not m:
        for pat in [r'CHURCHES?\s+AND\s+CHARACTER', r'CHURCHES?\s*\n\s*[A-Z]{5,}']:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                break
    return text[m.start():m.start() + 80000] if m else None


def parse_church_entries(section):
    """Block-based parser: blank lines separate entries.
    Returns list of {name, address} dicts."""
    blocks, cur = [], []
    for line in section.split('\n'):
        s = line.strip()
        if not s:
            if cur:
                blocks.append(' '.join(cur))
                cur = []
            continue
        if re.match(r'^CHURCHES?\s+(AND\s+)?(SYNAGOGUES|CONTD|CIVIC)', s, re.IGNORECASE):
            continue
        if re.match(r'^\d{1,4}$', s) or re.match(r'^[IVX]+$', s):
            continue
        cur.append(s)
    if cur:
        blocks.append(' '.join(cur))

    entries = []
    for block in blocks:
        # Skip blocks that are too short/long or non-church
        if len(block) < 10 or len(block) > 150 or AD_KW.search(block) or not CHURCH_KW.search(block):
            continue
        block = re.sub(r'\s+', ' ', block).strip().replace('\u2019', "'")
        m = ADDR_PAT.search(block)
        if m:
            name = m.group(1).strip().rstrip(',').rstrip('.')
            addr = m.group(2).strip() + ' ' + block[m.end():].strip()
            addr = re.sub(r'\s+', ' ', addr).strip()
            addr = re.sub(r'\s*\([A-Z0-9\s,]+\)\s*', ' ', addr).strip()
            addr = re.sub(r'\s*(?:Tel|PO Box|P\.O\.)\s.*$', '', addr).strip()
            if not addr or len(addr) < 5:
                name = block  # Address parse failed, use full block as name
                addr = ''
        else:
            name, addr = block, ''
        name = re.sub(r'\s+', ' ', name).strip()
        if name == name.upper() and len(name) > 15:
            name = name.title()
        # Purge "CONTD" prefix from name
        name = re.sub(r'^CONTD\s+', '', name).strip()
        if not name:
            continue
        entries.append({'name': name, 'address': addr.strip()})
    return entries


def infer_denomination(name):
    """Infer denomination from church name keywords."""
    n = name.lower()
    patterns = [
        (r'\bbaptist\b', 'Baptist'), (r'\bmethodist\b', 'Methodist'),
        (r'\bpresbyterian\b', 'Presbyterian'), (r'\blutheran\b', 'Lutheran'),
        (r'\bepiscopal\b', 'Episcopal'), (r'\bcatholic\b', 'Catholic'),
        (r'\bpentecostal\b', 'Pentecostal'), (r'\bholiness\b', 'Holiness'),
        (r'\bchurch of god\b', 'Church of God'),
        (r'\bchurch of christ\b', 'Church of Christ'),
        (r'\bassembly of god\b', 'Assembly of God'),
        (r'\bnazarene\b', 'Nazarene'), (r'\badventist\b', 'Adventist'),
        (r'\bmormon|latter.day|lds\b', 'LDS'),
        (r'\bjehovah|witness\b', 'Jehovah\'s Witness'),
        (r'\bsynagogue|temple emanuel|temple israel|beth israel|beth shalom|jewish', 'Jewish'),
        (r'\bunited church of christ|ucc\b', 'UCC'),
        (r'\bunitarian\b', 'Unitarian'),
        (r'\bchristian science\b', 'Christian Science'),
        (r'\bsalvation army\b', 'Salvation Army'),
        (r'\borthodox\b', 'Orthodox'),
        (r'\bame\b|african methodist', 'AME'),
        (r'\bamez\b|ame zion', 'AME Zion'), (r'\bcme\b', 'CME'),
        (r'\bfree will baptist\b', 'Free Will Baptist'),
        (r'\bprimitive baptist\b', 'Primitive Baptist'),
        (r'\breformed\b', 'Reformed'),
        (r'\bmenonite|mennonite\b', 'Mennonite'), (r'\bbrethren\b', 'Brethren'),
        (r'\bfriend|quaker\b', 'Quaker'),
        (r'\bmuslim|mosque|islamic|masjid\b', 'Islam'),
        (r'\bbuddhist\b', 'Buddhist'), (r'\bhindu\b', 'Hindu'),
        (r'\bsikh|gurdwara\b', 'Sikh'), (r'\bbahai|bahá.í\b', 'Bahai'),
        (r'\bapostolic\b', 'Apostolic'), (r'\bfoursquare\b', 'Foursquare'),
        (r'\bwesleyan\b', 'Wesleyan'), (r'\bfull gospel\b', 'Full Gospel'),
    ]
    for pat, denom in patterns:
        if re.search(pat, n):
            return denom
    return 'Other/Unknown'


def normalize_name(name):
    name = re.sub(r'[,.;:]+$', '', name.strip())
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'\bSt\.?\s', 'Saint ', name)
    name = re.sub(r'\bMt\.?\s', 'Mount ', name)
    name = re.sub(r'^The\s+', '', name)
    return name


# ── Database ─────────────────────────────────────────────────────────
def init_db(db):
    db.execute('''CREATE TABLE IF NOT EXISTS city_directory_churches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        church_id INTEGER REFERENCES churches(id),
        directory_id TEXT NOT NULL,
        directory_title TEXT,
        directory_year INTEGER,
        directory_city TEXT,
        directory_state TEXT,
        raw_name TEXT NOT NULL,
        raw_address TEXT,
        denomination TEXT,
        matched_church_id INTEGER,
        matched_name TEXT,
        match_confidence REAL,
        match_method TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(directory_id, raw_name))''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_cdc_dir ON city_directory_churches(directory_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_cdc_match ON city_directory_churches(matched_church_id)')
    db.commit()


def match_against_grid(db, entries, city, state):
    """Match parsed entries against GRID. Preloads + pre-normalizes for speed.
    Returns list with match info added."""
    # Preload all churches in this city with pre-normalized names
    city_churches = []
    if city:
        for cid, cname in db.execute(
            'SELECT id, name FROM churches WHERE city=?', (city,)
        ):
            city_churches.append((cid, cname, normalize_name(cname).lower()))
    
    results = []
    for entry in entries:
        norm = normalize_name(entry['name']).lower()
        best_id, best_name, best_score, best_method = None, None, 0, None

        # Strategy 1: exact normalized match
        for cid, cname, cnorm in city_churches:
            if norm == cnorm:
                best_id, best_name, best_score = cid, cname, 1.0
                best_method = 'exact_norm+city'
                break

        # Strategy 2: fuzzy match against pre-normalized names
        if not best_id:
            for cid, cname, cnorm in city_churches:
                score = SequenceMatcher(None, norm, cnorm).ratio()
                if score > best_score and score >= 0.75:
                    best_score, best_id, best_name = score, cid, cname
            if best_id:
                best_method = f'fuzzy_city({best_score:.2f})'

        results.append({
            'name': entry['name'], 'address': entry['address'],
            'denomination': infer_denomination(entry['name']),
            'matched_church_id': best_id, 'matched_name': best_name,
            'match_confidence': best_score, 'match_method': best_method,
        })
    return results


# ── Main Pipeline ────────────────────────────────────────────────────
def run(dry_run=0, limit=0):
    db = sqlite3.connect(DB)
    db.execute('PRAGMA journal_mode=WAL')
    init_db(db)

    print('Searching IA for city directories (1960-1980)...')
    query = f'title:"city directory" AND year:[{YEAR_RANGE[0]} TO {YEAR_RANGE[1]}]'
    docs = search_ia(query, MAX_RESULTS)
    print(f'  {len(docs)} results')

    # Deduplicate by city/state/year
    seen, directories = set(), []
    for doc in docs:
        ident, title = doc.get('identifier', ''), doc.get('title', '')
        year = doc.get('year') or 0
        volume = doc.get('volume', '')
        yr = int(volume) if volume and volume.isdigit() else int(year) if year else 0
        city, state = extract_city_state(title)
        if not city or not state:
            continue
        key = (city, state, yr)
        if key in seen:
            continue
        seen.add(key)
        directories.append({
            'identifier': ident, 'title': title, 'year': yr,
            'city': city, 'state': state,
            'collection': ', '.join(doc.get('collection', [])[:3]),
        })

    print(f'  {len(directories)} unique city/year directories')

    # Already processed
    existing = {r[0] for r in db.execute('SELECT DISTINCT directory_id FROM city_directory_churches')}    
    # Skip known problematic directories (inflated entries, hangs matching)
    SKIP = {'polksindianapol1966unse'}  # 602 entries, may be inflated    print(f'  {len(existing)} already processed\n')

    if limit:
        directories = directories[:limit]

    total_new, total_matched, processed = 0, 0, 0
    for i, d in enumerate(directories):
        if d['identifier'] in existing or d['identifier'] in SKIP:
            continue
        if dry_run and processed >= dry_run:
            break

        print(f'[{i+1}/{len(directories)}] {d["city"]}, {d["state"]} ({d["year"]}) '
              f'— {d["identifier"]}')

        text = download_ocr(d['identifier'])
        if not text:
            print(f'  ❌ No OCR available\n')
            processed += 1; time.sleep(REQUEST_DELAY); continue

        section = extract_churches_section(text)
        if not section:
            print(f'  ⚠️  No churches section found\n')
            processed += 1; time.sleep(REQUEST_DELAY); continue

        entries = parse_church_entries(section)
        print(f'  📋 {len(entries)} church entries')

        if not entries:
            processed += 1; time.sleep(REQUEST_DELAY); continue

        if dry_run:
            # Show sample + denomination breakdown
            denoms = {}
            for e in entries:
                dnm = infer_denomination(e['name'])
                denoms[dnm] = denoms.get(dnm, 0) + 1
            for dnm, cnt in sorted(denoms.items(), key=lambda x: -x[1])[:8]:
                print(f'    {dnm}: {cnt}')
            print()
        else:
            print(f'  🔍 Matching against GRID...', end=' ', flush=True)
            try:
                matched = match_against_grid(db, entries, d['city'], d['state'])
                print(f'done')
            except Exception as ex:
                print(f'ERROR: {ex}')
                import traceback; traceback.print_exc()
                continue
            inserted = 0
            for e in matched:
                try:
                    db.execute('''INSERT OR IGNORE INTO city_directory_churches
                        (directory_id, directory_title, directory_year, directory_city,
                         directory_state, raw_name, raw_address, denomination,
                         matched_church_id, matched_name, match_confidence, match_method)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (d['identifier'], d['title'], d['year'], d['city'], d['state'],
                         e['name'], e['address'], e['denomination'],
                         e['matched_church_id'], e['matched_name'],
                         e['match_confidence'], e['match_method']))
                    if db.execute('SELECT changes()').fetchone()[0]:
                        inserted += 1
                        if e['matched_church_id']:
                            total_matched += 1
                except Exception as ex:
                    print(f'  ⚠️  DB: {ex}')
            db.commit()
            total_new += inserted
            mp = sum(1 for e in matched if e['matched_church_id']) / len(matched) * 100
            print(f'  ✅ {inserted} inserted ({mp:.0f}% matched)\n')

        processed += 1
        time.sleep(REQUEST_DELAY)

    # Summary
    stats = db.execute('''SELECT COUNT(*), COUNT(DISTINCT directory_id),
        COALESCE(SUM(CASE WHEN matched_church_id IS NOT NULL THEN 1 ELSE 0 END), 0),
        COUNT(DISTINCT directory_city)
        FROM city_directory_churches''').fetchone()

    print(f'{"="*60}')
    print(f'DONE: {processed} dirs | {total_new} churches | {total_matched} matched to GRID')
    if stats[0]:
        print(f'Table: {stats[0]:,} entries | {stats[1]} dirs | {stats[2]:,} matched | {stats[3]} cities')
    db.close()


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', type=int, default=0, help='Test N directories without DB writes')
    ap.add_argument('--limit', type=int, default=0, help='Max directories to process')
    args = ap.parse_args()
    run(dry_run=args.dry_run, limit=args.limit)
