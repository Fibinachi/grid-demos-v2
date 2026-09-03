"""
Hybrid Catholic Directory Extraction: Regex + Kilo API.

Delegates modern/machine years to existing parsers and uses Kilo API
for narrative early years (1833-1859) that regex can't handle.

Usage:
  python scripts/ingest/extract_catholic_hybrid.py --year 2021
  python scripts/ingest/extract_catholic_hybrid.py --year 1860
  python scripts/ingest/extract_catholic_hybrid.py --missing
  python scripts/ingest/extract_catholic_hybrid.py --all-narrative
"""

import json, os, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import sqlite3

DB_PATH = Path("E:/grid/data/catholic_directory.db")
DIRS = Path("E:/grid/data/directories")
DIRS_CLEAN = Path("E:/grid/data/directories_clean")
API_KEY = os.environ.get("KILO_API_KEY", "")
BASE_URL = "https://api.kilo.ai/api/gateway/chat/completions"
MODEL = "openai/gpt-4o-mini"


# ── Normalization ───────────────────────────────────────────────

def norm_diocese(name):
    if not name: return ''
    n = name.strip()
    n = re.sub(r'^(?:Archdiocese|Diocese)\s+of\s+', '', n, flags=re.IGNORECASE)
    n = re.sub(r'[\.\s,;:].*$', '', n)
    n = re.sub(r'\s+', ' ', n).strip().lower()
    n = n.replace('st.', 'saint')
    fixes = {'yincennes':'vincennes','nesqualy':'seattle','oregon city':'portland',
             'fbancisco':'francisco','pittsburgh':'pittsburg','new-york':'new york',
             'new-orleans':'new orleans','saut sainte marie':'marquette',
             'los angelos':'monterey','milwaukie':'milwaukee'}
    n = re.sub(r'[^a-z\s]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    for bad, good in fixes.items():
        if re.sub(r'[^a-z\s]', '', bad) in n: return good
    return n


def normalize_parish_name(name):
    if not name: return ''
    n = name.lower().strip()
    n = re.sub(r'\bst\.?\s+', 'saint ', n)
    n = re.sub(r'\bss\.?\s+', 'saints ', n)
    n = re.sub(r'\bmt\.?\s+', 'mount ', n)
    n = re.sub(r'[^\w\s]', '', n)
    n = re.sub(r'\bsaint\s+(\w+)s\b', r'saint \1', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


# ── Format detection ────────────────────────────────────────────

def detect_format(year, text):
    """Detect format, searching past intro/advertising pages."""
    # Get the main body of the text — skip past intro material
    # Look for diocese headings or numbered entries in the full text
    body = text
    
    # Modern numbered entries: "1—CATHEDRAL..." anywhere in text
    modern_matches = re.findall(r'^\d+[\u2014\u2013\u2012-]\s*[A-Z]', body, re.MULTILINE)
    if len(modern_matches) > 20:
        return 'modern'
    
    # Machine format: "DIOCESE OF X" followed by clergy lines
    dio_matches = re.findall(r'^(?:ARCH)?DIOCESE\s+OF\s+[A-Z]', body, re.MULTILINE)
    if len(dio_matches) > 5:
        church_count = len(re.findall(r'^.+?[\u2014\u2013\u2012-]\s*(?:Rev\.|Most|Rt\.|Very)',
                                       body[:500000], re.MULTILINE))
        if church_count > 10:
            return 'machine'
        return 'machine'  # Has enough diocese headers, go with machine parser
    
    # Also check for "CHURCHES AND CLERGY" section marker (machine format)
    if re.search(r'CHURCHES\s+AND\s+CLERGY', body):
        return 'machine'
    
    return 'narrative'


# ── Delegated parsers ──────────────────────────────────────────

def extract_modern_year(db, year):
    from scripts.ingest.build_catholic_db import parse_modern_directory
    count = parse_modern_directory(db, year)
    return count if count else 0


def extract_machine_year(db, year):
    from scripts.ingest.parse_catholic_directories import parse_file
    
    # Use cleaned files — they have OCR spellcheck applied
    src = DIRS_CLEAN / f"{year}_cleaned.txt"
    if not src.exists():
        print(f"  Cleaned source not found for {year}")
        return 0
    
    records = parse_file(str(src), year)

    inserted = 0
    for rec in records:
        dio_name = rec.get('diocese', '')
        if not dio_name:
            continue
        nd = norm_diocese(dio_name)
        cur = db.execute("SELECT id FROM catholic_dioceses WHERE norm_name=?", (nd,))
        row = cur.fetchone()
        if row:
            did = row[0]
        else:
            db.execute("INSERT INTO catholic_dioceses (name, norm_name) VALUES (?,?)", (dio_name, nd))
            did = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        parish_name = rec.get('parish', rec.get('church', '')).strip()
        city = rec.get('city', '') or ''
        priest_name = rec.get('priest_name', '').strip()
        if not priest_name or not parish_name:
            continue

        norm = normalize_parish_name(parish_name)
        cur = db.execute("SELECT id FROM catholic_parishes WHERE year=? AND norm_name=?", (year, norm))
        prow = cur.fetchone()
        if prow:
            pid = prow[0]
        else:
            db.execute("""INSERT INTO catholic_parishes
                (year, diocese_id, parish_name, original_name, norm_name, city, source_file)
                VALUES (?,?,?,?,?,?,?)""",
                (year, did, parish_name, parish_name, norm, city, f"{year}_formatted.txt"))
            pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        db.execute("""INSERT INTO catholic_clergy
            (year, parish_id, priest_name, title, religious_order, role, source_file)
            VALUES (?,?,?,?,?,?,?)""",
            (year, pid, priest_name, rec.get('title', 'Rev.'),
             rec.get('order', ''), rec.get('role', ''), f"{year}_formatted.txt"))
        inserted += 1

    db.commit()
    return inserted


# ── Kilo API for narrative years ────────────────────────────────

KILO_PROMPT = """Extract Catholic Directory data from this OCR text for {diocese}.

Return ONLY a JSON object with:
- bishop_name: the bishop's full name (e.g. "Most Rev. John Smith")
- vicar_general: name of vicar general if mentioned
- chancellor: name of chancellor if mentioned
- parishes: array of objects, each with:
  - parish_name: name of church/parish/institution
  - city: city name
  - state: 2-letter state code (omit if not clear)
  - founded_year: year founded (integer) if mentioned in parentheses
  - clergy: array of {{
      "name": "Full Name",
      "title": "Rev./Most Rev./Very Rev./Msgr.",
      "order": "S.J./O.S.B./C.SS.R. etc. or null",
      "role": "Pastor/Assistant/Chaplain etc. or null"
    }}

Include ALL parishes, churches, missions, institutions that have clergy assigned.
Omit schools, convents, hospitals unless they have clergy listed.
Omit statistics (populations, numbers of churches, etc.).
Return ONLY valid JSON, no markdown, no explanation."""


def extract_narrative_via_kilo(db, year):
    if not API_KEY:
        print(f"  \u26a0 No KILO_API_KEY set, skipping {year}")
        return 0

    src = DIRS_CLEAN / f"{year}_cleaned.txt"
    if not src.exists():
        print(f"  {year}: cleaned file not found")
        return 0

    text = src.read_text(encoding='utf-8', errors='replace')
    sections = chunk_by_diocese(text)
    print(f"  Kilo API: {len(sections)} sections to process")

    total_clergy = 0
    import httpx

    for idx, (dio_name, section_text) in enumerate(sections):
        print(f"    [{idx+1}/{len(sections)}] {dio_name[:50]}...", end=' ')

        try:
            resp = httpx.post(
                BASE_URL,
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": "You extract structured Catholic Directory data from OCR text. Return only valid JSON."},
                        {"role": "user", "content": KILO_PROMPT.format(diocese=dio_name) + "\n\n---\n" + section_text[:32000]},
                    ],
                    "temperature": 0.05,
                    "max_tokens": 4096,
                },
                timeout=120,
            )
            resp.raise_for_status()
            content = resp.json()['choices'][0]['message']['content']
            content = re.sub(r'^`(?:json)?\s*', '', content.strip())
            content = re.sub(r'\s*`$', '', content)
            data = json.loads(content)
        except Exception as e:
            print(f"\u26a0 {e}")
            time.sleep(3)
            continue

        # Diocese
        nd = norm_diocese(dio_name)
        cur = db.execute("SELECT id FROM catholic_dioceses WHERE norm_name=?", (nd,))
        row = cur.fetchone()
        if row:
            did = row[0]
        else:
            db.execute("INSERT INTO catholic_dioceses (name, norm_name) VALUES (?,?)", (dio_name, nd))
            did = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Chancery
        if data.get('bishop_name'):
            db.execute("""INSERT OR REPLACE INTO catholic_chanceries
                (diocese_id, year, bishop_name, vicar_general, chancellor)
                VALUES (?,?,?,?,?)""",
                (did, year, data.get('bishop_name'), data.get('vicar_general'), data.get('chancellor')))

        # Parishes + clergy
        section_clergy = 0
        for p in data.get('parishes', []):
            pname = p.get('parish_name', '').strip()
            if not pname or not p.get('clergy'):
                continue

            norm = normalize_parish_name(pname)
            cur = db.execute("SELECT id FROM catholic_parishes WHERE year=? AND norm_name=?", (year, norm))
            prow = cur.fetchone()
            if prow:
                pid = prow[0]
            else:
                db.execute("""INSERT INTO catholic_parishes
                    (year, diocese_id, parish_name, original_name, norm_name, city, founded_year, source_file)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (year, did, pname, pname, norm, p.get('city',''), p.get('founded_year'), src.name))
                pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            for c in p['clergy']:
                db.execute("""INSERT INTO catholic_clergy
                    (year, parish_id, priest_name, title, religious_order, role, source_file)
                    VALUES (?,?,?,?,?,?,?)""",
                    (year, pid, c.get('name',''), c.get('title','Rev.'),
                     c.get('order'), c.get('role'), src.name))
                section_clergy += 1

        total_clergy += section_clergy
        print(f"\u2705 {len(data.get('parishes',[]))} parishes, {section_clergy} clergy")
        time.sleep(3)

    db.commit()
    return total_clergy


def chunk_by_diocese(text):
    sections = []
    pat = re.compile(r'^(Archdiocese|Diocese)\s+of\s+([A-Za-z\s\-\.\']+?)(?:,\s*(?:T:|CLERGY|$|\.))?', re.IGNORECASE | re.MULTILINE)
    matches = list(pat.finditer(text))
    if len(matches) > 3:
        for i, m in enumerate(matches):
            name = m.group(0).strip()
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunk = text[start:end].strip()
            if len(chunk) > 40000:
                for sub in split_chunk(name, chunk): sections.append(sub)
            else:
                sections.append((name, chunk))
        return sections

    pat2 = re.compile(r'^(ARCH)?DIOCESE\s+OF\s+(.+?)\.?\s*$', re.IGNORECASE | re.MULTILINE)
    matches = list(pat2.finditer(text))
    if len(matches) > 3:
        for i, m in enumerate(matches):
            name = f"Diocese of {m.group(2).strip()}"
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunk = text[start:end].strip()
            if len(chunk) > 40000:
                for sub in split_chunk(name, chunk): sections.append(sub)
            else:
                sections.append((name, chunk))
        return sections

    for i in range(0, len(text), 30000):
        sections.append((f"Section {i//30000 + 1}", text[i:i+30000]))
    return sections


def split_chunk(name, text, max_size=35000):
    parts = []
    for i in range(0, len(text), max_size):
        parts.append((f"{name} (part {i//max_size + 1})", text[i:i+max_size]))
    return parts


# ── Metadata ────────────────────────────────────────────────────

def get_available_years():
    years = set()
    for p in DIRS_CLEAN.glob('*_cleaned.txt'):
        m = re.match(r'(\d{4})_cleaned\.txt', p.name)
        if m: years.add(int(m.group(1)))
    return sorted(years)


def get_processed_years(db):
    return set(row[0] for row in db.execute("SELECT DISTINCT year FROM catholic_clergy").fetchall())


# ── Schema ──────────────────────────────────────────────────────

def ensure_schema(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS catholic_dioceses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, norm_name TEXT NOT NULL,
            city TEXT, state TEXT, country TEXT DEFAULT 'US',
            UNIQUE(norm_name)
        );
        CREATE TABLE IF NOT EXISTS catholic_parishes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            diocese_id INTEGER REFERENCES catholic_dioceses(id),
            parish_name TEXT NOT NULL,
            original_name TEXT NOT NULL,
            norm_name TEXT NOT NULL,
            city TEXT, state TEXT, address TEXT, zip TEXT, phone TEXT,
            founded_year INTEGER,
            status TEXT DEFAULT 'active',
            prev_year_id INTEGER, next_year_id INTEGER,
            church_id INTEGER, source_file TEXT, source_line INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS catholic_clergy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            parish_id INTEGER REFERENCES catholic_parishes(id),
            priest_name TEXT NOT NULL,
            title TEXT, religious_order TEXT, role TEXT,
            source_file TEXT, raw_line TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_cp_year ON catholic_parishes(year);
        CREATE INDEX IF NOT EXISTS idx_cp_norm ON catholic_parishes(norm_name);
        CREATE INDEX IF NOT EXISTS idx_cc_year ON catholic_clergy(year);
        CREATE INDEX IF NOT EXISTS idx_cc_parish ON catholic_clergy(parish_id);
        CREATE INDEX IF NOT EXISTS idx_cd_norm ON catholic_dioceses(norm_name);
    """)
    db.commit()


# ── Main loop ───────────────────────────────────────────────────

def process_year(db, year, force=False):
    src = DIRS_CLEAN / f"{year}_cleaned.txt"
    if not src.exists():
        print(f"  {year}: source not found")
        return 0

    if not force and year in get_processed_years(db):
        print(f"  {year}: already processed")
        return 0

    text = src.read_text(encoding='utf-8', errors='replace')
    fmt = detect_format(year, text)

    print(f"\n{'='*60}")
    print(f"  {year} [{fmt}] ({(src.stat().st_size/1e6):.0f} MB)")

    if fmt == 'modern':
        count = extract_modern_year(db, year)
        print(f"  \u2192 {count} clergy via modern parser")
    elif fmt == 'machine':
        count = extract_machine_year(db, year)
        print(f"  \u2192 {count} clergy via machine parser")
    else:
        count = extract_narrative_via_kilo(db, year)
        print(f"  \u2192 {count} clergy via Kilo API")

    return count


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Hybrid Catholic Directory Extraction')
    ap.add_argument('--year', type=int, help='Single year')
    ap.add_argument('--all', action='store_true', help='All available years')
    ap.add_argument('--missing', action='store_true', help='Unprocessed years only')
    ap.add_argument('--all-narrative', action='store_true', help='Narrative years via Kilo')
    ap.add_argument('--force', action='store_true', help='Re-extract even if exists')
    ap.add_argument('--dry-run', action='store_true', help='Show what would be done')
    args = ap.parse_args()

    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=OFF")
    ensure_schema(db)

    years = get_available_years()
    processed = get_processed_years(db)

    if args.year:
        targets = [args.year]
    elif args.all:
        targets = years
    elif args.missing:
        targets = [y for y in years if y not in processed]
    elif args.all_narrative:
        narrative = set()
        for y in years:
            if y in processed: continue
            text = open(DIRS_CLEAN / f'{y}_cleaned.txt', encoding='utf-8').read(50000)
            if detect_format(y, text) == 'narrative':
                narrative.add(y)
        targets = sorted(narrative)
        print(f"Narrative unprocessed: {len(targets)} years")
    else:
        ap.print_help(); db.close(); return

    if args.dry_run:
        for y in targets:
            text = open(DIRS_CLEAN / f'{y}_cleaned.txt', encoding='utf-8').read(50000)
            fmt = detect_format(y, text)
            status = "\u2705" if y in processed else "\u2b1c"
            print(f"  {status} {y} [{fmt}]")
        db.close()
        return

    for y in targets:
        process_year(db, y, args.force)

    db.close()

    db2 = sqlite3.connect(str(DB_PATH))
    tp = db2.execute("SELECT COUNT(*) FROM catholic_parishes").fetchone()[0]
    tc = db2.execute("SELECT COUNT(*) FROM catholic_clergy").fetchone()[0]
    ty = db2.execute("SELECT COUNT(DISTINCT year) FROM catholic_clergy").fetchone()[0]
    print(f"\n{'='*60}")
    print(f"  DB: {tp} parishes, {tc} clergy across {ty} years")
    db2.close()


if __name__ == '__main__':
    main()
