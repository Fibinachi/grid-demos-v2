#!/usr/bin/env python3
"""
Mexico Census Data Pipeline
============================
Downloads, ingests, and spatially joins MX census data to churches.

Data sources:
  1. INEGI CPV 2020 ITER data (municipio-level census microdata)
     https://www.inegi.org.mx/programas/ccpv/2020/#Datos_abiertos
  2. INEGI Marco Geoestadístico municipios shapefile
     http://www.conabio.gob.mx/informacion/gis/maps/geo/mun22gw.zip

Steps:
  1. Download census CSV and municipio shapefile if not present
  2. Create municipio_census_mx table
  3. Load municipio boundaries into spatialite
  4. Spatial join: point-in-polygon for MX churches → church_enrichment
  5. Aggregate & verify results

Columns populated in church_enrichment:
  mx_division_id       — CVE_MUN (3-digit municipio code within state)
  mx_division_name     — NOM_MUN (municipio name)
  mx_admin_level       — 3 (municipio level)
  mx_admin_subtype     — 'municipio'

Usage:
    python scripts/geodata/mx_census_pipeline.py [--force-download]
"""

import argparse
import csv
import io
import os
import sqlite3
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_DIR))

DATA_DIR = PROJECT_DIR / "data"
SHP_DIR = DATA_DIR / "shapefiles"
MEXICO_DIR = DATA_DIR / "mexico_census"

DB_PATH = PROJECT_DIR / "churches.db"

# Shapefile URL (CONABIO mirror of INEGI MG 2022 municipios, geographic WGS84)
MUN_SHP_URL = "http://www.conabio.gob.mx/informacion/gis/maps/geo/mun22gw.zip"
MUN_SHP_DIR = SHP_DIR / "mun22gw"

# INEGI CPV 2020 ITER — National-level CSV zip
ITER_URL = "https://www.inegi.org.mx/contenidos/programas/ccpv/2020/datosabiertos/iter/iter_00_cpv2020_csv.zip"

# For the ITER per-state files (fallback / cross-check)
ITER_STATE_URLS = [
    f"https://www.inegi.org.mx/contenidos/programas/ccpv/2020/datosabiertos/iter/iter_{i:02d}_cpv2020_csv.zip"
    for i in range(1, 33)  # states 01–32
]

# ── INEGI state → INEGI code mapping (for joining) ─────────────────────────
# We'll derive this from the data itself (ENTIDAD column in ITER CSV)

# ── Helpers ────────────────────────────────────────────────────────────────

def download_file(url, dest_path, label="file"):
    """Download a file if not exists; returns True if downloaded."""
    if dest_path.exists():
        print(f"  ✓ {label} already exists: {dest_path.name}")
        return False
    print(f"  ↓ Downloading {label} from {url}...", end=" ", flush=True)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            content = resp.read()
        with open(dest_path, "wb") as f:
            f.write(content)
        print(f"OK ({len(content) / 1024 / 1024:.1f} MB)")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False


def unzip_file(zip_path, extract_dir):
    """Extract zip file to directory."""
    if extract_dir.exists():
        print(f"  ✓ Already extracted: {extract_dir}")
        return
    print(f"  Extracting {zip_path.name} to {extract_dir}...", end=" ", flush=True)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extract_dir)
    print(f"OK ({len(list(extract_dir.iterdir()))} files)")


# ── Step 1: Download & extract INEGI census data ──────────────────────────

def download_census_data(force=False):
    """Download and extract the INEGI 2020 ITER national CSV."""
    MEXICO_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = MEXICO_DIR / "iter_00_cpv2020_csv.zip"
    # The data CSV is inside a nested subdirectory within the ZIP
    csv_data_path = MEXICO_DIR / "iter_00_cpv2020" / "conjunto_de_datos" / "conjunto_de_datos_iter_00CSV20.csv"

    if force and zip_path.exists():
        zip_path.unlink()
    if csv_data_path.exists() and not force:
        print(f"  ✓ Census CSV already ready: {csv_data_path}")
        return csv_data_path

    download_file(ITER_URL, zip_path, "INEGI ITER national CSV")
    if not zip_path.exists():
        print("  ERROR: INEGI ITER download failed.")
        return None

    # Extract the whole ZIP preserving directory structure
    csv_data_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Extracting {zip_path.name}...", end=" ", flush=True)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(MEXICO_DIR)
    print("OK")

    if csv_data_path.exists():
        return csv_data_path

    # Fallback: search recursively
    print(f"  Searching for data CSV in {MEXICO_DIR}...", end=" ", flush=True)
    csv_files = list(MEXICO_DIR.rglob("conjunto_de_datos_iter_*.csv"))
    if csv_files:
        print(f"found: {csv_files[0].name}")
        return csv_files[0]
    
    print("not found!")
    return None


def download_census_data_by_state(force=False):
    """Fallback: download per-state ITER CSVs and concatenate."""
    MEXICO_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MEXICO_DIR / "iter_00_cpv2020_combined.csv"
    if out_path.exists() and not force:
        return out_path

    all_rows = []
    headers = None
    for url in ITER_STATE_URLS:
        zip_path = MEXICO_DIR / os.path.basename(url)
        download_file(url, zip_path, f"state ITER {os.path.basename(url)}")
        if not zip_path.exists():
            continue
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                csv_name = [n for n in zf.namelist() if n.endswith('.csv')]
                if not csv_name:
                    continue
                with zf.open(csv_name[0]) as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'))
                    if headers is None:
                        headers = reader.fieldnames
                    for row in reader:
                        all_rows.append(row)
        except Exception as e:
            print(f"    Error reading {zip_path.name}: {e}")

    if not all_rows:
        print("  ERROR: Could not download any INEGI ITER census data.")
        print("  Please download manually from:")
        print(f"    {ITER_URL}")
        print(f"  and extract to {MEXICO_DIR}")
        return None

    # Write combined
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"  Wrote combined CSV: {out_path} ({len(all_rows):,} rows)")
    return out_path


# ── Step 2: Create municipio_census_mx table ──────────────────────────────

CREATE_MUNICIPIO_CENSUS_SQL = """
CREATE TABLE IF NOT EXISTS municipio_census_mx (
    -- Geographic keys
    entidad_id      TEXT NOT NULL,   -- 2-digit state code (01-32)
    entidad_name    TEXT,            -- State name
    municipio_id    TEXT NOT NULL,   -- 3-digit municipio code within state
    municipio_name  TEXT,            -- Municipio name (NOM_MUN)
    full_id         TEXT NOT NULL,   -- 5-digit CONCAT(entidad_id, municipio_id)
    
    -- Population
    total_pop       REAL,            -- POBTOT
    male_pop        REAL,            -- POBMAS
    female_pop      REAL,            -- POBFEM
    
    -- Age breakdowns
    pop_0_2         REAL,            -- P_0A2
    pop_3_5         REAL,            -- P_3A5
    pop_6_11        REAL,            -- P_6A11
    pop_12_14       REAL,            -- P_12A14
    pop_15_17       REAL,            -- P_15A17
    pop_18_24       REAL,            -- P_18A24
    pop_25_59       REAL,            -- Sum of P_25A29..P_55A59
    pop_60_plus     REAL,            -- P_60YMAS
    
    -- Education
    pop_15plus_illiterate REAL,      -- P15YM_AN (15+ illiterate)
    avg_schooling_years   REAL,      -- GRAPROES (avg years of schooling)
    literacy_pct          REAL,      -- (P_15YMAS - P15YM_AN) / P_15YMAS * 100
    
    -- Housing
    total_housing       REAL,        -- VIVTOT
    occupied_housing    REAL,        -- VIVPAR_HAB
    avg_occupants       REAL,        -- OCUPVIVPAR (avg occupants per occupied)
    homes_with_computer REAL,        -- VPH_PC
    homes_with_internet REAL,        -- VPH_INTER
    homes_with_fridge   REAL,        -- VPH_REFRI
    homes_with_washing  REAL,        -- VPH_LAVAD
    homes_with_car      REAL,        -- VPH_AUTOM
    homes_dirt_floor    REAL,        -- VPH_PISODT
    
    -- Indigenous / language
    indig_pop           REAL,        -- P3YM_HLI (3+ year pop speaking indigenous lang)
    indig_pct           REAL,        -- Derived
    
    -- Religion counts
    catholic_pop        REAL,        -- PCATOLICA
    protestant_pop      REAL,        -- PRO_CRIEVA
    no_religion_pop     REAL,        -- PSIN_RELIG
    
    -- Religion percentages (derived)
    catholic_pct        REAL,
    protestant_pct      REAL,
    no_religion_pct     REAL,
    
    -- Ethnicity
    afro_descendant_pop REAL,        -- POB_AFRO
    
    -- Source
    census_year         INTEGER DEFAULT 2020,
    source              TEXT DEFAULT 'inegi_cpv2020_iter',
    updated_at          TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_municipio_census_mx_id 
    ON municipio_census_mx(full_id);
CREATE INDEX IF NOT EXISTS idx_municipio_census_mx_entidad 
    ON municipio_census_mx(entidad_id);
"""


def create_municipio_census_table(db):
    """Create the municipio_census_mx table if not exists."""
    print("  Creating municipio_census_mx table...", end=" ", flush=True)
    db.executescript(CREATE_MUNICIPIO_CENSUS_SQL)
    print("OK")


def get_iter_column_mapping():
    """Map INEGI ITER column names to our municipio_census_mx columns.
    
    INEGI CPV 2020 ITER uses Spanish column abbreviations. Key notes:
      - No single P_25A59 column; compute from 5-year buckets P_25A29..P_55A59
      - PCATOLICA = Catholic population
      - PRO_CRIEVA = Protestant/Evangelical (CRIE = Creyente = Believer)
      - PSIN_RELIG = No religion
      - P15YM_AN = Population 15+ illiterate (AN = Analfabeta)
      - VPH_PC = Homes with computer
      - VPH_INTER = Homes with internet
      - VPH_REFRI = Homes with refrigerator
    """
    return {
        'ENTIDAD': 'entidad_id',
        'NOM_ENT': 'entidad_name',
        'MUN': 'municipio_id',
        'NOM_MUN': 'municipio_name',
        'POBTOT': 'total_pop',
        'POBMAS': 'male_pop',
        'POBFEM': 'female_pop',
        'P_0A2': 'pop_0_2',
        'P_3A5': 'pop_3_5',
        'P_6A11': 'pop_6_11',
        'P_12A14': 'pop_12_14',
        'P_15A17': 'pop_15_17',
        'P_18A24': 'pop_18_24',
        # No P_25A59 — computed below from 5-year buckets
        'P_60YMAS': 'pop_60_plus',
        'GRAPROES': 'avg_schooling_years',
        'P15YM_AN': 'pop_15plus_illiterate',  # intermediate (not stored directly)
        'P_15YMAS': '_pop_15plus',   # intermediate for literacy calc
        'VIVTOT': 'total_housing',
        'VIVPAR_HAB': 'occupied_housing',
        'OCUPVIVPAR': 'avg_occupants',
        'VPH_PC': 'homes_with_computer',
        'VPH_INTER': 'homes_with_internet',
        'VPH_REFRI': 'homes_with_fridge',
        'VPH_LAVAD': 'homes_with_washing',
        'VPH_AUTOM': 'homes_with_car',
        'VPH_PISODT': 'homes_dirt_floor',
        'P3YM_HLI': 'indig_pop',
        'PCATOLICA': 'catholic_pop',
        'PRO_CRIEVA': 'protestant_pop',
        'PSIN_RELIG': 'no_religion_pop',
        'POB_AFRO': 'afro_descendant_pop',
    }


def ingest_census_csv(db, csv_path):
    """Load INEGI ITER CSV into municipio_census_mx, filtering to municipio-level rows only.
    
    INEGI ITER CSV has rows at multiple geographic levels identified by LOC:
      - LOC == 0, ENTIDAD == 0, MUN == 0 → National (drop)
      - LOC == 0, ENTIDAD > 0, MUN == 0 → State (drop)
      - LOC == 0, ENTIDAD > 0, MUN > 0 → **Municipio** (keep!)
      - LOC > 0 (or LOC in [9998, 9999]) → Locality (drop)
    """
    print(f"  Reading CSV: {csv_path}...", end=" ", flush=True)
    df = pd.read_csv(csv_path, encoding='utf-8-sig', low_memory=False)
    print(f"OK ({len(df):,} total rows, {len(df.columns)} columns)")

    # Convert all data columns to numeric (INEGI has mixed types in CSV)
    for c in df.columns:
        if c in ('NOM_ENT', 'NOM_MUN', 'NOM_LOC'):
            continue
        df[c] = pd.to_numeric(df[c], errors='coerce')

    # Identify municipio-level rows: LOC == 0, MUN > 0
    mun_rows = df[(df['LOC'] == 0) & (df['MUN'] > 0)].copy()
    print(f"  Municipio-level rows: {len(mun_rows):,}")

    if len(mun_rows) == 0:
        print("  ERROR: No municipio-level rows found!")
        return

    # Build full_id: ENTIDAD (2 digits) + MUN (3 digits)
    mun_rows['entidad_id'] = mun_rows['ENTIDAD'].astype(int).astype(str).str.zfill(2)
    mun_rows['municipio_id'] = mun_rows['MUN'].astype(int).astype(str).str.zfill(3)
    mun_rows['full_id'] = mun_rows['entidad_id'] + mun_rows['municipio_id']

    # ── Compute derived fields ──────────────────────────────────────────
    # 1. pop_25_59 from 5-year buckets
    age_25_59_cols = ['P_25A29', 'P_30A34', 'P_35A39', 'P_40A44',
                      'P_45A49', 'P_50A54', 'P_55A59']
    existing_age_cols = [c for c in age_25_59_cols if c in mun_rows.columns]
    if existing_age_cols:
        mun_rows['pop_25_59'] = mun_rows[existing_age_cols].sum(axis=1, min_count=1)

    # 2. literacy_pct = (P_15YMAS - P15YM_AN) / P_15YMAS * 100
    if 'P_15YMAS' in mun_rows.columns and 'P15YM_AN' in mun_rows.columns:
        literacy = (
            (mun_rows['P_15YMAS'] - mun_rows['P15YM_AN'])
            / mun_rows['P_15YMAS'].replace(0, np.nan) * 100
        )
        mun_rows['literacy_pct'] = literacy.clip(0, 100)

    # 3. indig_pct = P3YM_HLI / POBTOT * 100
    if 'P3YM_HLI' in mun_rows.columns and 'POBTOT' in mun_rows.columns:
        indig = mun_rows['P3YM_HLI'] / mun_rows['POBTOT'].replace(0, np.nan) * 100
        mun_rows['indig_pct'] = indig.clip(0, 100)

    # 4. religion percentages
    for rel_col, pct_name in [('PCATOLICA', 'catholic_pct'),
                               ('PRO_CRIEVA', 'protestant_pct'),
                               ('PSIN_RELIG', 'no_religion_pct')]:
        if rel_col in mun_rows.columns and 'POBTOT' in mun_rows.columns:
            pct = mun_rows[rel_col] / mun_rows['POBTOT'].replace(0, np.nan) * 100
            mun_rows[pct_name] = pct.clip(0, 100)

    # ── Map columns ─────────────────────────────────────────────────────
    col_map = get_iter_column_mapping()
    
    insert_cols = []
    for iter_col, our_col in col_map.items():
        if our_col.startswith('_'):
            continue  # intermediate, skip
        if our_col in ('entidad_id', 'municipio_id', 'full_id', 'entidad_name', 'municipio_name'):
            continue  # already set or set separately
        if iter_col in mun_rows.columns:
            insert_cols.append((our_col, iter_col))

    computed = ['pop_25_59', 'literacy_pct', 'indig_pct',
                'catholic_pct', 'protestant_pct', 'no_religion_pct']

    # ── Build records ───────────────────────────────────────────────────
    records = []
    for _, row in mun_rows.iterrows():
        rec = {
            'entidad_id': row['entidad_id'],
            'entidad_name': str(row.get('NOM_ENT', '')),
            'municipio_id': row['municipio_id'],
            'municipio_name': str(row.get('NOM_MUN', '')),
            'full_id': row['full_id'],
        }
        for our_col, iter_col in insert_cols:
            val = row.get(iter_col)
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                rec[our_col] = float(val)

        for comp_col in computed:
            if comp_col in mun_rows.columns:
                val = row.get(comp_col)
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    rec[comp_col] = float(val)

        rec['census_year'] = 2020
        rec['source'] = 'inegi_cpv2020_iter'
        records.append(rec)

    # ── Insert ───────────────────────────────────────────────────────────
    TABLE_COLS = [
        'entidad_id', 'entidad_name', 'municipio_id', 'municipio_name',
        'full_id', 'total_pop', 'male_pop', 'female_pop',
        'pop_0_2', 'pop_3_5', 'pop_6_11', 'pop_12_14', 'pop_15_17',
        'pop_18_24', 'pop_25_59', 'pop_60_plus',
        'pop_15plus_illiterate',
        'avg_schooling_years', 'literacy_pct',
        'total_housing', 'occupied_housing', 'avg_occupants',
        'homes_with_computer', 'homes_with_internet',
        'homes_with_fridge', 'homes_with_washing', 'homes_with_car',
        'homes_dirt_floor',
        'indig_pop', 'indig_pct',
        'catholic_pop', 'protestant_pop', 'no_religion_pop',
        'catholic_pct', 'protestant_pct', 'no_religion_pct',
        'afro_descendant_pop',
        'census_year', 'source',
    ]

    print(f"  Inserting {len(records):,} municipio records...", end=" ", flush=True)
    db.execute("BEGIN TRANSACTION")

    insert_sql = f"""INSERT OR REPLACE INTO municipio_census_mx 
        ({', '.join(TABLE_COLS)})
        VALUES ({', '.join(['?'] * len(TABLE_COLS))})"""

    batch = []
    for rec in records:
        batch.append(tuple(rec.get(c) for c in TABLE_COLS))
        if len(batch) >= 500:
            db.executemany(insert_sql, batch)
            batch = []
    if batch:
        db.executemany(insert_sql, batch)

    db.execute("COMMIT")
    print("OK")


# ── Step 3: Download & load municipio shapefile ────────────────────────────

def download_shapefile(force=False):
    """Download and extract municipios shapefile."""
    SHP_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = SHP_DIR / "mun22gw.zip"
    
    if force and zip_path.exists():
        zip_path.unlink()
    
    download_file(MUN_SHP_URL, zip_path, "Municipio shapefile")
    if not zip_path.exists():
        print("  ERROR: Municipio shapefile download failed.")
        return None
    
    unzip_file(zip_path, MUN_SHP_DIR)
    
    # Find .shp file
    shp_files = list(MUN_SHP_DIR.glob("*.shp"))
    if not shp_files:
        print(f"  ERROR: No .shp file found in {MUN_SHP_DIR}")
        return None
    return shp_files[0]


# ── Step 4: Spatial join and update church_enrichment ──────────────────────

def spatial_join_mx_churches(db, shp_path):
    """Load MX churches with coordinates, spatial join to municipios, update church_enrichment."""
    print("\n=== Spatial Join: MX Churches → Municipios ===\n")
    
    # Load MX churches
    print("Loading MX churches with coordinates...")
    churches_df = pd.read_sql_query(
        "SELECT id, latitude, longitude FROM churches "
        "WHERE country = 'MX' AND latitude IS NOT NULL AND longitude IS NOT NULL",
        db
    )
    print(f"  {len(churches_df):,} churches with coordinates")
    
    if len(churches_df) == 0:
        print("  ERROR: No MX churches with coordinates found.")
        return
    
    # Load municipio shapefile
    print(f"Loading municipio boundaries from {shp_path}...")
    mun_gdf = gpd.read_file(shp_path)
    # Ensure WGS84
    if mun_gdf.crs is None or mun_gdf.crs.to_epsg() != 4326:
        mun_gdf = mun_gdf.to_crs("EPSG:4326")
    print(f"  {len(mun_gdf):,} municipio polygons")
    print(f"  Columns: {list(mun_gdf.columns)}")
    print(f"  CRS: {mun_gdf.crs}")
    
    # Show sample rows
    print(f"  Sample columns: CVE_MUN={mun_gdf.get('CVE_MUN', ['?']).iloc[0] if 'CVE_MUN' in mun_gdf.columns else 'N/A'}, "
          f"NOM_MUN={mun_gdf.get('NOM_MUN', ['?']).iloc[0] if 'NOM_MUN' in mun_gdf.columns else 'N/A'}")
    
    # Create church GeoDataFrame
    church_gdf = gpd.GeoDataFrame(
        churches_df,
        geometry=gpd.points_from_xy(churches_df['longitude'], churches_df['latitude']),
        crs="EPSG:4326"
    )
    
    # Spatial join
    print("\nRunning point-in-polygon spatial join...")
    t0 = time.time()
    
    joined = gpd.sjoin(church_gdf, mun_gdf, how='left', predicate='within')
    
    elapsed = time.time() - t0
    matched = joined['index_right'].notna().sum()
    print(f"  Done in {elapsed:.1f}s — {matched:,} / {len(churches_df):,} "
          f"({matched / len(churches_df) * 100:.1f}%) churches matched to municipio")
    
    # Update church_enrichment table
    print("\nUpdating church_enrichment.mx_* fields...")
    
    # Determine the join key columns in the shapefile
    # INEGI CONABIO shapefile uses: CVE_ENT, CVE_MUN, NOMGEO (not NOM_MUN)
    cve_ent = 'CVE_ENT' if 'CVE_ENT' in mun_gdf.columns else 'ENTIDAD'
    cve_mun = 'CVE_MUN' if 'CVE_MUN' in mun_gdf.columns else 'MUN'
    name_col = 'NOMGEO' if 'NOMGEO' in mun_gdf.columns else ('NOM_MUN' if 'NOM_MUN' in mun_gdf.columns else 'MUNICIPIO')
    
    # Build update data: {church_id: (division_id, division_name)}
    updates = {}
    for _, row in joined.iterrows():
        church_id = row['id']
        if pd.notna(row.get('index_right')):
            entidad = str(row.get(cve_ent, '')).strip().zfill(2)
            municipio = str(row.get(cve_mun, '')).strip().zfill(3)
            division_id = entidad + municipio  # 5-digit full code
            division_name = str(row.get(name_col, ''))
            updates[church_id] = (division_id, division_name)
    
    if not updates:
        print("  No matches to update.")
        return
    
    # First ensure all matched churches have a church_enrichment row
    # (INSERT OR IGNORE for missing rows, then UPDATE)
    print(f"  Ensuring church_enrichment rows exist for {len(updates):,} churches...", end=" ", flush=True)
    db.execute("BEGIN TRANSACTION")
    db.executemany(
        "INSERT OR IGNORE INTO church_enrichment (church_id) VALUES (?)",
        [(ch_id,) for ch_id in updates.keys()]
    )
    db.execute("COMMIT")
    print("OK")
    
    # Batch update enrichment fields
    t0 = time.time()
    db.execute("BEGIN TRANSACTION")
    
    update_sql = """
        UPDATE church_enrichment 
        SET mx_division_id = ?,
            mx_division_name = ?,
            mx_admin_level = 3,
            mx_admin_subtype = 'municipio'
        WHERE church_id = ?
    """
    
    batch_size = 1000
    items = list(updates.items())
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        db.executemany(
            update_sql,
            [(div_id, div_name, ch_id) for ch_id, (div_id, div_name) in batch]
        )
    
    db.execute("COMMIT")
    elapsed = time.time() - t0
    print(f"  Updated {len(updates):,} church_enrichment rows in {elapsed:.1f}s")
    
    return updates


# ── Step 5: Verification ──────────────────────────────────────────────────

def verify_results(db):
    """Print summary of MX enrichment results."""
    print("\n=== Verification ===\n")
    
    cur = db.execute("""
        SELECT 
            COUNT(*) as total_churches,
            SUM(CASE WHEN ce.mx_division_id IS NOT NULL THEN 1 ELSE 0 END) as geocoded,
            SUM(CASE WHEN ch.latitude IS NULL THEN 1 ELSE 0 END) as no_coords
        FROM churches ch
        LEFT JOIN church_enrichment ce ON ch.id = ce.church_id
        WHERE ch.country = 'MX'
    """)
    row = cur.fetchone()
    total = row[0]
    geocoded = row[1] or 0
    no_coords = row[2] or 0
    print(f"MX churches: {total:,}")
    print(f"  Geocoded to municipio: {geocoded:,} ({geocoded / total * 100:.1f}%)")
    print(f"  Without coordinates:   {no_coords:,} ({no_coords / total * 100:.1f}%)")
    
    # Top municipios by church count
    cur = db.execute("""
        SELECT ce.mx_division_name, ce.mx_division_id, COUNT(*) as cnt
        FROM churches ch
        JOIN church_enrichment ce ON ch.id = ce.church_id
        WHERE ch.country = 'MX' AND ce.mx_division_id IS NOT NULL
        GROUP BY ce.mx_division_id
        ORDER BY cnt DESC
        LIMIT 20
    """)
    print(f"\nTop 20 municipios by church count:")
    for r in cur.fetchall():
        print(f"  {r[0]:35s} ({r[1]:5s}): {r[2]:,}")
    
    # Municipios with census data available
    cur = db.execute("SELECT COUNT(*) FROM municipio_census_mx")
    print(f"\nMunicipios with census data: {cur.fetchone()[0]:,}")
    
    # Cross-check: how many matched have census data
    cur = db.execute("""
        SELECT COUNT(*) 
        FROM (SELECT DISTINCT ce.mx_division_id FROM church_enrichment ce 
              JOIN churches ch ON ch.id = ce.church_id 
              WHERE ch.country = 'MX' AND ce.mx_division_id IS NOT NULL) m
        JOIN municipio_census_mx mc ON m.mx_division_id = mc.full_id
    """)
    print(f"Geocoded churches in municipios WITH census data: {cur.fetchone()[0]:,}")
    
    # Sample census data
    cur = db.execute("""
        SELECT full_id, entidad_name, municipio_name, total_pop, catholic_pop, protestant_pop, no_religion_pop
        FROM municipio_census_mx
        WHERE total_pop IS NOT NULL
        ORDER BY total_pop DESC
        LIMIT 5
    """)
    print(f"\nLargest 5 municipios by population:")
    for r in cur.fetchall():
        print(f"  {r[1]:25s} / {r[2]:30s}: {r[3]:>10,.0f} pop (Cath: {r[4]:>8,.0f} Prot: {r[5]:>8,.0f} NoRel: {r[6]:>8,.0f})")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MX Census Geocoding Pipeline")
    parser.add_argument('--force-download', action='store_true',
                        help='Force re-download of all data')
    args = parser.parse_args()
    
    t_start = time.time()
    print("=" * 60)
    print("MX CENSUS GEOCODING PIPELINE")
    print("=" * 60)
    
    # Connect DB
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=OFF")
    
    # Step 1: Download census data
    print("\n─── Step 1: Download INEGI 2020 Census Data ───")
    csv_path = download_census_data(force=args.force_download)
    if csv_path is None:
        print("ERROR: Cannot proceed without census CSV.")
        return 1
    
    # Step 2: Create table and ingest
    print("\n─── Step 2: Create municipio_census_mx table ───")
    create_municipio_census_table(db)
    
    # Check if already populated
    cur = db.execute("SELECT COUNT(*) FROM municipio_census_mx")
    count = cur.fetchone()[0]
    if count > 0 and not args.force_download:
        print(f"  municipio_census_mx already has {count:,} rows (use --force-download to re-ingest)")
    else:
        ingest_census_csv(db, csv_path)
    
    # Step 3: Download shapefile
    print("\n─── Step 3: Download Municipio Shapefile ───")
    shp_path = download_shapefile(force=args.force_download)
    if shp_path is None:
        print("ERROR: Cannot proceed without shapefile.")
        return 1
    
    # Step 4: Spatial join
    print("\n─── Step 4: Spatial Join ───")
    spatial_join_mx_churches(db, shp_path)
    
    # Step 5: Verify
    verify_results(db)
    
    db.close()
    
    total_elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"Pipeline complete in {total_elapsed / 60:.1f} minutes!")
    print(f"{'=' * 60}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
