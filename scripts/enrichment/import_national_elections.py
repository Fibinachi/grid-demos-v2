#!/usr/bin/env python3
"""
Import national presidential & parliamentary election results from Wikipedia.
Creates: election_{ISO2}_results tables with district-level vote shares.

Pattern: Match Wikipedia region names → church_election_{ISO2}.dist_name
Then store party vote counts/percentages per district.

Usage:
    python scripts/enrichment/import_national_elections.py              # all
    python scripts/enrichment/import_national_elections.py --country GB # UK only
    python scripts/enrichment/import_national_elections.py --dry-run    # preview
"""

import io, json, re, sqlite3, ssl, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

DB = Path(r'E:\grid\churches.db')
CHUNK = 100

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# ── Country Configs ─────────────────────────────────────────────────
# Each: wikipedia page, table matching hints, district mapping info

COUNTRIES = {
    'GB': {
        'name': 'United Kingdom',
        'election': '2024 General Election',
        'wiki': '2024_United_Kingdom_general_election',
        'results_table': 'election_gb_results',
        'church_table': 'church_election_GB',
        'region_kw': ['constituency', 'seat', 'borough', 'shire', 'county'],
        'skip_pollster': True,
        'notes': '650 constituencies, FPTP — Wikipedia has "Results by constituency" page',
    },
    'IN': {
        'name': 'India',
        'election': '2024 Lok Sabha',
        'wiki': '2024_Indian_general_election',
        'results_table': 'election_in_ls_results',
        'church_table': 'church_election_IN',
        'region_kw': ['constituency', 'state', 'seat'],
        'skip_pollster': True,
        'notes': '543 constituencies — may need separate "Results by constituency" page',
    },
    'DE': {
        'name': 'Germany',
        'election': '2025 Bundestag',
        'wiki': '2025_German_federal_election',
        'results_table': 'election_de_bt_results',
        'church_table': 'church_election_DE',
        'region_kw': ['constituency', 'wahlkreis', 'state', 'land'],
        'skip_pollster': True,
        'notes': '299 wahlkreise — constituency winners are in Results section',
    },
    'FR': {
        'name': 'France',
        'election': '2024 Legislative',
        'wiki': '2024_French_legislative_election',
        'results_table': 'election_fr_leg_results',
        'church_table': 'church_election_FR',
        'region_kw': ['constituency', 'circonscription', 'department'],
        'skip_pollster': True,
        'notes': '577 circonscriptions, two rounds',
    },
    'JP': {
        'name': 'Japan',
        'election': '2024 General Election',
        'wiki': '2024_Japanese_general_election',
        'results_table': 'election_jp_hr_results',
        'church_table': 'church_election_JP',
        'region_kw': ['district', 'prefecture', 'block', 'constituency'],
        'skip_pollster': True,
        'notes': '289 single-seat + 176 PR — mixed system',
    },
    'KR': {
        'name': 'South Korea',
        'election': '2024 Legislative',
        'wiki': '2024_South_Korean_legislative_election',
        'results_table': 'election_kr_leg_results',
        'church_table': 'church_election_KR',
        'region_kw': ['district', 'constituency', 'province', 'city'],
        'skip_pollster': True,
        'notes': '254 constituencies',
    },
    'TW': {
        'name': 'Taiwan',
        'election': '2024 Presidential + Legislative',
        'wiki': '2024_Taiwanese_presidential_election',  # Legislative separate
        'results_table': 'election_tw_results',
        'church_table': 'church_election_TW',
        'region_kw': ['county', 'city', 'district', 'township'],
        'skip_pollster': True,
        'notes': 'Two elections; may need separate pages',
    },
    'AU': {
        'name': 'Australia',
        'election': '2022 Federal Election',
        'wiki': '2022_Australian_federal_election',
        'results_table': 'election_au_results',
        'church_table': 'church_election_AU',
        'region_kw': ['division', 'electorate', 'seat', 'state'],
        'skip_pollster': True,
        'notes': '151 divisions, preferential voting — House results page',
    },
    'IE': {
        'name': 'Ireland',
        'election': '2024 General Election',
        'wiki': '2024_Irish_general_election',
        'results_table': 'election_ie_results',
        'church_table': 'church_election_IE',
        'region_kw': ['constituency', 'county', 'district'],
        'skip_pollster': True,
        'notes': '43 constituencies, STV — Wikipedia has detailed tables',
    },
    'NZ': {
        'name': 'New Zealand',
        'election': '2023 General Election',
        'wiki': '2023_New_Zealand_general_election',
        'results_table': 'election_nz_results',
        'church_table': 'church_election_NZ',
        'region_kw': ['electorate', 'seat', 'district', 'region'],
        'skip_pollster': True,
        'notes': '72 electorates + list seats — MMP',
    },
    'ES': {
        'name': 'Spain',
        'election': '2023 General Election',
        'wiki': '2023_Spanish_general_election',
        'results_table': 'election_es_results',
        'church_table': 'church_election_ES',
        'region_kw': ['province', 'constituency', 'district'],
        'skip_pollster': True,
        'notes': '52 provinces as constituencies',
    },
    'IT': {
        'name': 'Italy',
        'election': '2022 General Election',
        'wiki': '2022_Italian_general_election',
        'results_table': 'election_it_results',
        'church_table': 'church_election_IT',
        'region_kw': ['region', 'constituency', 'district', 'college'],
        'skip_pollster': True,
        'notes': 'Mixed FPTP + PR system',
    },
    'TR': {
        'name': 'Turkey',
        'election': '2023 Presidential + Parliamentary',
        'wiki': '2023_Turkish_presidential_election',
        'results_table': 'election_tr_results',
        'church_table': 'church_election_TR',
        'region_kw': ['province', 'district', 'il', 'region'],
        'skip_pollster': True,
        'notes': '81 provinces',
    },
    'ZA': {
        'name': 'South Africa',
        'election': '2024 General Election',
        'wiki': '2024_South_African_general_election',
        'results_table': 'election_za_results',
        'church_table': 'church_election_ZA',
        'region_kw': ['province', 'district', 'region'],
        'skip_pollster': True,
        'notes': '9 provinces, PR system — provincial results available',
    },
    'AR': {
        'name': 'Argentina',
        'election': '2023 Presidential',
        'wiki': '2023_Argentine_general_election',
        'results_table': 'election_ar_results',
        'church_table': 'church_election_AR',
        'region_kw': ['province', 'district', 'region'],
        'skip_pollster': True,
        'notes': '23 provinces + CABA',
    },
    'PE': {
        'name': 'Peru',
        'election': '2021 Presidential',
        'wiki': '2021_Peruvian_general_election',
        'results_table': 'election_pe_results',
        'church_table': 'church_election_PE',
        'region_kw': ['department', 'region', 'province'],
        'skip_pollster': True,
        'notes': '26 departments',
    },
    'CO': {
        'name': 'Colombia',
        'election': '2022 Presidential',
        'wiki': '2022_Colombian_presidential_election',
        'results_table': 'election_co_results',
        'church_table': 'church_election_CO',
        'region_kw': ['department', 'district', 'region'],
        'skip_pollster': True,
        'notes': '32 departments',
    },
    'EC': {
        'name': 'Ecuador',
        'election': '2023 Presidential',
        'wiki': '2023_Ecuadorian_general_election',
        'results_table': 'election_ec_results',
        'church_table': 'church_election_EC',
        'region_kw': ['province', 'district', 'region'],
        'skip_pollster': True,
        'notes': '24 provinces',
    },
    'GT': {
        'name': 'Guatemala',
        'election': '2023 Presidential',
        'wiki': '2023_Guatemalan_general_election',
        'results_table': 'election_gt_results',
        'church_table': 'church_election_GT',
        'region_kw': ['department', 'district', 'region'],
        'skip_pollster': True,
        'notes': '22 departments',
    },
    'AT': {
        'name': 'Austria',
        'election': '2024 National Council',
        'wiki': '2024_Austrian_legislative_election',
        'results_table': 'election_at_nr_results',
        'church_table': 'church_election_AT',
        'region_kw': ['state', 'land', 'bundesland', 'region'],
        'skip_pollster': True,
        'notes': '9 states as electoral regions',
    },
    'PT': {
        'name': 'Portugal',
        'election': '2024 Legislative',
        'wiki': '2024_Portuguese_legislative_election',
        'results_table': 'election_pt_results',
        'church_table': 'church_election_PT',
        'region_kw': ['district', 'circle', 'region', 'constituency'],
        'skip_pollster': True,
        'notes': '22 electoral circles',
    },
    'BE': {
        'name': 'Belgium',
        'election': '2024 Federal',
        'wiki': '2024_Belgian_federal_election',
        'results_table': 'election_be_results',
        'church_table': 'church_election_BE',
        'region_kw': ['province', 'constituency', 'region', 'college'],
        'skip_pollster': True,
        'notes': '11 constituencies',
    },
    'DK': {
        'name': 'Denmark',
        'election': '2022 General Election',
        'wiki': '2022_Danish_general_election',
        'results_table': 'election_dk_results',
        'church_table': 'church_election_DK',
        'region_kw': ['region', 'constituency', 'district', 'county'],
        'skip_pollster': True,
        'notes': '10 multi-member constituencies',
    },
    'CH': {
        'name': 'Switzerland',
        'election': '2023 Federal',
        'wiki': '2023_Swiss_federal_election',
        'results_table': 'election_ch_results',
        'church_table': 'church_election_CH',
        'region_kw': ['canton', 'district', 'region', 'constituency'],
        'skip_pollster': True,
        'notes': '26 cantons as constituencies',
    },
    'NO': {
        'name': 'Norway',
        'election': '2025 Parliamentary',
        'wiki': '2025_Norwegian_parliamentary_election',
        'results_table': 'election_no_results',
        'church_table': 'church_election_NO',
        'region_kw': ['county', 'fylke', 'district', 'constituency'],
        'skip_pollster': True,
        'notes': '19 multi-member constituencies',
    },
    'CZ': {
        'name': 'Czechia',
        'election': '2025 Parliamentary',
        'wiki': '2025_Czech_parliamentary_election',
        'results_table': 'election_cz_results',
        'church_table': 'church_election_CZ',
        'region_kw': ['region', 'kraj', 'district', 'constituency'],
        'skip_pollster': True,
        'notes': '14 regions as constituencies',
    },
    'SE': {
        'name': 'Sweden',
        'election': '2022 Riksdag',
        'wiki': '2022_Swedish_general_election',
        'results_table': 'election_se_results',
        'church_table': 'church_election_SE',
        'region_kw': ['county', 'lan', 'constituency', 'region'],
        'skip_pollster': True,
        'notes': '29 constituencies',
    },
    'FI': {
        'name': 'Finland',
        'election': '2023 Parliamentary',
        'wiki': '2023_Finnish_parliamentary_election',
        'results_table': 'election_fi_results',
        'church_table': 'church_election_FI',
        'region_kw': ['district', 'region', 'constituency', 'maakunta'],
        'skip_pollster': True,
        'notes': '13 electoral districts',
    },
}

# ── Helpers ──────────────────────────────────────────────────────────

def log(msg):
    print(f'  [{datetime.now().strftime("%H:%M:%S")}] {msg}')

def fetch_wiki(page_name):
    """Fetch Wikipedia page HTML."""
    url = f'https://en.wikipedia.org/wiki/{page_name}'
    req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0 (research)'})
    with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as r:
        html = r.read().decode('utf-8')
    # Fix common malformed HTML issues
    html = re.sub(r'colspan="[^"]*!', 'colspan="1', html)
    html = re.sub(r'colspan="[^"]*[^0-9"][^"]*"', 'colspan="1"', html)
    return html

def load_known_regions(db, iso):
    """Load known region names from church_election table."""
    c = db.cursor()
    table = f'church_election_{iso}'
    if c.execute('SELECT COUNT(*) FROM sqlite_master WHERE name=?', (table,)).fetchone()[0]:
        # Auto-detect name column
        c.execute(f'PRAGMA table_info({table})')
        cols = [r[1] for r in c.fetchall()]
        name_col = None
        for col in cols:
            if 'name' in col.lower():
                name_col = col
                break
        if not name_col:
            print(f'    No name column in {table}, cols={cols}')
            return set()
        
        names = set()
        c.execute(f'SELECT COUNT(*) FROM {table}')
        if c.fetchone()[0] == 0:
            return set()
        for r in c.execute(f'SELECT DISTINCT LOWER({name_col}) FROM {table}'):
            if r[0]:
                n = r[0].strip().lower()
                names.add(n)
                names.add(n.replace('-', ' '))
                names.add(n.replace('  ', ' '))
        return names
    return set()

def find_election_table(tables, cfg, known_regions):
    """Find the table most likely containing district-level results."""
    best = None
    best_score = 0
    region_kw = cfg.get('region_kw', [])
    
    for t in tables:
        if t.shape[0] < 3 or t.shape[0] > 1000:
            continue
        
        # Flatten multi-level columns
        cols = []
        for col in t.columns:
            if isinstance(col, tuple):
                parts = [str(x) for x in col if 'Unnamed' not in str(x) and str(x) != 'nan']
                cols.append(' | '.join(parts) if parts else str(col[0]))
            else:
                cols.append(str(col))
        t_flat = t.copy()
        t_flat.columns = cols
        
        first_col_vals = [str(v).strip().lower() for v in t_flat.iloc[:, 0].values if pd.notna(v)]
        first_col_text = ' '.join(first_col_vals[:8])
        
        # Skip pollster/survey tables
        poll_kw = ['gms', 'infratest', 'ifop', 'ipsos', 'yougov', 'eurobarometer',
                    'election.de', 'europe elects', 'poll', 'survey',
                    'opinion poll', 'exit poll', 'forecast', 'projection']
        if any(kw in first_col_text for kw in poll_kw):
            continue
        
        # Skip summary/vote-type tables
        vote_kw = ['valid votes', 'invalid votes', 'blank votes', 'total votes',
                    'registered voters', 'turnout', 'total vote', 'nationwide']
        if sum(1 for kw in vote_kw if kw in first_col_text) >= 2:
            continue
        
        # Score: match against known regions
        matches = sum(1 for v in first_col_vals if v in known_regions)
        
        # Bonus for region keywords in column headers
        col_text = ' '.join(cols[:3]).lower()
        kw_bonus = sum(2 for kw in region_kw if kw in first_col_text or kw in col_text)
        
        # Bonus for numeric columns (party votes)
        numeric_cols = 0
        for col in t_flat.columns[1:6]:
            try:
                vals = pd.to_numeric(t_flat[col], errors='coerce')
                if vals.notna().sum() >= len(t_flat) * 0.3:
                    numeric_cols += 1
            except:
                pass
        
        score = matches * 10 + kw_bonus * 5 + numeric_cols * 3
        
        if score > best_score:
            best_score = score
            best = t_flat
    
    return best, best_score

def extract_results(table):
    """Extract district → party votes from a results table."""
    results = []
    
    for _, row in table.iterrows():
        region = str(row.iloc[0]).strip()
        if not region or region in ('nan', '', 'Total', 'Nationwide', 'Overall', 'Total seats'):
            continue
        # Skip footnote rows
        if region.startswith('[') or region.startswith('(') and region.endswith(')'):
            continue
        
        result = {'region': region}
        for col in table.columns[1:]:
            val = row[col]
            try:
                val_float = float(val)
                if pd.notna(val_float) and val_float >= 0:
                    party = col.strip().split('|')[0].strip()
                    party = re.sub(r'\s*\(.*?\)', '', party)
                    party = re.sub(r'\s*\[.*?\]', '', party)
                    party = party.strip()
                    if party and len(party) > 1 and party.lower() not in ('total', 'region', 'district'):
                        result[party] = val_float
            except (ValueError, TypeError):
                pass
        
        if len(result) > 1:  # Has at least one party result
            results.append(result)
    
    return results

def match_districts(results, known_regions):
    """Match Wikipedia region names to known district names."""
    matched = 0
    for r in results:
        name = r['region'].lower().strip()
        # Exact match
        if name in known_regions:
            r['_match'] = 'exact'
            matched += 1
            continue
        # Substring match (e.g., "London" matches "City of London")
        for kr in known_regions:
            if name in kr or kr in name:
                r['region'] = list(known_regions)[list(known_regions).index(kr)] if kr in known_regions else r['region']
                r['_match'] = 'substring'
                matched += 1
                break
        else:
            r['_match'] = 'unmatched'
    return matched

def store_results(db, iso, cfg, results):
    """Store election results in database."""
    table = cfg['results_table']
    c = db.cursor()
    
    # Create table (drop if exists for clean re-run)
    c.execute(f'DROP TABLE IF EXISTS {table}')
    
    # Collect all party names
    parties = set()
    for r in results:
        for k in r:
            if k not in ('region', '_match'):
                parties.add(k)
    parties = sorted(parties)
    
    # Create schema: region + party columns + metadata
    cols = ['region TEXT PRIMARY KEY']
    for p in parties:
        safe = re.sub(r'[^a-zA-Z0-9_]', '_', p.lower())[:50]
        cols.append(f'"{p}" REAL')
    cols.append('source TEXT')
    cols.append('election_date TEXT')
    
    db.execute(f'CREATE TABLE IF NOT EXISTS {table} ({", ".join(cols)})')
    
    # Insert (handle duplicates)
    for r in results:
        region = r['region']
        values = [region]
        for p in parties:
            values.append(r.get(p))
        values.append(cfg['wiki'])
        values.append(datetime.now().strftime('%Y-%m-%d'))
        
        placeholders = ','.join(['?' for _ in values])
        db.execute(f'INSERT OR REPLACE INTO {table} VALUES ({placeholders})', values)
    
    db.commit()
    
    # Register in catalog
    matched = sum(1 for r in results if r.get('_match') != 'unmatched')
    c.execute('''INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, row_count, source_date)
        VALUES (?,?,?,?,?,?,date('now'))''',
        (iso, table, 'election', 'district', cfg['election'], len(results)))
    
    return len(results), matched, len(parties)


# ── Main ─────────────────────────────────────────────────────────────

def process_country(db, iso, cfg):
    """Fetch and import election results for one country."""
    print(f'\n{"─"*60}')
    print(f'  {iso} {cfg["name"]} — {cfg["election"]}')
    print(f'{"─"*60}')
    
    # Load known regions
    known_regions = load_known_regions(db, iso)
    if known_regions:
        print(f'    Known regions: {len(known_regions):,}')
    else:
        print(f'    No church_election_{iso} table — skipping')
        return
    
    # Fetch Wikipedia
    try:
        html = fetch_wiki(cfg['wiki'])
    except Exception as e:
        print(f'    FAILED to fetch: {e}')
        return
    
    # Parse tables
    try:
        tables = pd.read_html(io.StringIO(html))
    except Exception as e:
        print(f'    FAILED to parse: {e}')
        return
    
    print(f'    Found {len(tables)} tables')
    
    # Find the results table
    table, score = find_election_table(tables, cfg, known_regions)
    if table is None or score < 1:
        print(f'    No suitable results table found (best score: {score})')
        # Debug: show first few tables
        for i, t in enumerate(tables[:5]):
            cols = list(t.columns)[:4]
            rows = len(t)
            print(f'      Table {i}: {rows} rows, cols={cols}')
        return
    
    print(f'    Selected table: {len(table)} rows, {len(table.columns)} cols (score={score})')
    
    # Extract results
    results = extract_results(table)
    print(f'    Extracted {len(results)} district results')
    
    # Match districts
    n_match = match_districts(results, known_regions)
    print(f'    Matched: {n_match}/{len(results)} districts')
    
    if n_match == 0:
        print(f'    WARNING: No district matches — storing anyway')
        # Show sample regions for debugging
        sample_regions = [r['region'] for r in results[:5]]
        sample_known = list(known_regions)[:5]
        print(f'    Sample Wikipedia: {sample_regions}')
        print(f'    Sample known:     {sample_known}')
    
    # Store
    rows, matched, n_parties = store_results(db, iso, cfg, results)
    log(f'  ✓ {cfg["name"]}: {rows} districts, {n_parties} parties, {matched} matched')


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--country', help='ISO code(s), comma-separated')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    
    t0 = time.time()
    db = sqlite3.connect(str(DB))
    
    # Select countries
    if args.country:
        selected = {iso.upper(): COUNTRIES[iso.upper()] 
                    for iso in args.country.split(',') if iso.upper() in COUNTRIES}
    else:
        selected = COUNTRIES
    
    print('=' * 60)
    print(f'  NATIONAL ELECTION IMPORT — {len(selected)} countries')
    print('=' * 60)
    
    if args.dry_run:
        for iso, cfg in sorted(selected.items()):
            print(f'  {iso}: {cfg["name"]} — {cfg["election"]} ({cfg["notes"]})')
        db.close()
        return
    
    success = 0
    for iso, cfg in sorted(selected.items()):
        try:
            process_country(db, iso, cfg)
            success += 1
        except Exception as e:
            print(f'    ERROR: {e}')
            import traceback
            traceback.print_exc()
    
    elapsed = time.time() - t0
    print(f'\n{"="*60}')
    print(f'  COMPLETE — {success}/{len(selected)} succeeded — {elapsed/60:.1f} min')
    db.close()

if __name__ == '__main__':
    main()
