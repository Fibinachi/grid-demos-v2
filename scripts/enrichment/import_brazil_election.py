#!/usr/bin/env python3
"""
Import Brazilian 2022 Presidential Election Results by Municipality.

Minimal, tested pipeline:
  1. Load IBGE→TSE municipality mapping (pre-built by build_brazil_municipio_mapping.py)
  2. Query TSE per-municipality API for churches in church_census_BR
  3. Build church_election_BR bridge + election_brazil_municipio_results

TSE API: /dados/{UF}/{UF}{TSE_CODE:05d}-c0001-e{ELECTION:06d}-v.json
  ELECTION 544 = 1st round president, 545 = 2nd round president
"""
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

DB = Path(r'E:\grid\churches.db')
DATA_DIR = Path(r'E:\grid\data\election')
CACHE_DIR = DATA_DIR / 'tse_municipios'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PRESIDENT_1ST = 544
PRESIDENT_2ND = 545
REQUEST_DELAY = 0.3
BATCH_SIZE = 500

CANDIDATE_NAMES = {
    '13': 'LULA', '22': 'JAIR BOLSONARO', '14': 'PADRE KELMON',
    '44': 'SORAYA THRONICKE', '15': 'SIMONE TEBET', '12': 'CIRO GOMES',
    '21': 'SOFIA MANZANO', '27': 'JOSE MARIA EYMAEL', '30': 'FELIPE D AVILA',
    '16': 'VERA LUCIA', '45': 'LEO PERICLES', '80': 'PABLO MARCAL',
}
ALL_CANDIDATES = list(CANDIDATE_NAMES.keys())

# Brazilian state name → abbreviation (unaccented lowercase)
STATE_ABBREV = {
    'acre': 'AC', 'alagoas': 'AL', 'amapa': 'AP', 'amazonas': 'AM',
    'bahia': 'BA', 'ceara': 'CE', 'distrito federal': 'DF',
    'espirito santo': 'ES', 'goias': 'GO', 'maranhao': 'MA',
    'mato grosso': 'MT', 'mato grosso do sul': 'MS', 'minas gerais': 'MG',
    'para': 'PA', 'paraiba': 'PB', 'parana': 'PR', 'pernambuco': 'PE',
    'piaui': 'PI', 'rio de janeiro': 'RJ', 'rio grande do norte': 'RN',
    'rio grande do sul': 'RS', 'rondonia': 'RO', 'roraima': 'RR',
    'santa catarina': 'SC', 'sao paulo': 'SP', 'sergipe': 'SE',
    'tocantins': 'TO',
}


def unaccent(text):
    """Remove accents from text."""
    replacements = {
        'á':'a','à':'a','ã':'a','â':'a','ä':'a',
        'é':'e','è':'e','ê':'e','ë':'e',
        'í':'i','ì':'i','î':'i','ï':'i',
        'ó':'o','ò':'o','õ':'o','ô':'o','ö':'o',
        'ú':'u','ù':'u','û':'u','ü':'u',
        'ç':'c',
        'Á':'A','À':'A','Ã':'A','Â':'A','Ä':'A',
        'É':'E','È':'E','Ê':'E','Ë':'E',
        'Í':'I','Ì':'I','Î':'I','Ï':'I',
        'Ó':'O','Ò':'O','Õ':'O','Ô':'O','Ö':'O',
        'Ú':'U','Ù':'U','Û':'U','Ü':'U',
        'Ç':'C',
    }
    for a, p in replacements.items():
        text = text.replace(a, p)
    return text


def state_to_abbrev(state_name):
    """Convert full Brazilian state name to 2-letter abbreviation."""
    if not state_name:
        return None
    name = unaccent(state_name.strip().lower())
    if name in STATE_ABBREV:
        return STATE_ABBREV[name]
    # Try first word match (e.g., "Rio de Janeiro" → "rio")
    first_word = name.split()[0]
    if first_word in STATE_ABBREV:
        return STATE_ABBREV[first_word]
    # Fallback: first 2 chars
    ab = state_name.strip()[:2].upper()
    return ab if len(ab) == 2 else None


def progress_bar(current, total, label=''):
    """Simple inline progress bar."""
    pct = current / total * 100 if total > 0 else 0
    bar_len = 40
    filled = int(bar_len * current / total) if total > 0 else 0
    bar = '#' * filled + '-' * (bar_len - filled)
    print(f'\r  {label} [{bar}] {current:,}/{total:,} ({pct:.0f}%)', end='', flush=True)
    if current >= total:
        print()


def fetch_municipio(session, uf, tse_code, election_code):
    """Fetch election results for one municipality. Returns JSON or None."""
    cache_file = CACHE_DIR / f'{uf}_{tse_code:05d}_e{election_code}.json'
    
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    
    url = (f'https://resultados.tse.jus.br/oficial/ele2022/{election_code}/dados/'
           f'{uf}/{uf}{tse_code:05d}-c0001-e{election_code:06d}-v.json')
    
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            with open(cache_file, 'w') as f:
                json.dump(data, f)
            return data
    except Exception:
        pass
    
    return None


def parse_municipio(data):
    """Parse TSE municipio JSON into flat dict with fields: e, tv, vv, vb, tvn, a, turnout_pct, winner, cand_N_*."""
    abr_list = data.get('abr', [])
    mun = None
    for a in abr_list:
        if a.get('tpabr') == 'MU':
            mun = a
            break
    if not mun:
        return {}
    
    entry = {}
    
    # Basic stats
    for field in ['e', 'tv', 'vv', 'vb', 'tvn', 'a']:
        try:
            entry[field] = int(mun.get(field, 0))
        except (ValueError, TypeError):
            entry[field] = 0
    
    # Turnout
    entry['turnout_pct'] = round(entry['tv'] / entry['e'] * 100, 1) if entry.get('e', 0) > 0 else 0.0
    
    # Candidates
    cands = mun.get('cand', [])
    top_votes = 0
    winner = None
    
    for c in cands:
        n = c.get('n', '')
        try:
            vap = int(c.get('vap', 0))
        except (ValueError, TypeError):
            vap = 0
        try:
            pvap = float(c.get('pvap', '0').replace(',', '.'))
        except (ValueError, TypeError):
            pvap = 0.0
        
        entry[f'cand_{n}_votes'] = vap
        entry[f'cand_{n}_pct'] = pvap
        entry[f'cand_{n}_name'] = CANDIDATE_NAMES.get(n, f'CAND_{n}')
        
        if vap > top_votes:
            top_votes = vap
            winner = CANDIDATE_NAMES.get(n, f'CAND_{n}')
    
    entry['winner'] = winner or 'UNKNOWN'
    return entry


def create_tables(db):
    """Create election tables, return column list."""
    fixed_cols = ['ibge_cod_mun']
    for rnd in (1, 2):
        pfx = f'round{rnd}_'
        fixed_cols.extend([
            f'{pfx}electorate', f'{pfx}total_votes', f'{pfx}valid_votes',
            f'{pfx}blank_votes', f'{pfx}null_votes', f'{pfx}abstentions',
            f'{pfx}turnout_pct', f'{pfx}winner',
        ])
        for cn in ALL_CANDIDATES:
            fixed_cols.extend([
                f'{pfx}cand_{cn}_votes', f'{pfx}cand_{cn}_pct', f'{pfx}cand_{cn}_name',
            ])
    
    col_defs = []
    for col in fixed_cols:
        if col == 'ibge_cod_mun':
            col_defs.append('ibge_cod_mun TEXT PRIMARY KEY')
        elif col.endswith('_pct'):
            col_defs.append(f'{col} REAL DEFAULT 0')
        elif any(col.endswith(s) for s in ('_votes', 'orate', 'tions')):
            col_defs.append(f'{col} INTEGER DEFAULT 0')
        elif any(col.endswith(s) for s in ('_name', 'winner')):
            col_defs.append(f'{col} TEXT DEFAULT \'\'')
        else:
            col_defs.append(f'{col} TEXT DEFAULT \'\'')
    
    db.executescript(f'''
        CREATE TABLE IF NOT EXISTS election_brazil_municipio_results (
            {', '.join(col_defs)},
            source TEXT DEFAULT 'tse_2022_api',
            import_date TEXT DEFAULT (date('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_ebmr_r1w ON election_brazil_municipio_results(round1_winner);
        CREATE INDEX IF NOT EXISTS idx_ebmr_r2w ON election_brazil_municipio_results(round2_winner);
    ''')
    
    db.executescript('''
        CREATE TABLE IF NOT EXISTS church_election_BR (
            church_rowid    INTEGER PRIMARY KEY,
            ibge_cod_mun    TEXT NOT NULL,
            setor_cod       TEXT,
            source_date     TEXT DEFAULT (date('now')),
            FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
        );
        CREATE INDEX IF NOT EXISTS idx_ce_br_mun ON church_election_BR(ibge_cod_mun);
    ''')
    
    return fixed_cols


def main():
    resume = '--resume' in sys.argv
    db = sqlite3.connect(str(DB), timeout=120)
    db.execute('PRAGMA journal_mode=WAL')
    
    # ── Step 1: Load mapping ──────────────────────────────────
    print('STEP 1: Loading IBGE-TSE mapping...')
    mapping_file = DATA_DIR / 'ibge_tse_mapping.json'
    if not mapping_file.exists():
        print('  ERROR: Run build_brazil_municipio_mapping.py first')
        return
    
    with open(mapping_file) as f:
        ibge_to_tse = json.load(f)  # {ibge_code: tse_code}
    print(f'  {len(ibge_to_tse):,} mappings loaded')
    
    # ── Step 2: Get church municipalities ──────────────────────
    print('\nSTEP 2: Getting unique municipalities from churches...')
    
    rows = db.execute('''
        SELECT DISTINCT
            SUBSTR(cc.setor_cod, 1, 7) as cd_mun,
            c.state
        FROM church_census_BR cc
        JOIN churches c ON cc.church_rowid = c.rowid
        WHERE cc.setor_cod IS NOT NULL
    ''').fetchall()
    
    print(f'  {len(rows):,} distinct (IBGE, state) pairs')
    
    # Build unique query list
    to_query = []
    seen_tse = set()
    no_tse = 0
    no_state = 0
    
    for ibge_code, state in rows:
        tse_code = ibge_to_tse.get(ibge_code)
        if not tse_code:
            no_tse += 1
            continue
        
        uf = state_to_abbrev(state)
        if not uf or len(uf) != 2:
            no_state += 1
            continue
        
        tse_int = int(tse_code)
        if tse_int not in seen_tse:
            seen_tse.add(tse_int)
            to_query.append((uf.lower(), tse_int, ibge_code))
    
    print(f'  {len(to_query):,} unique municipalities to query (2 rounds = {len(to_query)*2} API calls)')
    print(f'  No TSE mapping: {no_tse}  No valid state: {no_state}')
    
    if to_query:
        uf, tse, ibge = to_query[0]
        print(f'  Sample: {uf}{tse:05d} (IBGE={ibge})')
    
    # ── Step 3: Query TSE API ──────────────────────────────────
    eta_min = len(to_query) * 2 * REQUEST_DELAY / 60
    print(f'\nSTEP 3: Querying TSE API (ETA ~{eta_min:.0f} min)...')
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'GRID/1.0 (research project)'})
    
    results = {}  # tse_code → {round1_field: val, round2_field: val, ...}
    errors = 0
    done = 0
    
    for uf, tse_code, ibge_code in to_query:
        entry = {}
        
        for round_num, ec in [(1, PRESIDENT_1ST), (2, PRESIDENT_2ND)]:
            data = fetch_municipio(session, uf, tse_code, ec)
            if data:
                parsed = parse_municipio(data)
                if parsed:
                    for k, v in parsed.items():
                        entry[f'round{round_num}_{k}'] = v
            else:
                errors += 1
        
        if entry:
            results[tse_code] = entry
        
        done += 1
        if done % 100 == 0:
            progress_bar(done, len(to_query), 'Querying')
        time.sleep(REQUEST_DELAY)
    
    progress_bar(len(to_query), len(to_query), 'Querying')
    print(f'  Results: {len(results):,}  Errors: {errors}')
    
    if not results:
        print('  ERROR: No results obtained. Aborting.')
        db.close()
        return
    
    # ── Step 4: Build tables & insert ─────────────────────────
    print('\nSTEP 4: Creating tables and inserting results...')
    fixed_cols = create_tables(db)
    
    # Reverse mapping: TSE → IBGE
    tse_to_ibge = {int(v): k for k, v in ibge_to_tse.items()}
    
    db.execute('DELETE FROM election_brazil_municipio_results')
    
    batch = []
    inserted = 0
    
    for tse_code, entry in results.items():
        ibge_code = tse_to_ibge.get(tse_code)
        if not ibge_code:
            continue
        
        row = {'ibge_cod_mun': ibge_code}
        for col in fixed_cols:
            if col == 'ibge_cod_mun':
                continue
            default = 0 if '_votes' in col or 'orate' in col or 'tions' in col else \
                      0.0 if '_pct' in col else ''
            row[col] = entry.get(col, default)
        
        batch.append(row)
        
        if len(batch) >= BATCH_SIZE:
            cols = ', '.join(row.keys())
            ph = ', '.join([f':{k}' for k in row.keys()])
            db.executemany(
                f'INSERT OR REPLACE INTO election_brazil_municipio_results ({cols}) VALUES ({ph})',
                batch
            )
            db.commit()
            inserted += len(batch)
            batch = []
    
    if batch:
        row = batch[0]
        cols = ', '.join(row.keys())
        ph = ', '.join([f':{k}' for k in row.keys()])
        db.executemany(
            f'INSERT OR REPLACE INTO election_brazil_municipio_results ({cols}) VALUES ({ph})',
            batch
        )
        db.commit()
        inserted += len(batch)
    
    print(f'  Inserted {inserted:,} municipality results')
    
    # ── Step 5: Church bridge ─────────────────────────────────
    print('\nSTEP 5: Building church_election_BR bridge...')
    
    db.execute('DELETE FROM church_election_BR')
    
    bridge_count = db.execute('''
        INSERT INTO church_election_BR (church_rowid, ibge_cod_mun, setor_cod)
        SELECT cc.church_rowid, SUBSTR(cc.setor_cod, 1, 7), cc.setor_cod
        FROM church_census_BR cc
        WHERE cc.setor_cod IS NOT NULL
    ''').rowcount
    db.commit()
    
    coverage = db.execute('''
        SELECT COUNT(*) FROM church_election_BR ce
        JOIN election_brazil_municipio_results e ON ce.ibge_cod_mun = e.ibge_cod_mun
    ''').fetchone()[0]
    
    print(f'  {bridge_count:,} churches linked')
    print(f'  {coverage:,} have election data ({100*coverage/bridge_count:.1f}%)')
    
    # ── Step 6: Catalog ────────────────────────────────────────
    print('\nSTEP 6: Updating catalog and provenance...')
    
    result_count = db.execute('SELECT COUNT(*) FROM election_brazil_municipio_results').fetchone()[0]
    
    db.execute('''
        INSERT OR REPLACE INTO church_census_catalog
            (country, table_name, category, geo_unit, description, variable_count, row_count, refresh_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, date('now'))
    ''', ('BR', 'election_brazil_municipio_results', 'election', 'municipio',
          'TSE 2022 presidential election per municipality', len(fixed_cols), result_count))
    
    db.execute('''
        INSERT OR REPLACE INTO church_census_catalog
            (country, table_name, category, geo_unit, description, variable_count, row_count, refresh_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, date('now'))
    ''', ('BR', 'church_election_BR', 'election', 'bridge',
          'Church-to-municipio bridge for Brazil elections', 3, bridge_count))
    
    now = datetime.now().isoformat()
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted, fields_populated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'tse_2022_api',
        'import_brazil_election.py',
        now, now, 0, result_count,
        'round1_winner,round2_winner,turnout,candidate_votes',
        len(to_query), result_count,
        'completed',
        f'TSE 2022 presidential: {result_count} municipalities, {coverage} churches matched'
    ))
    db.commit()
    
    # ── Sample output ──────────────────────────────────────────
    print('\n=== SAMPLE RESULTS (top cities by votes) ===')
    for row in db.execute('''
        SELECT ibge_cod_mun, round1_winner, round1_turnout_pct,
               round1_cand_13_pct, round1_cand_22_pct,
               round2_winner, round2_cand_13_pct, round2_cand_22_pct
        FROM election_brazil_municipio_results
        WHERE round1_total_votes > 100000
        ORDER BY round1_total_votes DESC
        LIMIT 8
    ''').fetchall():
        lula1 = f'{row[3]:.1f}%' if row[3] else 'N/A'
        bolso1 = f'{row[4]:.1f}%' if row[4] else 'N/A'
        lula2 = f'{row[6]:.1f}%' if row[6] else 'N/A'
        bolso2 = f'{row[7]:.1f}%' if row[7] else 'N/A'
        print(f'  {row[0]} | R1:{row[1] or "":25s} L:{lula1:>6s} B:{bolso1:>6s} '
              f'({row[2] or 0:.1f}%) | R2:{row[5] or "":25s} L:{lula2:>6s} B:{bolso2:>6s}')
    
    db.close()
    
    print(f'\n{"="*60}')
    print(f'Brazil 2022 Election Import — DONE')
    print(f'  Municipalities with results: {result_count:,}')
    print(f'  Churches matched: {coverage:,} / {bridge_count:,} ({100*coverage/bridge_count:.1f}%)')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
