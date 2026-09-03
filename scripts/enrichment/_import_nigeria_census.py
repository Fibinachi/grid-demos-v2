#!/usr/bin/env python3
"""
Nigeria Census Pipeline — DHS + WorldPop + geoBoundaries
=========================================================
Creates join tables for Nigeria churches at LGA and zone level.

Join pattern (NO new columns on churches table):
  churches ← church_census_NG.dist_code → lga_census_NG.dist_code
  churches ← church_census_NG.dist_code → lga_zone_map.dist_code → dhs_zone_NG.zone_name

Sources:
  - DHS API: 6-zone subnational indicators (fertility, education, health, household)
  - WorldPop 2020: 1km population grid -> LGA zonal stats
  - geoBoundaries: ADM1 (states) + ADM2 (LGAs)

Usage:
    python scripts/enrichment/_import_nigeria_census.py
"""
import io, json, os, sqlite3, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
from rasterstats import zonal_stats

PROJECT_DIR = Path('E:/grid')
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = PROJECT_DIR / 'churches.db'
DATA_DIR = PROJECT_DIR / 'data'
NG_DIR = DATA_DIR / 'nigeria_census'
NG_DIR.mkdir(parents=True, exist_ok=True)

GB_DIR = DATA_DIR / 'world_boundaries'
ADM2_PATH = GB_DIR / 'geoBoundaries-NGA-ADM2.geojson'
ADM1_PATH = GB_DIR / 'geoBoundaries-NGA-ADM1.geojson'

WORLDPOP_URL = 'https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/2020/NGA/nga_ppp_2020_1km.tif'
WORLDPOP_PATH = NG_DIR / 'nga_ppp_2020_1km_UNadj.tif'

DHS_API = 'https://api.dhsprogram.com/rest/dhs'

ZONE_STATES = {
    'North Central': ['Benue', 'Kogi', 'Kwara', 'Nasarawa', 'Niger', 'Plateau', 'Federal Capital Territory'],
    'North East': ['Adamawa', 'Bauchi', 'Borno', 'Gombe', 'Taraba', 'Yobe'],
    'North West': ['Jigawa', 'Kaduna', 'Kano', 'Katsina', 'Kebbi', 'Sokoto', 'Zamfara'],
    'South East': ['Abia', 'Anambra', 'Ebonyi', 'Enugu', 'Imo'],
    'South South': ['Akwa Ibom', 'Bayelsa', 'Cross River', 'Delta', 'Edo', 'Rivers'],
    'South West': ['Ekiti', 'Lagos', 'Ogun', 'Ondo', 'Osun', 'Oyo'],
}

DHS_INDICATORS = {
    'HC_MEMB_H_MNM': 'mean_household_size',
    'HC_HHHD_H_FEM': 'pct_female_headed_hh',
    'HC_AGEG_P_014': 'pct_age_0_14',
    'HC_AGEG_P_ADL': 'pct_age_10_19',
    'HC_AGEG_P_ADT': 'pct_age_18_plus',
    'HC_AGEG_P_SNR': 'pct_age_65_plus',
    'HC_AGEG_P_WRK': 'pct_age_15_64',
    'ED_EDUC_W_NED': 'pct_women_no_education',
    'ED_EDUC_W_SEC': 'pct_women_secondary_plus',
    'ED_EDUC_W_MYR': 'median_education_years_women',
    'ED_EDAT_B_MYR': 'median_education_years_both',
    'ED_EDAT_B_NED': 'pct_no_education_both',
    'ED_EDAT_B_HGH': 'pct_higher_education_both',
    'FE_FRTR_W_TFR': 'total_fertility_rate',
    'FE_CEBA_W_MNC': 'mean_children_ever_born',
    'FE_AAFB_W_M2B': 'median_age_first_birth_25_49',
    'MA_AAFM_W_M15': 'pct_married_by_15',
    'MA_AAFM_W_M18': 'pct_married_by_18',
    'CM_ECMR_C_U5M': 'under5_mortality',
    'CM_ECMR_C_IMR': 'infant_mortality',
    'CM_ECMR_C_NNR': 'neonatal_mortality',
    'CN_NUTS_C_HA2': 'pct_children_stunted',
    'CN_NUTS_C_WA2': 'pct_children_underweight',
    'CN_NUTS_C_WH2': 'pct_children_wasted',
    'FP_NADM_W_UNT': 'pct_unmet_need_fp',
    'FP_NADM_W_MNT': 'pct_met_need_fp',
    'RH_ANCN_W_AN1': 'pct_anc_1_visit',
    'RH_ANCN_W_AN4': 'pct_anc_4_visits',
    'RH_DELP_C_DEL': 'pct_delivery_health_facility',
    'CH_VACS_C_BAS': 'pct_basic_vaccination',
    'ML_NETP_C_ITN': 'pct_children_itn',
    'HA_HIVP_B_HIV': 'pct_hiv_positive',
    'HC_CHAR_P_UNW': 'population_unweighted',
    'HC_CHAR_H_UNW': 'households_unweighted',
}


def main():
    t0 = time.time()
    db = sqlite3.connect(str(DB_PATH), timeout=120)
    
    print("=" * 60)
    print("Nigeria Census Pipeline - DHS + WorldPop")
    print("=" * 60)
    
    # Step 0: Download ADM1 if needed
    if not ADM1_PATH.exists():
        print("\n[0] Downloading geoBoundaries ADM1 (states)...")
        url = 'https://github.com/wmgeolab/geoBoundaries/raw/main/releaseData/gbOpen/NGA/ADM1/geoBoundaries-NGA-ADM1.geojson'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=120) as resp:
                content = resp.read()
            with open(ADM1_PATH, 'wb') as f:
                f.write(content)
            print(f"  Downloaded {len(content)/1024/1024:.1f} MB")
        except Exception as e:
            print(f"  FAILED: {e}")
    
    # Step 1: Map LGAs to states to zones
    print("\n[1] Mapping LGAs -> States -> Zones...")
    adm2 = gpd.read_file(ADM2_PATH)
    print(f"  {len(adm2):,} ADM2 (LGAs)")
    
    state_zone_lookup = {}
    for zone, states in ZONE_STATES.items():
        for s in states:
            state_zone_lookup[s.lower()] = zone
    
    if ADM1_PATH.exists():
        adm1 = gpd.read_file(ADM1_PATH)
        print(f"  {len(adm1):,} ADM1 (states)")
        
        # Match ADM1 state names to our zone lookup
        adm1_names = adm1['shapeName'].tolist()
        print(f"  ADM1 state names: {adm1_names}")
        
        # Build state name mapping from ADM1
        for name in adm1_names:
            nl = name.lower().strip()
            matched = False
            for k in state_zone_lookup:
                if k in nl or nl in k:
                    matched = True
                    break
            if not matched:
                print(f"  WARNING: ADM1 state '{name}' not in zone lookup!")
        
        # Spatial join LGA centroid -> state
        adm2_c = adm2.copy()
        adm2_c['geometry'] = adm2.centroid
        joined = gpd.sjoin(adm2_c[['shapeID', 'shapeName', 'geometry']],
                          adm1[['shapeName', 'geometry']],
                          how='left', predicate='within')
        joined['state_name'] = joined['shapeName_right']
        joined['lga_name'] = joined['shapeName_left']
        
        def find_zone(sn):
            if pd.isna(sn): return None
            sn = str(sn).lower().strip()
            for k, v in state_zone_lookup.items():
                if k in sn or sn in k:
                    return v
            return None
        
        joined['zone_name'] = joined['state_name'].apply(find_zone)
        print(f"  LGA->State: {joined['state_name'].notna().sum()}/{len(joined)}")
        print(f"  LGA->Zone:  {joined['zone_name'].notna().sum()}/{len(joined)}")
    else:
        print("  No ADM1, using hardcoded mapping only")
        joined = adm2[['shapeID', 'shapeName']].copy()
        joined['lga_name'] = joined['shapeName']
        joined['state_name'] = None
        joined['zone_name'] = None
    
    # Step 2: WorldPop
    print("\n[2] WorldPop Population...")
    if not WORLDPOP_PATH.exists():
        print("  Downloading WorldPop Nigeria 2020...")
        try:
            req = urllib.request.Request(WORLDPOP_URL, headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=300) as resp:
                content = resp.read()
            with open(WORLDPOP_PATH, 'wb') as f:
                f.write(content)
            print(f"  Downloaded {len(content)/1024/1024:.1f} MB")
        except Exception as e:
            print(f"  FAILED: {e}")
    else:
        print(f"  Cached: {WORLDPOP_PATH.stat().st_size/1024/1024:.1f} MB")
    
    pop_data = {}
    if WORLDPOP_PATH.exists():
        print("  Zonal stats (may take a few minutes)...")
        adm2_r = adm2.to_crs('EPSG:4326')
        stats = zonal_stats(adm2_r.geometry, str(WORLDPOP_PATH),
                          stats=['sum'], nodata=-99999, all_touched=True)
        total_pop = 0
        for i, s in enumerate(stats):
            sid = str(adm2.iloc[i]['shapeID'])
            pop = round(s['sum']) if s['sum'] and s['sum'] > 0 else 0
            pop_data[sid] = pop
            total_pop += pop
            if (i + 1) % 200 == 0:
                print(f"    {i+1}/{len(stats)} LGAs...")
        print(f"    Total: {total_pop:,.0f}")
    
    # Step 3: DHS Zones
    print("\n[3] DHS Zone Indicators...")
    dhs_path = NG_DIR / 'nga_dhs_zones.csv'
    
    if not dhs_path.exists():
        zone_data = fetch_dhs_zones()
        if zone_data is not None:
            zone_data.to_csv(dhs_path, index=False)
    else:
        zone_data = pd.read_csv(dhs_path)
        print(f"  Cached: {len(zone_data)} rows")
    
    # Step 4: Create tables
    print("\n[4] Creating Join Tables...")
    create_lga_census(db, joined, pop_data)
    create_lga_zone_map(db, joined)
    if zone_data is not None and len(zone_data) > 0:
        create_dhs_zone(db, zone_data)
    update_catalog(db)
    
    # Step 5: Verify
    print("\n[5] Verification...")
    verify(db)
    
    now = datetime.now().isoformat()
    elapsed = time.time() - t0
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at, status, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ('nigeria_census_dhs_worldpop', '_import_nigeria_census.py',
          now, now, 'completed',
          f'NG LGA+zone census from DHS+WorldPop. {elapsed:.0f}s'))
    db.commit()
    db.close()
    
    print(f"\nDone! ({elapsed:.0f}s)")


def fetch_dhs_zones():
    """Fetch DHS indicators at zone level."""
    all_rows = []
    for iid, col_name in DHS_INDICATORS.items():
        url = (f'{DHS_API}/data?countryIds=NG&indicatorIds={iid}&breakdown=subnational&perpage=100')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            
            for row in data.get('Data', []):
                val = row.get('Value')
                try: val = float(val) if val else None
                except: val = None
                all_rows.append({
                    'zone_name': row.get('CharacteristicLabel', ''),
                    'indicator': col_name,
                    'value': val,
                    'survey_year': row.get('SurveyYear', ''),
                    'is_total': row.get('IsTotal', 0),
                })
        except Exception as e:
            print(f"  {iid}: {e}")
    
    if not all_rows:
        print("  No DHS data!")
        return None
    
    df = pd.DataFrame(all_rows)
    df_zones = df[df['is_total'] == 0].copy()
    
    pivot = df_zones.pivot_table(index='zone_name', columns='indicator',
                                 values='value', aggfunc='first').reset_index()
    pivot['country'] = 'NG'
    pivot['source'] = 'DHS API subnational'
    
    print(f"  Zones: {list(pivot['zone_name'])}")
    print(f"  Indicators: {len([c for c in pivot.columns if c not in ('zone_name','country','source')])}")
    return pivot


def create_lga_census(db, joined, pop_data):
    db.executescript('''
        DROP TABLE IF EXISTS lga_census_NG;
        CREATE TABLE lga_census_NG (
            dist_code       TEXT PRIMARY KEY,
            dist_name       TEXT NOT NULL,
            state_name      TEXT,
            zone_name       TEXT,
            total_pop       REAL,
            source          TEXT DEFAULT 'worldpop_2020',
            updated_at      TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_lga_census_state ON lga_census_NG(state_name);
        CREATE INDEX IF NOT EXISTS idx_lga_census_zone ON lga_census_NG(zone_name);
    ''')
    
    church_lgas = set(r[0] for r in db.execute('SELECT DISTINCT dist_code FROM church_census_NG'))
    
    rows = []
    for _, row in joined.iterrows():
        sid = str(row['shapeID'])
        if sid not in church_lgas:
            continue
        rows.append({
            'dist_code': sid,
            'dist_name': str(row['lga_name']),
            'state_name': str(row.get('state_name')) if pd.notna(row.get('state_name')) else None,
            'zone_name': str(row.get('zone_name')) if pd.notna(row.get('zone_name')) else None,
            'total_pop': pop_data.get(sid),
        })
    
    db.executemany('''
        INSERT OR IGNORE INTO lga_census_NG (dist_code, dist_name, state_name, zone_name, total_pop)
        VALUES (:dist_code, :dist_name, :state_name, :zone_name, :total_pop)
    ''', rows)
    
    tp = db.execute('SELECT SUM(total_pop) FROM lga_census_NG').fetchone()[0]
    print(f"  lga_census_NG: {len(rows):,} rows, pop sum: {tp:,.0f}" if tp else f"  lga_census_NG: {len(rows):,} rows")
    
    print("  Top LGAs by pop:")
    for r in db.execute('SELECT dist_name, state_name, total_pop FROM lga_census_NG ORDER BY total_pop DESC LIMIT 10'):
        p = f'{r[2]:,.0f}' if r[2] else 'N/A'
        print(f"    {r[0][:30]:30s} {str(r[1] or ''):20s} {p}")


def create_lga_zone_map(db, joined):
    db.executescript('''
        DROP TABLE IF EXISTS lga_zone_map;
        CREATE TABLE lga_zone_map (
            dist_code       TEXT PRIMARY KEY,
            state_name      TEXT,
            zone_name       TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_lga_zone_map_zone ON lga_zone_map(zone_name);
    ''')
    
    church_lgas = set(r[0] for r in db.execute('SELECT DISTINCT dist_code FROM church_census_NG'))
    rows = []
    for _, row in joined.iterrows():
        sid = str(row['shapeID'])
        if sid not in church_lgas: continue
        zn = row.get('zone_name')
        if pd.isna(zn): continue
        rows.append({
            'dist_code': sid,
            'state_name': str(row.get('state_name')) if pd.notna(row.get('state_name')) else None,
            'zone_name': str(zn),
        })
    
    db.executemany('INSERT OR IGNORE INTO lga_zone_map (dist_code, state_name, zone_name) VALUES (:dist_code, :state_name, :zone_name)', rows)
    
    zc = db.execute('SELECT zone_name, COUNT(*) FROM lga_zone_map GROUP BY zone_name').fetchall()
    print(f"  lga_zone_map: {len(rows):,} rows")
    for zn, cnt in zc:
        print(f"    {zn:20s}: {cnt:4d}")


def create_dhs_zone(db, zone_data):
    """Create dhs_zone_NG AND dhs_state_NG from DHS data.
    
    DHS returns both zone-level and state-level entries.
    State entries have '..' prefix (e.g., '..Abia').
    Zone entries have no prefix (e.g., 'North Central').
    """
    cols = [c for c in zone_data.columns if c not in ('zone_name','country','source','survey_year')]
    
    # Split into zones and states
    zone_rows_all = zone_data[~zone_data['zone_name'].str.startswith('..')].copy()
    state_rows_all = zone_data[zone_data['zone_name'].str.startswith('..')].copy()
    
    # Clean state names (remove '..' prefix)
    state_rows_all['state_name'] = state_rows_all['zone_name'].str.lstrip('.')
    
    # Filter to current zones only (exclude old 1990 zones like 'Northeast - 1990')
    current_zones = list(ZONE_STATES.keys())
    zone_rows = zone_rows_all[zone_rows_all['zone_name'].isin(current_zones)]
    
    print(f"  Zone rows: {len(zone_rows)} (filtered from {len(zone_rows_all)})")
    print(f"  State rows: {len(state_rows_all)}")
    
    # --- Create dhs_zone_NG ---
    db.executescript(f'''
        DROP TABLE IF EXISTS dhs_zone_NG;
        CREATE TABLE dhs_zone_NG (
            zone_name       TEXT PRIMARY KEY,
            country         TEXT DEFAULT 'NG',
            {", ".join(f"{c} REAL" for c in cols)},
            source          TEXT DEFAULT 'dhs_api_subnational',
            updated_at      TEXT DEFAULT (datetime('now'))
        );
    ''')
    
    zone_sql_cols = ", ".join(cols)
    zone_sql_vals = ", ".join(':' + c for c in cols)
    
    for _, row in zone_rows.iterrows():
        r = {'zone_name': str(row['zone_name']), 'country': 'NG'}
        for c in cols:
            r[c] = float(row[c]) if (c in row and pd.notna(row[c])) else None
        
        db.execute(f'''
            INSERT OR REPLACE INTO dhs_zone_NG (zone_name, country, {zone_sql_cols})
            VALUES (:zone_name, :country, {zone_sql_vals})
        ''', r)
    
    zc = db.execute('SELECT COUNT(*) FROM dhs_zone_NG').fetchone()[0]
    print(f"  dhs_zone_NG: {zc} zones, {len(cols)} indicators")
    
    print("  Zone sample:")
    for r in db.execute('SELECT zone_name, mean_household_size, total_fertility_rate, pct_women_no_education FROM dhs_zone_NG'):
        hh = f'{r[1]:.1f}' if r[1] else 'N/A'
        tfr = f'{r[2]:.1f}' if r[2] else 'N/A'
        edu = f'{r[3]:.0f}%' if r[3] else 'N/A'
        print(f"    {r[0][:20]:20s} HH:{hh:>5s} TFR:{tfr:>5s} NoEd(F):{edu:>6s}")
    
    # --- Create dhs_state_NG ---
    db.executescript(f'''
        DROP TABLE IF EXISTS dhs_state_NG;
        CREATE TABLE dhs_state_NG (
            state_name      TEXT PRIMARY KEY,
            country         TEXT DEFAULT 'NG',
            {", ".join(f"{c} REAL" for c in cols)},
            source          TEXT DEFAULT 'dhs_api_subnational',
            updated_at      TEXT DEFAULT (datetime('now'))
        );
    ''')
    
    state_sql_cols = ", ".join(cols)
    state_sql_vals = ", ".join(':' + c for c in cols)
    
    for _, row in state_rows_all.iterrows():
        r = {'state_name': str(row['state_name']), 'country': 'NG'}
        for c in cols:
            r[c] = float(row[c]) if (c in row and pd.notna(row[c])) else None
        
        db.execute(f'''
            INSERT OR REPLACE INTO dhs_state_NG (state_name, country, {state_sql_cols})
            VALUES (:state_name, :country, {state_sql_vals})
        ''', r)
    
    sc = db.execute('SELECT COUNT(*) FROM dhs_state_NG').fetchone()[0]
    print(f"  dhs_state_NG: {sc} states, {len(cols)} indicators")
    
    print("  State sample (top 5 by TFR):")
    for r in db.execute('SELECT state_name, mean_household_size, total_fertility_rate, pct_women_no_education FROM dhs_state_NG ORDER BY total_fertility_rate DESC LIMIT 5'):
        hh = f'{r[1]:.1f}' if r[1] else 'N/A'
        tfr = f'{r[2]:.1f}' if r[2] else 'N/A'
        edu = f'{r[3]:.0f}%' if r[3] else 'N/A'
        print(f"    {r[0][:30]:30s} HH:{hh:>5s} TFR:{tfr:>5s} NoEd(F):{edu:>6s}")


def update_catalog(db):
    entries = [
        ('lga_census_NG', 'census', 'LGA', 'Nigeria LGA pop from WorldPop 2020', 3),
        ('lga_zone_map', 'lookup', 'LGA', 'Nigeria LGA->State->Zone mapping', 3),
        ('dhs_zone_NG', 'census', 'zone', 'Nigeria DHS zone-level indicators', 34),
        ('dhs_state_NG', 'census', 'state', 'Nigeria DHS state-level indicators', 34),
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
    r = db.execute('''
        SELECT COUNT(*) FROM churches c
        JOIN church_census_NG cn ON c.rowid = cn.church_rowid
        WHERE c.country = 'NG'
    ''').fetchone()
    print(f"  Churches with LGA mapping: {r[0]:,}")
    
    r = db.execute('''
        SELECT COUNT(*) FROM churches c
        JOIN church_census_NG cn ON c.rowid = cn.church_rowid
        JOIN lga_zone_map zm ON cn.dist_code = zm.dist_code
        WHERE c.country = 'NG'
    ''').fetchone()
    print(f"  Churches with zone mapping: {r[0]:,}")
    
    print("\n  Zone breakdown:")
    print(f"  {'Zone':20s} {'Churches':>9s} {'HH Sz':>6s} {'TFR':>6s}")
    print(f"  {'-'*20} {'-'*9} {'-'*6} {'-'*6}")
    for r in db.execute('''
        SELECT zm.zone_name, COUNT(DISTINCT c.rowid),
               dz.mean_household_size, dz.total_fertility_rate
        FROM churches c
        JOIN church_census_NG cn ON c.rowid = cn.church_rowid
        JOIN lga_zone_map zm ON cn.dist_code = zm.dist_code
        LEFT JOIN dhs_zone_NG dz ON zm.zone_name = dz.zone_name
        WHERE c.country = 'NG'
        GROUP BY zm.zone_name ORDER BY COUNT(DISTINCT c.rowid) DESC
    '''):
        zn = r[0] or '?'
        ch = f'{r[1]:,}'
        hh = f'{r[2]:.1f}' if r[2] else '?'
        tf = f'{r[3]:.1f}' if r[3] else '?'
        print(f"  {zn:20s} {ch:>9s} {hh:>6s} {tf:>6s}")
    
    # State-level sample
    print(f"\n  State sample (churches with DHS state data):")
    for r in db.execute('''
        SELECT ds.state_name, ds.mean_household_size, ds.total_fertility_rate,
               COUNT(DISTINCT c.rowid) as churches
        FROM churches c
        JOIN church_census_NG cn ON c.rowid = cn.church_rowid
        JOIN lga_zone_map zm ON cn.dist_code = zm.dist_code
        JOIN dhs_state_NG ds ON zm.state_name = ds.state_name
        WHERE c.country = 'NG'
        GROUP BY ds.state_name
        ORDER BY churches DESC LIMIT 5
    '''):
        hh = f'{r[1]:.1f}' if r[1] else '?'
        tf = f'{r[2]:.1f}' if r[2] else '?'
        print(f"    {r[0][:30]:30s} {r[3]:,} churches  HH:{hh} TFR:{tf}")


if __name__ == '__main__':
    main()
