#!/usr/bin/env python3
"""
Match Mexican churches to INEGI 2020 Census AGEB (census tract) boundaries.

Uses INEGI Marco Geoestadistico 2020 shapefiles:
  - 00a.shp  (urban AGEBs, 81,451 polygons)
  - NNar.shp (rural AGEBs, per state)

Then enriches with AGEB-level demographic data from INEGI census CSVs.

Workflow:
1. Extract AGEB boundaries from MG2020 archives
2. Load Mexican churches with GPS coordinates
3. Point-in-polygon spatial join (urban + rural AGEBs)
4. Create church_census_mx table with CVEGEO + demographic variables
5. Log provenance
"""

import sqlite3
import geopandas as gpd
import pandas as pd
import numpy as np
import os
import sys
import time
import zipfile
import io
import csv
from datetime import datetime

DB_PATH = r'E:\grid\churches.db'
MG2020_DIR = r'E:\grid\data\inegi_mg2020'
MG2020_ZIP = os.path.join(MG2020_DIR, 'mg2020.zip')
EXTRACT_DIR = os.path.join(MG2020_DIR, 'extracted')
AGEB_CSV_DIR = os.path.join(MG2020_DIR, 'ageb_census_csv')

# State number -> ZIP name mapping
STATE_ZIP_MAP = {
    1: '01_aguascalientes', 2: '02_bajacalifornia', 3: '03_bajacaliforniasur',
    4: '04_campeche', 5: '05_coahuiladezaragoza', 6: '06_colima',
    7: '07_chiapas', 8: '08_chihuahua', 9: '09_ciudaddemexico',
    10: '10_durango', 11: '11_guanajuato', 12: '12_guerrero',
    13: '13_hidalgo', 14: '14_jalisco', 15: '15_mexico',
    16: '16_michoacandeocampo', 17: '17_morelos', 18: '18_nayarit',
    19: '19_nuevoleon', 20: '20_oaxaca', 21: '21_puebla',
    22: '22_queretaro', 23: '23_quintanaroo', 24: '24_sanluispotosi',
    25: '25_sinaloa', 26: '26_sonora', 27: '27_tabasco',
    28: '28_tamaulipas', 29: '29_tlaxcala', 30: '30_veracruzignaciodelallave',
    31: '31_yucatan', 32: '32_zacatecas'
}


# ============================================================================
# EXTRACT SHAPEFILES FROM MG2020 ARCHIVES
# ============================================================================

def extract_ageb_shapefiles():
    """
    Extract urban (00a) and rural (*ar) AGEB shapefiles from MG2020 archive.
    Returns path to directory containing .shp files.
    """
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    shp_dir = os.path.join(EXTRACT_DIR, 'ageb')
    os.makedirs(shp_dir, exist_ok=True)

    urban_shp = os.path.join(shp_dir, '00a.shp')
    if os.path.exists(urban_shp):
        print('AGEB shapefiles already extracted.')
        return shp_dir

    if not os.path.exists(MG2020_ZIP):
        print(f'ERROR: MG2020 ZIP not found at {MG2020_ZIP}')
        sys.exit(1)

    print('Extracting urban AGEB (00a) from MG_2020_Integrado.zip...')
    with zipfile.ZipFile(MG2020_ZIP) as zf:
        inner_data = zf.read('MG_2020_Integrado.zip')
        with zipfile.ZipFile(io.BytesIO(inner_data)) as inner:
            ageb_files = [n for n in inner.namelist() if n.startswith('conjunto_de_datos/00a')]
            for n in ageb_files:
                target = os.path.join(shp_dir, os.path.basename(n))
                with open(target, 'wb') as f:
                    f.write(inner.read(n))
            print(f'  Extracted {len(ageb_files)} files for urban AGEB')

        # Extract rural AGEB (*ar.shp) from all 32 state ZIPs
        print('Extracting rural AGEB (*ar.shp) from state ZIPs...')
        rural_count = 0
        for st_num in range(1, 33):
            st_name = STATE_ZIP_MAP[st_num]
            try:
                state_data = zf.read(f'{st_name}.zip')
                with zipfile.ZipFile(io.BytesIO(state_data)) as szf:
                    ar_shp = [n for n in szf.namelist() if 'ar' in n.lower() and n.endswith('.shp')]
                    if ar_shp:
                        ar_base = os.path.splitext(ar_shp[0])[0]
                        for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                            src = f'{ar_base}{ext}'
                            if src in szf.namelist():
                                target = os.path.join(shp_dir, os.path.basename(src))
                                if not os.path.exists(target):
                                    with open(target, 'wb') as f:
                                        f.write(szf.read(src))
                        rural_count += 1
            except Exception:
                pass

        print(f'  Extracted rural AGEB for {rural_count} states')

    return shp_dir


# ============================================================================
# LOAD AGEB BOUNDARIES
# ============================================================================

def load_ageb_boundaries(shp_dir):
    """Load all urban + rural AGEB shapefiles into one GeoDataFrame."""

    urban_shp = os.path.join(shp_dir, '00a.shp')
    gdf_list = []

    # Urban AGEBs
    if os.path.exists(urban_shp):
        print(f'Loading urban AGEB from 00a.shp...')
        urban = gpd.read_file(urban_shp)
        urban['ageb_type'] = 'urbana'
        print(f'  {len(urban):,} urban AGEB polygons')
        print(f'  Columns: {list(urban.columns)}')
        print(f'  CRS: {urban.crs}')
        gdf_list.append(urban)

    # Rural AGEBs
    rural_files = sorted([
        os.path.join(shp_dir, f) for f in os.listdir(shp_dir)
        if f.lower().endswith('ar.shp')
    ])
    if rural_files:
        print(f'\nLoading rural AGEB shapefiles ({len(rural_files)} files)...')
        for fpath in rural_files:
            try:
                rural = gpd.read_file(fpath)
                rural['ageb_type'] = 'rural'
                print(f'  {os.path.basename(fpath)}: {len(rural):,} polygons')
                gdf_list.append(rural)
            except Exception as e:
                print(f'  {os.path.basename(fpath)}: ERROR - {e}')
    else:
        print('  No rural AGEB files found.')

    if not gdf_list:
        print('ERROR: No AGEB shapefiles loaded.')
        return None

    # Merge all
    if len(gdf_list) == 1:
        merged = gdf_list[0]
    else:
        merged = pd.concat(gdf_list, ignore_index=True)

    print(f'\nTotal AGEB polygons: {len(merged):,}')
    print(f'  Urban: {len(merged[merged.ageb_type=="urbana"]):,}')
    print(f'  Rural: {len(merged[merged.ageb_type=="rural"]):,}')
    return merged


# ============================================================================
# LOAD CHURCHES
# ============================================================================

def load_churches(db):
    """Load Mexican church records with GPS coordinates."""
    print(f'\nLoading Mexican church records...')
    cur = db.execute("SELECT COUNT(*) FROM churches WHERE country = 'MX'")
    total = cur.fetchone()[0]

    cur = db.execute(
        "SELECT COUNT(*) FROM churches WHERE country = 'MX' AND latitude IS NOT NULL"
    )
    with_gps = cur.fetchone()[0]
    print(f'  Total Mexican churches: {total:,}')
    print(f'  With GPS coordinates: {with_gps:,} ({100*with_gps/total:.1f}%)')

    df = pd.read_sql_query(
        "SELECT rowid, id, name, city, state, latitude, longitude "
        "FROM churches WHERE country = 'MX' AND latitude IS NOT NULL",
        db
    )
    print(f'  Loaded {len(df):,} records.')
    return df


# ============================================================================
# SPATIAL JOIN
# ============================================================================

def do_spatial_join(churches_df, ageb_gdf):
    """Perform point-in-polygon spatial join."""
    print(f'\nRunning spatial join (church points -> AGEB polygons)...')
    t0 = time.time()

    churches_df = churches_df.copy()
    church_gdf = gpd.GeoDataFrame(
        churches_df,
        geometry=gpd.points_from_xy(churches_df.longitude, churches_df.latitude),
        crs='EPSG:4326'
    )

    # Reproject to AGEB CRS (ITRF_2008_LCC)
    print(f'  Reprojecting churches to {ageb_gdf.crs}...')
    church_gdf = church_gdf.to_crs(ageb_gdf.crs)

    # Spatial join
    join_cols = [c for c in ageb_gdf.columns if c != 'geometry']
    joined = gpd.sjoin(
        church_gdf,
        ageb_gdf[join_cols + ['geometry']],
        how='left',
        predicate='within'
    )

    # Deduplicate: some points match multiple overlapping polygons (urban/rural edges)
    # Keep first match, preferring urban over rural
    orig_count = len(joined)
    if 'rowid' in joined.columns:
        joined = joined.sort_values(['rowid', 'ageb_type'], ascending=[True, True])
        joined = joined.drop_duplicates(subset='rowid', keep='first')
        dupes = orig_count - len(joined)
        if dupes > 0:
            print(f'  Deduplicated: removed {dupes:,} overlapping matches')

    matched = joined['CVEGEO'].notna().sum()
    total = len(joined)
    elapsed = time.time() - t0
    print(f'  Matched: {matched:,} / {total:,} ({100*matched/total:.1f}%)')
    print(f'  Time: {elapsed:.1f}s')

    return joined


# ============================================================================
# LOAD CENSUS DEMOGRAPHIC DATA
# ============================================================================

def load_census_data():
    """
    Load AGEB demographic data from all 32 state CSVs.
    CSVs are at manzana (block) level; aggregate to AGEB level.
    Returns DataFrame keyed by (ENTIDAD, MUN, LOC, AGEB).
    """
    print(f'\nLoading AGEB census demographic data...')

    if not os.path.exists(AGEB_CSV_DIR):
        print(f'  WARNING: AGEB CSV dir not found at {AGEB_CSV_DIR}')
        return None

    csv_zips = sorted([f for f in os.listdir(AGEB_CSV_DIR) if f.endswith('.zip')])
    if not csv_zips:
        print(f'  WARNING: No CSV ZIPs found in {AGEB_CSV_DIR}')
        return None

    print(f'  Processing {len(csv_zips)} state CSV files...')

    # Demographic columns to aggregate (manzana -> AGEB level)
    agg_columns = [
        'POBTOT', 'POBFEM', 'POBMAS',
        'P_0A2', 'P_3YMAS', 'P_5YMAS', 'P_12YMAS', 'P_15YMAS', 'P_18YMAS',
        'P_3A5', 'P_6A11', 'P_8A14', 'P_12A14', 'P_15A17', 'P_18A24',
        'P_60YMAS', 'POB0_14', 'POB15_64', 'POB65_MAS',
        'P3YM_HLI', 'P3_HLI_HE', 'P3_HLI_NHE', 'P5_HLI',
        'POB_AFRO', 'PCON_DISC', 'PCON_LIMI',
        'P15PRI_IN', 'P15PRI_CO', 'P15SEC_IN', 'P15SEC_CO',
        'PEA', 'POCUPADA', 'PDESOCUP',
        'PCATOLICA', 'PRO_CRIEVA', 'POTRAS_REL', 'PSIN_RELIG',
        'TOTHOG', 'VIVTOT', 'TVIVHAB', 'OCUPVIVPAR',
        'GRAPROES',
    ]

    ageb_rows = []

    for czip_name in csv_zips:
        czip_path = os.path.join(AGEB_CSV_DIR, czip_name)
        try:
            with zipfile.ZipFile(czip_path) as zf:
                csv_name = [n for n in zf.namelist()
                           if 'conjunto_de_datos_ageb' in n and n.endswith('.csv')]
                if not csv_name:
                    continue

                with zf.open(csv_name[0]) as f:
                    raw = f.read()
                    try:
                        text = raw.decode('utf-8-sig')
                    except UnicodeDecodeError:
                        text = raw.decode('latin-1')
                    reader = csv.DictReader(io.StringIO(text))

                    # Aggregate by ENTIDAD + MUN + LOC + AGEB
                    ageb_agg = {}
                    for row in reader:
                        key = (row['ENTIDAD'], row['MUN'], row['LOC'], row['AGEB'])
                        if key not in ageb_agg:
                            ageb_agg[key] = {c: 0 for c in agg_columns}

                        for col in agg_columns:
                            val = row.get(col, '0').strip()
                            try:
                                ageb_agg[key][col] += int(val) if val else 0
                            except ValueError:
                                pass

                    for key, vals in ageb_agg.items():
                        ageb_rows.append({
                            'ENTIDAD': key[0], 'MUN': key[1],
                            'LOC': key[2], 'AGEB': key[3],
                            **vals
                        })

                    state_code = czip_name.split('_')[-1][:2]
                    print(f'    State {state_code}: {len(ageb_agg):,} AGEBs aggregated')

        except Exception as e:
            print(f'    {czip_name}: ERROR - {e}')

    if not ageb_rows:
        print('  No AGEB census data loaded.')
        return None

    census_df = pd.DataFrame(ageb_rows)
    print(f'\n  Total AGEB census records: {len(census_df):,}')
    print(f'  Columns: {list(census_df.columns[:15])}...')

    return census_df


# ============================================================================
# CREATE ENRICHMENT TABLE
# ============================================================================

def create_enrichment_table(db, joined, census_df=None):
    """
    Create church_census_mx table with AGEB + demographic data.
    """
    print('\nCreating church_census_mx table...')

    db.executescript('''
        CREATE TABLE IF NOT EXISTS church_census_mx (
            church_rowid    INTEGER PRIMARY KEY,
            cvegeo          TEXT,
            cve_ent         TEXT,
            cve_mun         TEXT,
            cve_loc         TEXT,
            cve_ageb        TEXT,
            ageb_type       TEXT,
            created_at      TEXT DEFAULT (date(\'now\')),
            FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
        );
    ''')

    geo_cols = ['CVEGEO', 'CVE_ENT', 'CVE_MUN', 'CVE_LOC', 'CVE_AGEB', 'ageb_type']

    demo_cols = []
    if census_df is not None:
        demo_cols = [c for c in census_df.columns
                    if c not in ('ENTIDAD', 'MUN', 'LOC', 'AGEB')]

    # Add demographic columns
    existing_cols = set(r[1].lower()
                       for r in db.execute('PRAGMA table_info(church_census_mx)'))

    for col in geo_cols + demo_cols:
        cl = col.lower()
        if cl not in existing_cols and cl not in ('church_rowid', 'created_at'):
            safe_type = 'INTEGER' if col in demo_cols else 'TEXT'
            if safe_type not in ('INTEGER', 'TEXT'):
                safe_type = 'TEXT'
            db.execute(f'ALTER TABLE church_census_mx ADD COLUMN "{col}" {safe_type}')

    # Clear old data
    db.execute('DELETE FROM church_census_mx')

    # Build census lookup: (ENTIDAD, MUN, LOC, AGEB) -> row
    census_lookup = {}
    if census_df is not None:
        for _, row in census_df.iterrows():
            key = (row['ENTIDAD'], row['MUN'], row['LOC'], row['AGEB'])
            census_lookup[key] = row

    all_value_cols = geo_cols + demo_cols
    insert_cols = ['church_rowid'] + all_value_cols
    placeholders = ','.join(['?' for _ in insert_cols])
    insert_sql = f'INSERT INTO church_census_mx ({",".join(insert_cols)}) VALUES ({placeholders})'

    rows = []
    for _, row in joined.iterrows():
        vals = [int(row['rowid'])]

        # Geo columns
        for col in geo_cols:
            v = row.get(col)
            if isinstance(v, (np.integer,)):
                v = str(v)
            elif isinstance(v, (np.floating,)):
                v = str(int(v)) if not np.isnan(v) else None
            elif pd.isna(v):
                v = None
            vals.append(v)

        # Census demographic data
        if census_df is not None and row.get('CVE_ENT') and row.get('CVE_AGEB'):
            lookup_key = (
                str(row['CVE_ENT']).zfill(2),
                str(row['CVE_MUN']).zfill(3) if pd.notna(row.get('CVE_MUN')) else '000',
                str(row['CVE_LOC']).zfill(4) if pd.notna(row.get('CVE_LOC')) else '0000',
                str(row['CVE_AGEB']).zfill(4) if pd.notna(row.get('CVE_AGEB')) else '0000',
            )
            census_row = census_lookup.get(lookup_key)
            if census_row is not None:
                for col in demo_cols:
                    vals.append(int(census_row.get(col, 0)))
            else:
                vals.extend([0 for _ in demo_cols])
        elif census_df is not None:
            vals.extend([0 for _ in demo_cols])

        rows.append(tuple(vals))

    db.executemany(insert_sql, rows)
    db.commit()

    # Stats
    cur = db.execute('SELECT COUNT(*) FROM church_census_mx')
    total_records = cur.fetchone()[0]
    cur = db.execute('SELECT COUNT(*) FROM church_census_mx WHERE cvegeo IS NOT NULL')
    matched = cur.fetchone()[0]

    print(f'  Inserted {len(rows):,} rows')
    print(f'  Matched to AGEB: {matched:,} / {total_records:,} ({100*matched/total_records:.1f}%)')

    if matched > 0:
        cur = db.execute('''
            SELECT ageb_type, COUNT(*) as cnt
            FROM church_census_mx
            WHERE cvegeo IS NOT NULL
            GROUP BY ageb_type
        ''')
        print('  By AGEB type:')
        for r in cur.fetchall():
            print(f'    {r[0]}: {r[1]:,}')

    return total_records, matched


# ============================================================================
# LOG PROVENANCE
# ============================================================================

def log_provenance(db, total_records, matched, census_loaded):
    """Log the enrichment operation in provenance_log."""
    now = datetime.now().isoformat()
    pragma = db.execute('PRAGMA table_info(provenance_log)').fetchall()
    pragma_cols = [r[1] for r in pragma]

    fields = 'cvegeo,cve_ent,cve_mun,cve_loc,cve_ageb,ageb_type'
    if census_loaded:
        fields += ',demographics'

    status = 'completed' if matched > 0 else 'partial'
    notes = f'Matched {matched:,}/{total_records:,} Mexican churches to INEGI 2020 AGEB boundaries'

    if 'records_attempted' in pragma_cols:
        db.execute('''
            INSERT INTO provenance_log
                (source, script_name, started_at, completed_at,
                 records_attempted, records_matched, fields_populated, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('inegi_mg2020', '_match_mexico_census_tracts.py',
              now, now, total_records, matched, fields, status, notes))
    else:
        db.execute('''
            INSERT INTO provenance_log
                (source, script_name, started_at, completed_at, status, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('inegi_mg2020', '_match_mexico_census_tracts.py',
              now, now, status, notes))
    db.commit()
    print('Provenance logged.')


# ============================================================================
# MAIN
# ============================================================================

def main():
    print('=' * 60)
    print('MEXICO CENSUS TRACT (AGEB) MATCHING')
    print('=' * 60)
    t_start = time.time()

    # Step 1: Extract shapefiles
    print('\n--- Step 1: Extract AGEB shapefiles ---')
    shp_dir = extract_ageb_shapefiles()

    # Step 2: Load AGEB boundaries
    print('\n--- Step 2: Load AGEB boundaries ---')
    ageb_gdf = load_ageb_boundaries(shp_dir)
    if ageb_gdf is None or len(ageb_gdf) == 0:
        print('FATAL: No AGEB boundaries loaded.')
        sys.exit(1)

    # Step 3: Load churches
    print('\n--- Step 3: Load Mexican churches ---')
    db = sqlite3.connect(DB_PATH)
    churches_df = load_churches(db)
    if len(churches_df) == 0:
        print('FATAL: No Mexican churches with GPS found.')
        db.close()
        sys.exit(1)

    # Step 4: Spatial join
    print('\n--- Step 4: Spatial join ---')
    joined = do_spatial_join(churches_df, ageb_gdf)

    # Step 5: Load census data
    print('\n--- Step 5: Load AGEB census demographics ---')
    census_df = load_census_data()

    # Step 6: Create enrichment table
    print('\n--- Step 6: Create enrichment table ---')
    total_records, matched = create_enrichment_table(db, joined, census_df)

    # Step 7: Log provenance
    print('\n--- Step 7: Log provenance ---')
    log_provenance(db, total_records, matched, census_df is not None)

    # Summary
    elapsed = time.time() - t_start
    print(f'\n{"=" * 60}')
    print('COMPLETE')
    print(f'{"=" * 60}')
    print(f'Total Mexican churches processed: {total_records:,}')
    if total_records > 0 and matched > 0:
        print(f'Matched to AGEB: {matched:,} ({100*matched/total_records:.1f}%)')
        print(f'Unmatched: {total_records - matched:,}')
    print(f'Census demographics: {"Yes" if census_df is not None else "No"}')
    print(f'Total time: {elapsed/60:.1f} min')
    print(f'\nEnrichment table: church_census_mx')

    db.close()


if __name__ == '__main__':
    main()
