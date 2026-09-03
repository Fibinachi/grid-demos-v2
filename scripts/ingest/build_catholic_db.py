"""
Build standalone Catholic Directory database.

Architecture:
- Parse 2021 directory first (most complete, cleanest)
- Work backwards: 2020 matches to 2021, 2019 to 2020, ...
- Chain-link: each parish links to same parish in adjacent years
- Original names preserved; normalized names for matching

Tables:
  catholic_parishes  — one row per parish per year
  catholic_clergy    — one row per priest assignment per year
  catholic_dioceses  — diocese metadata

Usage:
  python scripts/ingest/build_catholic_db.py --init        # Create DB + parse 2021
  python scripts/ingest/build_catholic_db.py --year 2020   # Parse + link one year
  python scripts/ingest/build_catholic_db.py --all-back    # Work backwards 2020→1860
  python scripts/ingest/build_catholic_db.py --stats       # Show stats
"""
import sqlite3, re, sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

DB_PATH = Path("E:/grid/data/catholic_directory.db")
DIRS = Path("E:/grid/data/directories")


# ── Normalization ────────────────────────────────────────────────

def normalize_name(name):
    if not name: return ''
    n = name.lower().strip()
    n = re.sub(r'\bst\.?\s+', 'saint ', n)
    n = re.sub(r'\bss\.?\s+', 'saints ', n)
    n = re.sub(r'\bmt\.?\s+', 'mount ', n)
    n = re.sub(r'[^\w\s]', '', n)
    n = re.sub(r'\bsaint\s+(\w+)s\b', r'saint \1', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def norm_diocese(name):
    if not name: return ''
    n = name.strip()
    n = re.sub(r'^(?:Archdiocese|Diocese)\s+of\s+', '', n, flags=re.IGNORECASE)
    n = re.sub(r'[\.\s,;:].*$', '', n)
    n = re.sub(r'\s+', ' ', n).strip().lower()
    n = n.replace('st.', 'saint')
    fixes = {'yincennes':'vincennes','nesqualy':'seattle','oregon city':'portland',
             'fbancisco':'francisco','pittsburgh':'pittsburg','new-york':'new york',
             'new-orleans':'new orleans','saut sainte marie':'marquette'}
    n = re.sub(r'[^a-z\s]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    for bad, good in fixes.items():
        if re.sub(r'[^a-z\s]', '', bad) in n: n = good; break
    return n


# ── DB Schema ────────────────────────────────────────────────────

def init_db(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS catholic_dioceses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,           -- modern name (e.g. "Archdiocese of Baltimore")
            norm_name TEXT NOT NULL,       -- normalized for matching
            city TEXT, state TEXT, country TEXT DEFAULT 'US',
            UNIQUE(norm_name)
        );

        CREATE TABLE IF NOT EXISTS catholic_parishes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            diocese_id INTEGER REFERENCES catholic_dioceses(id),
            parish_name TEXT NOT NULL,      -- name as it appears in this year's directory
            original_name TEXT NOT NULL,    -- exact text from source (for matching)
            norm_name TEXT NOT NULL,        -- normalized for search
            city TEXT,
            address TEXT,
            zip TEXT,
            phone TEXT,
            founded_year INTEGER,           -- from directory notation (1848)
            status TEXT DEFAULT 'active',   -- active, closed, merged
            prev_year_id INTEGER,           -- same parish in previous year
            next_year_id INTEGER,           -- same parish in next year
            church_id INTEGER,              -- link to churches.db (future)
            source_file TEXT,
            source_line INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS catholic_clergy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            parish_id INTEGER REFERENCES catholic_parishes(id),
            priest_name TEXT NOT NULL,
            title TEXT,                     -- Rev., Very Rev., Most Rev., etc.
            religious_order TEXT,           -- S.J., O.S.B., etc.
            role TEXT,                      -- Pastor, Assistant, etc.
            source_file TEXT,
            source_line INTEGER,
            raw_line TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_cp_year ON catholic_parishes(year);
        CREATE INDEX IF NOT EXISTS idx_cp_diocese ON catholic_parishes(diocese_id);
        CREATE INDEX IF NOT EXISTS idx_cp_norm ON catholic_parishes(norm_name);
        CREATE INDEX IF NOT EXISTS idx_cp_prev ON catholic_parishes(prev_year_id);
        CREATE INDEX IF NOT EXISTS idx_cc_year ON catholic_clergy(year);
        CREATE INDEX IF NOT EXISTS idx_cc_parish ON catholic_clergy(parish_id);
        CREATE INDEX IF NOT EXISTS idx_cc_priest ON catholic_clergy(priest_name);
        CREATE INDEX IF NOT EXISTS idx_cd_norm ON catholic_dioceses(norm_name);
    """)
    db.commit()


# ── 2021 Parser ──────────────────────────────────────────────────

RE_DIOCESE_2021 = re.compile(r'^(?:Archdiocese|Diocese)\s+of\s+([A-Za-z\s\-\']+?)(?:,\s*T:.*)?$')
RE_PARISH_2021 = re.compile(r'^(\d+)[—\-]\s*(.+?)(?:,\s*(.+?))?\s*\((\d{4})\)')
RE_ADDRESS = re.compile(r'^(.+?),?\s*(\d{5}(?:-\d{4})?)\.?\s*(?:T:|F:|$|Church@|www\.|\.com)')

def parse_modern_directory(db, year):
    """Parse a modern (numbered-entry) directory into catholic_parishes + catholic_clergy."""
    src = DIRS / f"{year}_formatted.txt"
    if not src.exists():
        print(f"  Source not found: {src}")
        return 0

    # Check format: modern directories have '^\d+[—\-]' numbered entries
    with open(src, 'r', encoding='utf-8', errors='replace') as f:
        sample = f.read(50000)
    if not re.search(r'^\d+[—\-]', sample, re.MULTILINE):
        return None  # Not modern format

    print(f"Parsing {year} from {src.name}...")
    src_name = f"{year}_formatted.txt"
    current_diocese_id = None
    parishes = []
    clergy_records = []

    with open(src, 'r', encoding='utf-8', errors='replace') as f:
        lines = [l.rstrip() for l in f.readlines()]

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        dm = RE_DIOCESE_2021.match(line)
        if dm:
            dio_name = dm.group(1).strip()
            nd = norm_diocese(dio_name)
            cur = db.execute("SELECT id FROM catholic_dioceses WHERE norm_name=?", (nd,)).fetchone()
            if not cur:
                db.execute("INSERT INTO catholic_dioceses (name, norm_name) VALUES (?,?)", (dio_name, nd))
                db.commit()
                cur = db.execute("SELECT id FROM catholic_dioceses WHERE norm_name=?", (nd,)).fetchone()
            current_diocese_id = cur[0]
            
            # Extract chancery info from following lines
            ch_lines = []
            j = i + 1
            while j < len(lines) and j < i + 40:
                nl = lines[j].strip()
                if RE_DIOCESE_2021.match(nl) or RE_PARISH_2021.match(nl):
                    break
                ch_lines.append(nl)
                j += 1
            ch_text = ' '.join(ch_lines)
            
            # Extract bishop
            bishop = None
            bm = re.search(r'Most\s+Rev(?:erend)?\s+([A-Z][A-Z\s\.]+?)(?:,|\.|D\.D\.|ordained)', ch_text)
            if bm: bishop = bm.group(1).strip()
            
            # Extract address
            addr = None; city = None; st = None; zip_code = None
            am = re.search(r'(?:Chancery\s+Office|Pastoral\s+Center)[:\s]+(.+?)(?:\d{5})', ch_text)
            if am:
                addr_text = am.group(1)
                zm = re.search(r'(\d{5}(?:-\d{4})?)', ch_text)
                if zm: zip_code = zm.group(1)
                # City, State
                csm = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})', ch_text[am.end()-50:])
                if csm: city, st = csm.group(1), csm.group(2)
                addr = addr_text.strip().rstrip(',').strip()
            
            # Extract phone/fax/email/web
            phone = None; fax = None; email = None; web = None
            pm = re.search(r'(?:Tel[:\s.]*|T:\s*)([\d\-\(\)\s\.]+)', ch_text)
            if pm: phone = pm.group(1).strip()
            fm = re.search(r'(?:Fax|F):\s*([\d\-\(\)\s\.]+)', ch_text)
            if fm: fax = fm.group(1).strip()
            em = re.search(r'([\w\.]+@[\w\.]+)', ch_text)
            if em: email = em.group(1)
            wm = re.search(r'(?:Web|www)\S*:\s*(\S+\.(?:org|com|net))', ch_text, re.IGNORECASE)
            if wm: web = wm.group(1)
            
            # Insert chancery
            if addr or phone or bishop:
                db.execute("""
                    INSERT OR IGNORE INTO catholic_chanceries
                    (year, diocese_id, address, city, state, zip, phone, fax, email, website, bishop_name, source_file)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (year, current_diocese_id, addr, city, st, zip_code, phone, fax, email, web, bishop, src_name))
            
            i = j
            continue

        pm = RE_PARISH_2021.match(line)
        if pm and current_diocese_id:
            parish_name = pm.group(2).strip()
            city = (pm.group(3) or '').strip()
            founded = int(pm.group(4))

            addr_lines = []
            j = i + 1
            while j < len(lines) and j < i + 15:
                nl = lines[j].strip()
                if RE_PARISH_2021.match(nl) or RE_DIOCESE_2021.match(nl):
                    break
                if nl and not re.match(r'^(School|Convent|Legal Name|The Portier)', nl):
                    addr_lines.append(nl)
                j += 1

            addr_text = ' '.join(addr_lines)

            am = RE_ADDRESS.search(addr_text)
            address = am.group(1).strip() if am else addr_text[:200]
            zip_code = am.group(2) if am else None

            phone = None
            pm2 = re.search(r'T:\s*([\d\-\(\)\s\.]+)', addr_text)
            if pm2: phone = pm2.group(1).strip().rstrip('.')

            for cm in re.finditer(
                r'(?:Rev(?:s?\.|erend)\s+)?(?:Msgr\.\s+)?(?:Very\s+Rev(?:\.|erend)?\.?\s+)?'
                r'((?:[A-Z][a-z]+(?:\s+[A-Z]\.)*\s+){1,3}[A-Z][a-z]+)',
                addr_text
            ):
                name = cm.group(1).strip()
                skip = ('Legal','Mailing','The Portier','Parish Office','School',
                        'Corpus Christi','St Dominic','Holy Family','Cathedral',
                        'Government','Springhill','McKenna','Burma','Joyce',
                        'Stephens','Conti','Dauphin','Total Students','Lodge',
                        'Delaware','Williams','Hopewell','Rosa','Main','West')
                if name not in skip and not re.match(r'^\d', name):
                    clergy_records.append({
                        'parish_name': parish_name, 'diocese_id': current_diocese_id,
                        'priest_name': name, 'title': 'Rev.',
                        'source_line': i + 1, 'raw_line': line,
                    })

            parishes.append({
                'diocese_id': current_diocese_id, 'parish_name': parish_name,
                'original_name': parish_name, 'norm_name': normalize_name(parish_name),
                'city': city, 'address': address, 'zip': zip_code, 'phone': phone,
                'founded_year': founded, 'source_line': i + 1, 'source_file': src.name,
            })
            i = j
            continue
        i += 1

    # Insert all parish records
    parish_id_map = {}
    for p in parishes:
        cur = db.execute("""
            INSERT INTO catholic_parishes (year, diocese_id, parish_name, original_name, norm_name, city, address, zip, phone, founded_year, source_file, source_files, source_line)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (year, p['diocese_id'], p['parish_name'], p['original_name'], p['norm_name'],
              p['city'], p['address'], p['zip'], p['phone'], p['founded_year'],
              src_name, src_name, p['source_line']))
        pid = cur.lastrowid
        key = (p['diocese_id'], p['norm_name'], (p['city'] or '').lower())
        parish_id_map[key] = pid

    clergy_count = 0
    for c in clergy_records:
        key = (c['diocese_id'], normalize_name(c['parish_name']), '')
        pid = parish_id_map.get(key)
        if pid:
            db.execute("INSERT INTO catholic_clergy (year, parish_id, priest_name, title, source_line, raw_line) VALUES (?,?,?,?,?,?)",
                       (year, pid, c['priest_name'], c['title'], c['source_line'], c['raw_line']))
            clergy_count += 1

    db.commit()
    total = db.execute("SELECT COUNT(*) FROM catholic_parishes WHERE year=?", (year,)).fetchone()[0]
    print(f"  {year}: {total:,} parishes, {clergy_count:,} clergy")
    return total


# ── Backwards linker ─────────────────────────────────────────────

def link_year(db, year):
    """Parse directory for `year` and link parishes to `year+1`."""
    src = DIRS / f"{year}_formatted.txt"
    if not src.exists():
        print(f"  No source for {year}")
        return 0

    # Check if already done
    existing = db.execute("SELECT COUNT(*) FROM catholic_parishes WHERE year=?", (year,)).fetchone()[0]
    if existing > 0:
        print(f"  {year}: already has {existing:,} parishes (skipping)")
        return existing

    # Parse using existing machine-format parser
    from scripts.ingest.parse_catholic_directories import parse_file
    records = parse_file(str(src), year)

    # Filter garbage
    garbage = re.compile(r'^$|^(Most|Rt\.?|Very|V\.|Mt\.?)$|^(?:Rev|Reverend)', re.IGNORECASE)
    records = [r for r in records if r['parish'] and not garbage.search(r['parish'])]

    if not records:
        print(f"  {year}: no valid parish records extracted")
        return 0

    # Get year+1 parishes for matching
    next_parishes = {}
    for r in db.execute("""
        SELECT p.id, p.diocese_id, d.norm_name as dio_norm, p.norm_name, p.city
        FROM catholic_parishes p
        JOIN catholic_dioceses d ON d.id = p.diocese_id
        WHERE p.year = ?
    """, (year + 1,)).fetchall():
        key = (r[2], r[3], (r[4] or '').lower())
        next_parishes[key] = r[0]

    # Track dioceses
    dio_cache = {}
    def get_diocese_id(name):
        nd = norm_diocese(name)
        if nd not in dio_cache:
            cur = db.execute("SELECT id FROM catholic_dioceses WHERE norm_name=?", (nd,)).fetchone()
            if cur:
                dio_cache[nd] = cur[0]
            else:
                db.execute("INSERT INTO catholic_dioceses (name, norm_name) VALUES (?,?)", (name, nd))
                db.commit()
                dio_cache[nd] = db.execute("SELECT id FROM catholic_dioceses WHERE norm_name=?", (nd,)).fetchone()[0]
        return dio_cache[nd]

    # Deduplicate: one row per unique (diocese, norm_name, city)
    seen = {}
    linked = 0
    new_parishes = 0
    clergy_inserts = 0

    parish_clergy = defaultdict(list)
    for r in records:
        dio_id = get_diocese_id(r['diocese'] or '')
        np = normalize_name(r['parish'] or '')
        city = (r['city'] or '').lower().strip()
        key = (dio_id, np, city)
        parish_clergy[key].append(r)

    for key, recs in parish_clergy.items():
        dio_id, np, city = key
        r = recs[0]  # Use first record for parish info
        match_key = (norm_diocese(r['diocese'] or ''), np, city)

        # Try to link to year+1
        next_id = next_parishes.get(match_key)
        if next_id:
            linked += 1
            status = 'linked'
        else:
            # Try fuzzy: just diocese + name
            for (d, n, c), pid in next_parishes.items():
                if d == match_key[0] and n == match_key[1]:
                    next_id = pid
                    linked += 1
                    status = 'linked_fuzzy'
                    break
            else:
                new_parishes += 1
                status = 'new'

        # Insert parish
        src_file = f"{year}_formatted.txt"
        
        # Get master_parish_id and accumulated source_files from year+1 match
        master_id = None
        acc_sources = src_file
        if next_id:
            next_row = db.execute("SELECT master_parish_id, source_files FROM catholic_parishes WHERE id=?", (next_id,)).fetchone()
            if next_row:
                master_id = next_row[0]
                acc_sources = (next_row[1] or '') + ', ' + src_file

        cur = db.execute("""
            INSERT INTO catholic_parishes (year, diocese_id, parish_name, original_name, norm_name, city, status, next_year_id, master_parish_id, source_files, source_file, source_line)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (year, dio_id, r['parish'], r['parish'], np, city or None,
              status, next_id, master_id, acc_sources, src_file, r['source_line']))
        pid = cur.lastrowid

        # New parishes get their own master_parish_id
        if not master_id:
            db.execute("UPDATE catholic_parishes SET master_parish_id=? WHERE id=?", (pid, pid))

        # Update year+1's prev_year_id and source_files
        if next_id:
            db.execute("UPDATE catholic_parishes SET prev_year_id=?, source_files=? WHERE id=?", (pid, acc_sources, next_id))

        # Insert clergy for this parish
        for cr in recs:
            db.execute("""
                INSERT INTO catholic_clergy (year, parish_id, priest_name, title, religious_order, role, source_line, raw_line)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (year, pid, cr['priest_name'], cr['title'], cr['order'], cr['role'],
                  cr['source_line'], cr['raw_line']))
            clergy_inserts += 1

    db.commit()
    total = linked + new_parishes
    print(f"  {year}: {total:,} parishes ({linked:,} linked to {year+1}, {new_parishes:,} new), {clergy_inserts:,} clergy")
    return total


# ── Stats ─────────────────────────────────────────────────────────

def show_stats(db):
    print(f"\n{'='*60}")
    print("CATHOLIC DIRECTORY DATABASE STATS")
    print(f"{'='*60}")

    # Parishes by year
    print(f"\n{'Year':<6} {'Parishes':>9} {'Clergy':>8} {'Linked':>8}")
    print("-" * 35)
    for r in db.execute("""
        SELECT p.year, COUNT(DISTINCT p.id),
               COUNT(DISTINCT c.id),
               SUM(CASE WHEN p.next_year_id IS NOT NULL THEN 1 ELSE 0 END)
        FROM catholic_parishes p
        LEFT JOIN catholic_clergy c ON c.parish_id = p.id
        GROUP BY p.year ORDER BY p.year DESC
    """).fetchall():
        print(f"{r[0]:<6} {r[1]:>9,} {r[2]:>8,} {r[3]:>8,}")

    # Totals
    total_p = db.execute("SELECT COUNT(*) FROM catholic_parishes").fetchone()[0]
    total_c = db.execute("SELECT COUNT(*) FROM catholic_clergy").fetchone()[0]
    total_d = db.execute("SELECT COUNT(*) FROM catholic_dioceses").fetchone()[0]
    print(f"\nTotal: {total_p:,} parish-year records, {total_c:,} clergy assignments, {total_d} dioceses")

    # Chain integrity
    chains = db.execute("""
        SELECT COUNT(*) FROM catholic_parishes
        WHERE prev_year_id IS NOT NULL AND next_year_id IS NOT NULL
    """).fetchone()[0]
    print(f"Full chain links (prev+next): {chains:,}")


# ── Main ──────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--init', action='store_true', help='Create DB + parse 2021')
    ap.add_argument('--year', type=int, help='Parse + link specific year')
    ap.add_argument('--all-back', action='store_true', help='Work backwards 2020→1860')
    ap.add_argument('--stats', action='store_true')
    args = ap.parse_args()

    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    init_db(db)

    if args.init:
        print("Initializing Catholic Directory Database...")
        parse_modern_directory(db, 2021)
        show_stats(db)

    elif args.year:
        link_year(db, args.year)
        show_stats(db)

    elif args.all_back:
        parse_modern_directory(db, 2021)
        for y in range(2020, 1859, -1):
            link_year(db, y)
        show_stats(db)

    elif args.stats:
        show_stats(db)

    else:
        ap.print_help()

    db.close()


if __name__ == '__main__':
    main()
