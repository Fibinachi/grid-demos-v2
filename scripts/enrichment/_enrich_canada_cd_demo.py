#!/usr/bin/env python3
"""Canada Census Division demographics -> churches via DA->CD mapping."""
import sqlite3, zipfile
from datetime import datetime, date
import pandas as pd

DB = r'E:\grid\churches.db'
ZIP = r'E:\grid\data\canada_census\census_2021_da.csv'
SZ = 500

# Key CHARACTERISTIC_ID -> column name
KV = {'1':'pop_2021','2':'pop_2016','4':'dwellings_total','5':'dwellings_occupied',
      '6':'pop_density','7':'land_area_sqkm','47':'pop_0_14','72':'pop_15_64',
      '93':'pop_65plus','396':'avg_hh_size','669':'median_income_2020'}

def pb(i, n, label=''):
    p = i/n if n else 0
    b = chr(9608)*int(30*p)+chr(9617)*(30-int(30*p))
    print(f'\r  {label}: |{b}| {i:,}/{n:,} ({100*p:.1f}%)', end='', flush=True)
    if i>=n: print()

def main():
    # ═══ Step 1: Extract CD demographics ══════════════════════════════
    print('Reading census zip...')
    with zipfile.ZipFile(ZIP) as z:
        df = pd.read_csv(z.open('98-401-X2021004_English_CSV_data.csv'), encoding='latin-1', low_memory=False)
    cd = df[df.GEO_LEVEL == 'Census division'].copy()
    del df
    cd['cid'] = cd['CHARACTERISTIC_ID'].astype(str)
    cd = cd[cd.cid.isin(KV.keys())].copy()
    cd['var'] = cd.cid.map(KV)
    cd['val'] = pd.to_numeric(cd['C1_COUNT_TOTAL'], errors='coerce')
    
    piv = cd.pivot_table(index='DGUID', columns='var', values='val', aggfunc='first')
    del cd
    
    # Build DGUID -> CD name + PR+CD code (first 4 of DAUID)
    df2 = pd.read_csv(zipfile.ZipFile(ZIP).open('98-401-X2021004_English_CSV_data.csv'), 
                       encoding='latin-1', low_memory=False)
    cds = df2[df2.GEO_LEVEL=='Census division'][['DGUID','ALT_GEO_CODE','GEO_NAME']].drop_duplicates()
    # Map DGUID -> (prcd_code, name) where prcd_code is first 4 of DAUID
    dguid_map = {}
    for _, r in cds.iterrows():
        dguid = str(r.DGUID)
        # DGUID format: 2021A0003PPCC -> PR=PP, CD=CC
        if len(dguid) >= 13:
            pr_cd = dguid[9:11] + dguid[11:13]  # PP + CC
            dguid_map[dguid] = (pr_cd, str(r.GEO_NAME))
    del df2
    
    print(f'  CDs: {len(piv):,}, variables: {len(KV)}')
    
    # Build lookup: PRCD code (first 4 of DAUID) -> demographics
    cd_lookup = {}
    for dguid, row in piv.iterrows():
        dguid_str = str(dguid)
        if dguid_str in dguid_map:
            prcd_code, name = dguid_map[dguid_str]
            cd_lookup[prcd_code] = {
                'name': name,
                **{k: (float(row[k]) if pd.notna(row[k]) else None) for k in KV.values() if k in piv.columns}
            }
    
    # ═══ Step 2: Map churches to CD ═══════════════════════════════════
    db = sqlite3.connect(DB, timeout=120)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=60000')
    
    ch = db.execute('SELECT church_rowid, dauid FROM church_census_ca WHERE dauid IS NOT NULL').fetchall()
    print(f'  Churches with DA: {len(ch):,}')
    
    church_demo = {}
    for rid, dauid in ch:
        try:
            cd_code = str(int(float(dauid)))[:4]  # first 4 of DAUID = PR+CD
            if cd_code in cd_lookup:
                church_demo[rid] = (cd_code, cd_lookup[cd_code])
        except:
            pass
    
    print(f'  Matched: {len(church_demo):,}/{len(ch):,}')
    
    # ═══ Step 3: Create table & insert ═════════════════════════════════
    print('Creating church_census_ca_demo...')
    vcols = list(KV.values())
    db.execute('DROP TABLE IF EXISTS church_census_ca_demo')
    col_sql = ',\n  '.join(['church_rowid INTEGER PRIMARY KEY','cd_code TEXT','cd_name TEXT'] +
                           [f'{v} REAL' for v in vcols] +
                           ["source TEXT DEFAULT 'statcan_2021_cd'",
                            "source_date TEXT DEFAULT (date('now'))",
                            "FOREIGN KEY (church_rowid) REFERENCES churches(rowid)"])
    db.execute(f'CREATE TABLE church_census_ca_demo ({col_sql})')
    db.execute('CREATE INDEX IF NOT EXISTS idx_cad_cd ON church_census_ca_demo(cd_code)')
    
    rows = []
    for i, (rid, (cd_code, demo)) in enumerate(church_demo.items()):
        pb(i+1, len(church_demo), 'Inserting')
        vals = [demo.get(v) for v in vcols]
        rows.append((int(rid), cd_code, demo.get('name'), *vals, 'statcan_2021_cd', date.today().isoformat()))
        if len(rows) >= SZ:
            ph = ','.join(['?']*16)
            db.executemany(f'INSERT OR REPLACE INTO church_census_ca_demo VALUES ({ph})', rows)
            db.commit()
            rows = []
    if rows:
        ph = ','.join(['?']*16)
        db.executemany(f'INSERT OR REPLACE INTO church_census_ca_demo VALUES ({ph})', rows)
        db.commit()
    
    n = db.execute('SELECT COUNT(*) FROM church_census_ca_demo').fetchone()[0]
    print(f'\n  Inserted: {n:,}')
    
    # Catalog
    db.execute('INSERT OR REPLACE INTO church_census_catalog (country,table_name,category,geo_unit,description,variable_count,row_count,refresh_date) VALUES (?,?,?,?,?,?,?,date(?))',
               ('CA','church_census_ca_demo','census','CD','Canada Census 2021 CD-level demographics per church',3+len(vcols),n,'now'))
    
    # Verify
    print('\nTop CDs by church count:')
    for r in db.execute('SELECT cd_name, COUNT(*) n FROM church_census_ca_demo GROUP BY cd_name ORDER BY n DESC LIMIT 10'):
        print(f'  {str(r[0])[:40]:40s} {r[1]:,}')
    
    db.commit()
    db.close()
    print('Done!')

if __name__ == '__main__':
    main()
