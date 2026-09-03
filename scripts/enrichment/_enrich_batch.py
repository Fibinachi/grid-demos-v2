#!/usr/bin/env python3
"""
Batch electoral district spatial joins for remaining countries.

Countries: Germany, France, Australia, New Zealand, Singapore

Creates: church_election_{ISO2} tables following naming convention.
"""
import sqlite3
import io
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import urllib.request
import ssl

# Workaround for SSL cert issues with some government sites
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

DB = r'E:\grid\churches.db'
DATA_DIR = Path(r'E:\grid\data\election_boundaries')
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Source URLs for electoral boundary GeoJSON/GeoPackage downloads
SOURCES = {
    'DE': {
        'name': 'Germany Bundestag constituencies',
        'url': 'https://www.bundeswahlleiterin.de/bundestagswahlen/2025/wahlkreiseinteilung/downloads/btw25_wahlkreise_geo_shp.zip',
        'country': 'DE',
        'file': 'btw25_wahlkreise_geo_shp.zip',
        'format': 'zip_shp',
        'id_col': 'WKR_NR',
        'name_col': 'WKR_NAME',
        'table': 'church_election_DE',
        'geo_unit': 'wahlkreis',
        'description': 'Bundestag constituency 2025 per church'
    },
    'FR': {
        'name': 'France legislative circonscriptions',
        'url': 'https://www.data.gouv.fr/fr/datasets/r/efa8c2e6-b8f7-4594-ad01-10b46b06b56a',
        'country': 'FR',
        'file': 'circonscriptions_legislatives.geojson',
        'format': 'geojson',
        'id_col': 'ID',
        'name_col': 'nom_dpt',
        'table': 'church_election_FR',
        'geo_unit': 'circonscription',
        'description': 'Legislative circonscription per church (Sciences Po 2012/2017 boundaries)'
    },
    'AU': {
        'name': 'Australia electoral divisions',
        'url': 'https://www.aec.gov.au/electorates/gis/files/2021-Cwlth_electoral_boundaries_ESRI.zip',
        'country': 'AU',
        'file': 'au_electoral_2021.zip',
        'format': 'zip_shp',
        'id_col': 'ELECT_DIV',
        'name_col': 'ELECT_DIV',
        'table': 'church_election_AU',
        'geo_unit': 'division',
        'description': 'Federal electoral division per church'
    },
    'NZ': {
        'name': 'New Zealand general electorates',
        'url': None,  # Stats NZ requires API key — skip for now
        'country': 'NZ',
        'skip': True,
        'note': 'Stats NZ Data Service API required'
    },
    'SG': {
        'name': 'Singapore electoral divisions',
        'url': None,  # data.gov.sg API with dataset ID
        'country': 'SG',
        'skip': True,
        'note': 'Use data.gov.sg API — dataset d_7ddf956dfc1c59080bf95bba1c58a5d2'
    },
}


def download_file(info):
    """Download file if not already present."""
    dest = DATA_DIR / info['file']
    if dest.exists() and dest.stat().st_size > 1000:
        print(f'  Already downloaded: {info["file"]}')
        return dest
    
    print(f'  Downloading...')
    try:
        req = urllib.request.Request(info['url'], headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=300, context=ssl_ctx) as resp:
            with open(dest, 'wb') as f:
                f.write(resp.read())
        print(f'  Downloaded {dest.stat().st_size/1024/1024:.1f}MB')
        return dest
    except Exception as e:
        print(f'  Failed: {e}')
        return None


def process_country(db, info):
    """Download, spatial join, and create table for one country."""
    if info.get('skip'):
        print(f'\n  ⏭ SKIPPING {info["name"]}: {info.get("note", "")}')
        return
    
    print(f'\n{"="*60}')
    print(f'  {info["name"]}')
    print(f'{"="*60}')
    
    country = info['country']
    
    # Load churches
    churches_df = pd.read_sql_query(
        f"SELECT rowid, latitude, longitude FROM churches WHERE country='{country}' AND latitude IS NOT NULL",
        db
    )
    print(f'  Churches: {len(churches_df):,} with GPS')
    if len(churches_df) == 0:
        print('  No churches with GPS — skipping')
        return
    
    # Download
    dest = download_file(info)
    if not dest:
        return
    
    # Load boundaries
    print(f'  Loading boundaries...')
    if info['format'] == 'zip_shp':
        import zipfile, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(dest, 'r') as z:
                z.extractall(tmp)
            shp_files = list(Path(tmp).glob("**/*.shp"))
            if not shp_files:
                print(f'  No SHP found in archive')
                return
            gdf = gpd.read_file(shp_files[0])
    elif info['format'] == 'geojson':
        gdf = gpd.read_file(dest)
    else:
        print(f'  Unknown format: {info["format"]}')
        return
    
    print(f'  {len(gdf):,} features, CRS: {gdf.crs}')
    
    # Spatial join
    church_gdf = gpd.GeoDataFrame(
        {'church_rowid': churches_df['rowid'].values},
        geometry=gpd.points_from_xy(churches_df.longitude, churches_df.latitude),
        crs='EPSG:4326'
    )
    
    if church_gdf.crs != gdf.crs:
        church_gdf = church_gdf.to_crs(gdf.crs)
    
    id_col = info['id_col']
    name_col = info['name_col']
    
    # Find actual columns (may differ from expected)
    actual_id = id_col if id_col in gdf.columns else next((c for c in gdf.columns if 'code' in c.lower() or 'nr' in c.lower() or 'div' in c.lower()), gdf.columns[1])
    actual_name = name_col if name_col in gdf.columns else next((c for c in gdf.columns if 'name' in c.lower() or 'nom' in c.lower()), gdf.columns[2])
    
    print(f'  Using ID={actual_id}, Name={actual_name}')
    
    joined = gpd.sjoin(
        church_gdf,
        gdf[[actual_id, actual_name, 'geometry']],
        how='left',
        predicate='within'
    )
    matched = joined[actual_id].notna().sum()
    print(f'  Matched: {matched:,} / {len(joined):,} ({100*matched/len(joined):.1f}%)')
    
    # Create table
    table = info['table']
    db.executescript(f'''
        CREATE TABLE IF NOT EXISTS {table} (
            church_rowid    INTEGER PRIMARY KEY,
            dist_code       TEXT,
            dist_name       TEXT,
            source          TEXT DEFAULT '',
            source_date     TEXT DEFAULT (date('now')),
            FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
        );
        CREATE INDEX IF NOT EXISTS idx_{table}_code ON {table}(dist_code);
    ''')
    
    db.execute(f'DELETE FROM {table}')
    
    result = joined[['church_rowid', actual_id, actual_name]].dropna(subset=[actual_id]).copy()
    rows = [(int(r.church_rowid), str(getattr(r, actual_id)), str(getattr(r, actual_name))) 
            for r in result.itertuples()]
    
    db.executemany(
        f'INSERT INTO {table} (church_rowid, dist_code, dist_name, source) VALUES (?,?,?,?)',
        [(r[0], r[1], r[2], info['name']) for r in rows]
    )
    db.commit()
    print(f'  Inserted {len(rows):,} rows')
    
    # Catalog
    rc = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    db.execute('''
        INSERT OR REPLACE INTO church_census_catalog
            (country, table_name, category, geo_unit, description, variable_count, row_count, refresh_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, date('now'))
    ''', (country, table, 'election', info['geo_unit'], info['description'], 3, rc))
    db.commit()
    
    # Provenance
    now = datetime.now().isoformat()
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted, fields_populated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        f'election_{country.lower()}',
        '_enrich_batch.py',
        now, now, 0, len(rows),
        'dist_code,dist_name',
        len(churches_df), matched,
        'completed',
        f'{info["name"]}: {matched}/{len(churches_df)} churches enriched'
    ))
    db.commit()


def main():
    db = sqlite3.connect(DB, timeout=120)
    
    for key in ['DE', 'FR', 'AU']:  # NZ and SG need API keys
        try:
            process_country(db, SOURCES[key])
        except Exception as e:
            print(f'  ❌ {key} failed: {e}')
    
    # NZ and SG noted
    for key in ['NZ', 'SG']:
        info = SOURCES[key]
        print(f'\n  ⏭ {info["name"]}: {info.get("note", "")}')
    
    db.close()
    print(f'\n{"="*60}')
    print('BATCH COMPLETE')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
