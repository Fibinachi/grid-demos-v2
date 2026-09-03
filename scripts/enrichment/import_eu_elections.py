"""
Scrape subnational 2024 EU Parliament election results from Wikipedia.
Creates: election_eu2024_{ISO2}_results tables with province-level breakdowns.

Priority: DE, FR, IT, ES, AT — largest church counts with election bridges.
"""
import sqlite3, urllib.request, ssl, io, re, json
from datetime import datetime
from pathlib import Path
import pandas as pd

DB = r'E:\grid\churches.db'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Country config: Wikipedia page name, what to look for in tables
COUNTRIES = {
    'DE': {'page': 'Germany', 'region_kw': ['state', 'land', 'bundesland', 'lander'],
           'churches': 105431},
    'FR': {'page': 'France', 'region_kw': ['department', 'region', 'circonscription'],
           'churches': 92884},
    'IT': {'page': 'Italy', 'region_kw': ['region', 'circoscrizione', 'constituency'],
           'churches': 85996},
    'ES': {'page': 'Spain', 'region_kw': ['province', 'comunidad', 'region'],
           'churches': 49967},
    'AT': {'page': 'Austria', 'region_kw': ['state', 'land', 'bundesland'],
           'churches': 19721},
    'PT': {'page': 'Portugal', 'region_kw': ['district', 'region', 'circle'],
           'churches': 17302},
    'BE': {'page': 'Belgium', 'region_kw': ['province', 'region', 'constituency', 'college'],
           'churches': 14075},
    'DK': {'page': 'Denmark', 'region_kw': ['region', 'constituency', 'district'],
           'churches': 6665},
    'HR': {'page': 'Croatia', 'region_kw': ['county', 'region', 'constituency'],
           'churches': 5190},
}

def get_tables(iso, name):
    """Fetch Wikipedia page and parse tables."""
    url = f'https://en.wikipedia.org/wiki/2024_European_Parliament_election_in_{name}'
    req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0 (research)'})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        html = r.read().decode('utf-8')
    # Fix malformed colspan
    html = re.sub(r'colspan="[^"]*!', 'colspan="1', html)
    html = re.sub(r'colspan="[^"]*[^0-9"][^"]*"', 'colspan="1"', html)
    return pd.read_html(io.StringIO(html))

def flatten_cols(df):
    """Flatten multi-level columns."""
    cols = []
    for c in df.columns:
        if isinstance(c, tuple):
            parts = [str(x) for x in c if 'Unnamed' not in str(x) and str(x) != 'nan']
            cols.append(' | '.join(parts) if parts else str(c[0]))
        else:
            cols.append(str(c))
    df = df.copy()
    df.columns = cols
    return df

def load_known_regions(db, iso):
    """Load known region names from church_election table."""
    c = db.cursor()
    table = f'church_election_{iso}'
    if c.execute('SELECT COUNT(*) FROM sqlite_master WHERE name=?', (table,)).fetchone()[0]:
        names = set()
        for r in c.execute(f'SELECT DISTINCT LOWER(dist_name) FROM {table}'):
            n = r[0].strip().lower()
            names.add(n)
            # Add variants
            names.add(n.replace('-', ' '))
            names.add(n.replace('  ', ' '))
        return names
    return set()


def find_regional_table(tables, region_kw, known_regions):
    """Find the table most likely containing regional results."""
    best = None
    best_score = 0
    
    for t in tables:
        if t.shape[0] < 3 or t.shape[0] > 60:
            continue
        
        t_flat = flatten_cols(t)
        first_col_vals = [str(v).strip().lower() for v in t_flat.iloc[:, 0].values if pd.notna(v)]
        
        # Skip if first column looks like pollsters or dates
        pollster_kw = ['gms', 'infratest', 'ifop', 'ipsos', 'yougov', 'eurobarometer',
                       'election.de', 'europe elects', 'poll', 'survey', 'cluster']
        first_col_text = ' '.join(first_col_vals[:5])
        if any(kw in first_col_text for kw in pollster_kw):
            continue
        
        # Skip if rows look like vote types rather than regions
        vote_type_kw = ['valid votes', 'invalid votes', 'blank votes', 'total votes',
                        'registered voters', 'turnout', 'total vote']
        if any(kw in first_col_text for kw in vote_type_kw):
            continue
        
        # Score: match against known regions
        matches = sum(1 for v in first_col_vals if v in known_regions)
        
        # Bonus for numeric columns
        numeric_cols = 0
        for col in t_flat.columns[1:]:
            try:
                vals = pd.to_numeric(t_flat[col], errors='coerce')
                if vals.notna().sum() >= len(t_flat) * 0.4:
                    numeric_cols += 1
            except:
                pass
        
        score = matches * 10 + numeric_cols
        
        if score > best_score:
            best_score = score
            best = t_flat
    
    return best

def extract_region_results(table, region_kw):
    """Extract region name -> party vote shares from a table."""
    results = []
    
    for _, row in table.iterrows():
        # First column is region name
        region = str(row.iloc[0]).strip()
        if not region or region in ('nan', '', 'Total', 'Nationwide', 'Overall'):
            continue
        
        result = {'region': region}
        
        # Extract numeric columns as party results
        for col in table.columns[1:]:
            val = row[col]
            try:
                val_float = float(val)
                if pd.notna(val_float):
                    # Clean party name
                    party = col.strip().split('|')[0].strip()
                    party = re.sub(r'\s*\(.*?\)', '', party)  # Remove (parentheticals)
                    party = re.sub(r'\s*\[.*?\]', '', party)  # Remove [footnotes]
                    party = party.strip()
                    if party and len(party) > 1:
                        result[party] = val_float
            except (ValueError, TypeError):
                pass
        
        if len(result) > 1:  # Has at least one party result
            results.append(result)
    
    return results

def save_results(db, iso, results):
    """Save regional results to database. Does not modify input."""
    c = db.cursor()
    table = f'election_eu2024_{iso}_results'
    now = datetime.now().isoformat()
    
    c.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
        region TEXT PRIMARY KEY, results_json TEXT, election_year INTEGER DEFAULT 2024,
        source TEXT, import_date TEXT)""")
    c.execute(f'DELETE FROM {table}')
    
    data = []
    for r in results:
        r_copy = dict(r)
        region = r_copy.pop('region', str(r_copy))
        data.append((region, json.dumps(r_copy), 2024, 'wikipedia_eu2024', now))
    
    for i in range(0, len(data), 500):
        c.executemany(f'INSERT OR REPLACE INTO {table} VALUES (?,?,?,?,?)', data[i:i+500])
    db.commit()
    
    # Catalog
    c.execute("""INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, variable_count, row_count, source_date, refresh_date)
        VALUES (?, ?, 'election', 'region', ?, 2, ?, ?, ?)""",
        (iso, table, f'EU Parliament 2024 subnational results for {iso}', len(data), now[:10], now))
    db.commit()
    
    return len(data)


# ═══════════════════════════════════════
print('EU 2024 Subnational Results Importer')
print('=' * 60)

db = sqlite3.connect(DB)
total = 0

for iso, cfg in COUNTRIES.items():
    print(f'\n{iso} ({cfg["page"]}): ', end='', flush=True)
    
    try:
        tables = get_tables(iso, cfg['page'])
        known_regions = load_known_regions(db, iso)
        table = find_regional_table(tables, cfg['region_kw'], known_regions)
        
        if table is None:
            print(f'No regional table found (tried {len(tables)} tables)')
            continue
        
        results = extract_region_results(table, cfg['region_kw'])
        
        n_parties = len(results[0]) - 1  # minus region key
        n = save_results(db, iso, results)
        print(f'{n} regions ({n_parties} parties) from {table.shape[0]}x{table.shape[1]} table')
        if n >= 2:
            regions_sample = [r['region'] if 'region' in r else str(r) for r in results[:4]]
            print(f'  Regions: {", ".join(regions_sample)}...')
        total += n
        
    except Exception as e:
        print(f'FAILED: {e}')

db.close()
print(f'\n{"="*60}')
print(f'Imported: {total} regional results across countries')
print('Done.')
