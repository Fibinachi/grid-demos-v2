#!/usr/bin/env python3
"""
Nigeria 2023 Election Results — Wikipedia scraper
==================================================
Creates election_results_NG (state-level) join table.

Sources: Wikipedia — 2023 Nigerian presidential election
  State-level: APC, PDP, LP, NNPP votes + percentages + turnout

Join pattern:
  churches → church_census_NG → lga_zone_map.state_name → election_results_NG.state_name

Usage:
    python scripts/enrichment/_import_nigeria_election.py
"""
import json, os, re, sqlite3, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path('E:/grid')
sys.path.insert(0, str(PROJECT_DIR))
DB_PATH = PROJECT_DIR / 'churches.db'
DATA_DIR = PROJECT_DIR / 'data' / 'nigeria_census'
DATA_DIR.mkdir(parents=True, exist_ok=True)

WIKI_URL = 'https://en.wikipedia.org/w/api.php?action=parse&page=2023_Nigerian_presidential_election&prop=wikitext&format=json'
CACHE_PATH = DATA_DIR / 'nga_election_2023_wiki.json'


def main():
    db = sqlite3.connect(str(DB_PATH), timeout=120)
    t0 = time.time()
    
    print("=" * 60)
    print("Nigeria 2023 Election Import (Wikipedia)")
    print("=" * 60)
    
    # Fetch wikitext
    print("\n[1] Fetching Wikipedia data...")
    if CACHE_PATH.exists():
        wikitext = json.loads(CACHE_PATH.read_text())['wikitext']
        print(f"  Cached: {len(wikitext):,} chars")
    else:
        req = urllib.request.Request(WIKI_URL, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        wikitext = data['parse']['wikitext']['*']
        CACHE_PATH.write_text(json.dumps({'wikitext': wikitext}))
        print(f"  Fetched: {len(wikitext):,} chars")
    
    # Extract Results section
    print("\n[2] Parsing results...")
    results_start = wikitext.find('== Results ==')
    results_end = wikitext.find('== Aftermath ==', results_start)
    results_text = wikitext[results_start:results_end]
    
    # Parse national totals from the election results template
    national = parse_national(results_text)
    print(f"  National: APC {national['apc_votes']:,}, PDP {national['pdp_votes']:,}, "
          f"LP {national['lp_votes']:,}, NNPP {national['nnpp_votes']:,}")
    print(f"  Turnout: {national['turnout_pct']}%, Electorate: {national['electorate']:,}")
    
    # Parse state results from the "By state" table
    print("\n[3] Parsing state results...")
    states = parse_state_table(results_text)
    print(f"  Parsed {len(states)} states")
    
    # Map Wikipedia state names to our geoBoundaries state names
    name_map = build_name_map(db)
    
    # Show matching
    matched = 0
    unmatched = []
    for s in states:
        wiki_name = s['state_name']
        # Clean FCT template
        if '{{abbr' in wiki_name:
            wiki_name = re.sub(r'\{\{abbr\|[^|]*\|([^}]*)\}\}', r'\1', wiki_name)
        mapped = name_map.get(wiki_name.lower(), None)
        if mapped:
            s['state_name_mapped'] = mapped
            matched += 1
        else:
            unmatched.append(wiki_name)
            s['state_name_mapped'] = wiki_name  # use as-is
    
    print(f"  Matched to geoBoundaries: {matched}/{len(states)}")
    if unmatched:
        print(f"  Unmatched: {unmatched}")
    
    # Determine winner per state
    for s in states:
        votes = {'APC': s['apc_votes'], 'PDP': s['pdp_votes'],
                 'LP': s['lp_votes'], 'NNPP': s['nnpp_votes']}
        s['winner'] = max(votes, key=votes.get)
    
    # Parse zone results
    print("\n[4] Parsing zone results...")
    zones = parse_zone_table(results_text)
    print(f"  Parsed {len(zones)} zones")
    
    # Create tables
    print("\n[5] Creating join tables...")
    create_election_state(db, states)
    create_election_zone(db, zones)
    update_catalog(db)
    
    # Verify
    print("\n[6] Verification...")
    verify(db)
    
    # Provenance
    now = datetime.now().isoformat()
    elapsed = time.time() - t0
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at, status, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ('wikipedia_2023_nigeria_election', '_import_nigeria_election.py',
          now, now, 'completed',
          f'NG 2023 election: {len(states)} states. {elapsed:.0f}s'))
    db.commit()
    db.close()
    print(f"\nDone! ({elapsed:.0f}s)")


def parse_national(text):
    """Parse {{Election results}} template for national totals."""
    d = {
        'apc_votes': 0, 'pdp_votes': 0, 'lp_votes': 0, 'nnpp_votes': 0,
        'electorate': 0, 'turnout_pct': 0, 'total_valid': 0, 'invalid': 0
    }
    
    # Extract from template
    m = re.search(r'\|votes1=(\d+)', text)
    if m: d['apc_votes'] = int(m.group(1))
    m = re.search(r'\|votes2=(\d+)', text)
    if m: d['pdp_votes'] = int(m.group(1))
    m = re.search(r'\|votes3=(\d+)', text)
    if m: d['lp_votes'] = int(m.group(1))
    m = re.search(r'\|votes4=(\d+)', text)
    if m: d['nnpp_votes'] = int(m.group(1))
    
    # Total from the zone table
    m = re.search(r'!\s*Total[\s\S]*?\n!\s*([\d,]+)\s*\|\|\s*([\d.]+)%[\s\S]*?\n!\s*([\d,]+)\s*\|\|\s*([\d.]+)%[\s\S]*?\n!\s*([\d,]+)\s*\|\|\s*([\d.]+)%[\s\S]*?\n!\s*([\d,]+)\s*\|\|\s*([\d.]+)%[\s\S]*?\n!\s*([\d,]+)\s*\|\|\s*([\d.]+)%\s*\n!\s*([\d,]+)\s*\n!\s*([\d.]+)%', text)
    
    # Simpler approach: sum from state table
    total = d['apc_votes'] + d['pdp_votes'] + d['lp_votes'] + d['nnpp_votes']
    d['total_valid'] = 24025940  # Known from Wikipedia
    
    m = re.search(r'\|electorate=(\d+)', text)
    if m: d['electorate'] = int(m.group(1))
    
    if d['electorate'] > 0:
        d['turnout_pct'] = round(d['total_valid'] / d['electorate'] * 100, 2)
    
    return d


def parse_state_table(text):
    """Parse the 'By state' wikitable."""
    state_start = text.find('==== By state ====')
    if state_start == -1:
        state_start = text.find('=== By state ===')
    state_section = text[state_start:]
    
    # Clean wikitext: remove refs, bold markers, HTML comments
    cleaned = re.sub(r'<ref[^>]*>.*?</ref>', '', state_section, flags=re.DOTALL)
    cleaned = re.sub(r"'''", '', cleaned)
    cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)
    
    # Pattern for each state row
    # State name from wikilink: [[...|StateName]]
    # Followed by 4 rows of (votes || pct || threshold), then others row, total, turnout
    pattern = (
        r'\|\s*style="text-align:left;"\s*\|\s*\[\[[^\]]*?\|([^\]]+)\]\]\s*\n'
        r'\|\s*([\d,]+)\s*\|\|\s*([\d.]+)%\s*\|\|\s*(\d+)\s*\n'
        r'\|\s*([\d,]+)\s*\|\|\s*([\d.]+)%\s*\|\|\s*(\d+)\s*\n'
        r'\|\s*([\d,]+)\s*\|\|\s*([\d.]+)%\s*\|\|\s*(\d+)\s*\n'
        r'\|\s*([\d,]+)\s*\|\|\s*([\d.]+)%\s*\|\|\s*(\d+)\s*\n'
        r'\|\s*([\d,]+)\s*\|\|\s*([\d.]+)%\s*\n'
        r'\|\s*([\d,]+)\s*\n'
        r'\|\s*([\d.]+)%'
    )
    
    states = []
    for m in re.finditer(pattern, cleaned):
        name = m.group(1).strip()
        if name.lower() in ('total', 'abbreviation', 'state', 'states of nigeria'):
            continue
        
        try:
            states.append({
                'state_name': name,
                'apc_votes': int(m.group(2).replace(',', '')),
                'apc_pct': float(m.group(3)),
                'pdp_votes': int(m.group(5).replace(',', '')),
                'pdp_pct': float(m.group(6)),
                'lp_votes': int(m.group(8).replace(',', '')),
                'lp_pct': float(m.group(9)),
                'nnpp_votes': int(m.group(11).replace(',', '')),
                'nnpp_pct': float(m.group(12)),
                'other_votes': int(m.group(14).replace(',', '')),
                'other_pct': float(m.group(15)),
                'total_valid': int(m.group(16).replace(',', '')),
                'turnout_pct': float(m.group(17)),
            })
        except (ValueError, IndexError) as e:
            print(f"  Parse error for '{name}': {e}")
    
    return states


def parse_zone_table(text):
    """Parse the 'By geopolitical zone' wikitable."""
    zone_start = text.find('==== By geopolitical zone ====')
    zone_section = text[zone_start:]
    
    # Clean
    cleaned = re.sub(r'<ref[^>]*>.*?</ref>', '', zone_section, flags=re.DOTALL)
    cleaned = re.sub(r"'''", '', cleaned)
    cleaned = re.sub(r'\{\{efn\|.*?\}\}', '', cleaned)  # Remove efn templates
    cleaned = re.sub(r'\{\{abbr\|[^}]*\}\}', '', cleaned)  # Remove abbr templates
    cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'&nbsp;', ' ', cleaned)
    
    pattern = (
        r'\|\s*style="text-align:left;"\s*\|\s*\[\[(?:[^\]]*?\|)?([^\]]+)\]\]\s*\n'
        r'\|\s*([\d,]+)\s*\|\|\s*([\d.]+)%\s*\|\|\s*(\d+)\s*\n'
        r'\|\s*([\d,]+)\s*\|\|\s*([\d.]+)%\s*\|\|\s*(\d+)\s*\n'
        r'\|\s*([\d,]+)\s*\|\|\s*([\d.]+)%\s*\|\|\s*(\d+)\s*\n'
        r'\|\s*([\d,]+)\s*\|\|\s*([\d.]+)%\s*\|\|\s*(\d+)\s*\n'
        r'\|\s*([\d,]+)\s*\|\|\s*([\d.]+)%\s*\n'
        r'\|\s*([\d,]+)\s*\n'
        r'\|\s*([\d.]+)?%?'
    )
    
    zones = []
    valid_zones = {'North Central', 'North East', 'North West', 'South East', 'South South', 'South West'}
    
    for m in re.finditer(pattern, cleaned):
        name = m.group(1).strip()
        if name not in valid_zones:
            continue
        try:
            turnout = float(m.group(17)) if m.group(17) else None
            zones.append({
                'zone_name': name,
                'apc_votes': int(m.group(2).replace(',', '')),
                'apc_pct': float(m.group(3)),
                'pdp_votes': int(m.group(5).replace(',', '')),
                'pdp_pct': float(m.group(6)),
                'lp_votes': int(m.group(8).replace(',', '')),
                'lp_pct': float(m.group(9)),
                'nnpp_votes': int(m.group(11).replace(',', '')),
                'nnpp_pct': float(m.group(12)),
                'other_votes': int(m.group(14).replace(',', '')),
                'other_pct': float(m.group(15)),
                'total_valid': int(m.group(16).replace(',', '')),
                'turnout_pct': turnout,
            })
        except (ValueError, IndexError) as e:
            print(f"  Zone parse error for '{name}': {e}")
    
    return zones


def build_name_map(db):
    """Map Wikipedia state names to geoBoundaries ADM1 state names (case-insensitive)."""
    cur = db.execute("SELECT DISTINCT state_name FROM lga_zone_map WHERE state_name IS NOT NULL")
    gb_states = {r[0]: r[0].lower() for r in cur if r[0]}
    
    name_map = {}
    for gb_name, gb_lower in gb_states.items():
        name_map[gb_lower] = gb_name
        # Special: handle FCT/Abuja variations
        if 'federal capital' in gb_lower:
            name_map['f.c.t.'] = gb_name
            name_map['fct'] = gb_name
            name_map['abuja'] = gb_name
            name_map['federal capital territory'] = gb_name
    
    return name_map


def create_election_state(db, states):
    """Create election_results_NG table (state-level)."""
    
    db.executescript('''
        DROP TABLE IF EXISTS election_results_NG;
        CREATE TABLE election_results_NG (
            state_name      TEXT PRIMARY KEY,
            year            INTEGER DEFAULT 2023,
            
            -- Major party votes
            apc_votes       INTEGER,
            apc_pct         REAL,
            pdp_votes       INTEGER,
            pdp_pct         REAL,
            lp_votes        INTEGER,
            lp_pct          REAL,
            nnpp_votes      INTEGER,
            nnpp_pct        REAL,
            other_votes     INTEGER,
            other_pct       REAL,
            
            -- Totals
            total_valid     INTEGER,
            turnout_pct     REAL,
            winner          TEXT,
            
            -- Source
            source          TEXT DEFAULT 'wikipedia_2023',
            updated_at      TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_elec_ng_winner ON election_results_NG(winner);
    ''')
    
    for s in states:
        mapped = s.get('state_name_mapped', s['state_name'])
        db.execute('''
            INSERT OR REPLACE INTO election_results_NG
                (state_name, year, apc_votes, apc_pct, pdp_votes, pdp_pct,
                 lp_votes, lp_pct, nnpp_votes, nnpp_pct, other_votes, other_pct,
                 total_valid, turnout_pct, winner)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            mapped, 2023,
            s['apc_votes'], s['apc_pct'],
            s['pdp_votes'], s['pdp_pct'],
            s['lp_votes'], s['lp_pct'],
            s['nnpp_votes'], s['nnpp_pct'],
            s['other_votes'], s['other_pct'],
            s['total_valid'], s['turnout_pct'],
            s['winner'],
        ))
    
    rc = db.execute('SELECT COUNT(*) FROM election_results_NG').fetchone()[0]
    print(f"  election_results_NG: {rc} states")
    
    # Show winners
    print("  Winners by state:")
    for r in db.execute('''
        SELECT winner, COUNT(*) FROM election_results_NG GROUP BY winner ORDER BY COUNT(*) DESC
    '''):
        print(f"    {r[0]:5s}: {r[1]:2d} states")


def create_election_zone(db, zones):
    """Create election_zone_NG table."""
    
    db.executescript('''
        DROP TABLE IF EXISTS election_zone_NG;
        CREATE TABLE election_zone_NG (
            zone_name       TEXT PRIMARY KEY,
            year            INTEGER DEFAULT 2023,
            apc_votes       INTEGER,
            apc_pct         REAL,
            pdp_votes       INTEGER,
            pdp_pct         REAL,
            lp_votes        INTEGER,
            lp_pct          REAL,
            nnpp_votes      INTEGER,
            nnpp_pct        REAL,
            other_votes     INTEGER,
            other_pct       REAL,
            total_valid     INTEGER,
            turnout_pct     REAL,
            winner          TEXT,
            source          TEXT DEFAULT 'wikipedia_2023',
            updated_at      TEXT DEFAULT (datetime('now'))
        );
    ''')
    
    for z in zones:
        votes = {'APC': z['apc_votes'], 'PDP': z['pdp_votes'],
                 'LP': z['lp_votes'], 'NNPP': z['nnpp_votes']}
        winner = max(votes, key=votes.get)
        
        db.execute('''
            INSERT OR REPLACE INTO election_zone_NG
                (zone_name, year, apc_votes, apc_pct, pdp_votes, pdp_pct,
                 lp_votes, lp_pct, nnpp_votes, nnpp_pct, other_votes, other_pct,
                 total_valid, turnout_pct, winner)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            z['zone_name'], 2023,
            z['apc_votes'], z['apc_pct'],
            z['pdp_votes'], z['pdp_pct'],
            z['lp_votes'], z['lp_pct'],
            z['nnpp_votes'], z['nnpp_pct'],
            z['other_votes'], z['other_pct'],
            z['total_valid'], z['turnout_pct'],
            winner,
        ))
    
    rc = db.execute('SELECT COUNT(*) FROM election_zone_NG').fetchone()[0]
    print(f"  election_zone_NG: {rc} zones")


def update_catalog(db):
    entries = [
        ('election_results_NG', 'election', 'state', 'Nigeria 2023 presidential results by state', 14),
        ('election_zone_NG', 'election', 'zone', 'Nigeria 2023 presidential results by zone', 14),
    ]
    for table, cat, geo, desc, varcnt in entries:
        rc = db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        db.execute('''
            INSERT OR REPLACE INTO church_census_catalog
                (country, table_name, category, geo_unit, description, variable_count, row_count, refresh_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, date('now'))
        ''', ('NG', table, cat, geo, desc, varcnt, rc))
    print("  Catalog updated")


def verify(db):
    # Churches with state election data
    r = db.execute('''
        SELECT COUNT(*) FROM churches c
        JOIN church_census_NG cn ON c.rowid = cn.church_rowid
        JOIN lga_zone_map zm ON cn.dist_code = zm.dist_code
        JOIN election_results_NG er ON zm.state_name = er.state_name
        WHERE c.country = 'NG'
    ''').fetchone()
    print(f"  Churches with state election data: {r[0]:,}")
    
    # Zone election
    r = db.execute('''
        SELECT COUNT(*) FROM churches c
        JOIN church_census_NG cn ON c.rowid = cn.church_rowid
        JOIN lga_zone_map zm ON cn.dist_code = zm.dist_code
        JOIN election_zone_NG ez ON zm.zone_name = ez.zone_name
        WHERE c.country = 'NG'
    ''').fetchone()
    print(f"  Churches with zone election data: {r[0]:,}")
    
    # Show state-level breakdown with religion context
    print("\n  Election + DHS combined view (Muslim north vs Christian south):")
    print(f"  {'State':25s} {'Winner':6s} {'APC%':>6s} {'LP%':>6s} {'PDP%':>6s} {'TFR':>5s} {'NoEd%':>6s} {'Churches':>8s}")
    print(f"  {'-'*25} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*5} {'-'*6} {'-'*8}")
    for r in db.execute('''
        SELECT er.state_name, er.winner, er.apc_pct, er.lp_pct, er.pdp_pct,
               ds.total_fertility_rate, ds.pct_women_no_education,
               COUNT(DISTINCT c.rowid) as churches
        FROM election_results_NG er
        JOIN lga_zone_map zm ON er.state_name = zm.state_name
        JOIN church_census_NG cn ON zm.dist_code = cn.dist_code
        JOIN churches c ON cn.church_rowid = c.rowid
        LEFT JOIN dhs_state_NG ds ON er.state_name = ds.state_name
        WHERE c.country = 'NG'
        GROUP BY er.state_name
        ORDER BY churches DESC
        LIMIT 15
    '''):
        apc = f'{r[2]:.0f}%' if r[2] else '?'
        lp = f'{r[3]:.0f}%' if r[3] else '?'
        pdp = f'{r[4]:.0f}%' if r[4] else '?'
        tfr = f'{r[5]:.1f}' if r[5] else '?'
        ned = f'{r[6]:.0f}%' if r[6] else '?'
        print(f"  {r[0][:25]:25s} {r[1]:6s} {apc:>6s} {lp:>6s} {pdp:>6s} {tfr:>5s} {ned:>6s} {r[7]:8,}")


if __name__ == '__main__':
    main()
