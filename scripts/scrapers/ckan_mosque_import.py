"""Generic CKAN open data portal importer for mosque datasets."""
import sqlite3, requests, sys, os, json, tempfile, time, re
from datetime import datetime, timezone
import pandas as pd

DB = r"E:\grid\churches.db"
HEADERS = {"User-Agent": "GRID/1.0 (research)"}
SCRIPT = "ckan_mosques"

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

def import_ckan_package(portal_url, package_id, country, source_name=None):
    """Import all resources from a CKAN package into source table."""
    conn = sqlite3.connect(DB, timeout=120)
    c = conn.cursor()
    
    # Get package info
    api_url = f"{portal_url}/api/3/action/package_show?id={package_id}"
    log(f"Fetching: {api_url}")
    try:
        r = requests.get(api_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        pkg = r.json()['result']
    except Exception as e:
        log(f"  API error: {e}")
        conn.close()
        return 0
    
    resources = pkg.get('resources', [])
    log(f"  {len(resources)} resources found")
    
    total = 0
    for res in resources:
        url = res.get('url', '')
        name = res.get('name', 'unknown')
        fmt = (res.get('format', '') or '').upper()
        
        if fmt not in ('XLS', 'XLSX', 'CSV', 'ODS'):
            log(f"  Skipping {name} ({fmt})")
            continue
        
        log(f"  Downloading: {name} ({fmt})")
        try:
            dl = requests.get(url, headers=HEADERS, timeout=60, allow_redirects=True)
            dl.raise_for_status()
        except Exception as e:
            log(f"    Download error: {e}")
            continue
        
        # Save to temp file
        ext = '.xlsx' if fmt in ('XLS', 'XLSX') else '.csv'
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp.write(dl.content)
        tmp.close()
        
        try:
            if ext == '.csv':
                df = pd.read_csv(tmp.name)
            else:
                df = pd.read_excel(tmp.name)
        except Exception as e:
            log(f"    Parse error: {e}")
            os.unlink(tmp.name)
            continue
        
        log(f"    {len(df)} rows, {len(df.columns)} columns: {', '.join(df.columns[:8])}")
        
        # Store in source table
        source_table = f"source_{source_name or portal_url.split('//')[1].split('.')[0]}_{package_id[:8]}"
        
        # Try to identify name, location, lat/lon columns
        name_col = location_col = lat_col = lon_col = None
        for col in df.columns:
            cl = col.lower().strip()
            if not name_col and any(w in cl for w in ('name', 'اسم', 'mosque', 'مسجد')):
                name_col = col
            if not location_col and any(w in cl for w in ('location', 'address', 'city', 'governorate', 'محافظة', 'مدينة', 'عنوان')):
                location_col = col
            if not lat_col and any(w in cl for w in ('lat', 'latitude', 'y', 'خط')):
                lat_col = col
            if not lon_col and any(w in cl for w in ('lon', 'long', 'lng', 'longitude', 'x', 'طول')):
                lon_col = col
        
        # Fallback: first text column = name, second = location
        if not name_col:
            name_col = df.columns[0]
        if not location_col and len(df.columns) > 1:
            location_col = df.columns[1]
        
        log(f"    Mapping: name='{name_col}', location='{location_col}', lat='{lat_col}', lon='{lon_col}'")
        
        # Store raw data as JSON in a source table
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS "{source_table}" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                church_id INTEGER,
                raw_data TEXT,
                name TEXT,
                location TEXT,
                lat REAL,
                lon REAL,
                source_url TEXT,
                imported_at TEXT DEFAULT (datetime('now'))
            )
        """)
        
        inserted = 0
        for _, row in df.iterrows():
            name_val = str(row[name_col]) if pd.notna(row[name_col]) else None
            if not name_val:
                continue
            
            lat_val = float(row[lat_col]) if lat_col and pd.notna(row[lat_col]) else None
            lon_val = float(row[lon_col]) if lon_col and pd.notna(row[lon_col]) else None
            loc_val = str(row[location_col]) if location_col and pd.notna(row[location_col]) else None
            
            c.execute(f"""
                INSERT INTO "{source_table}" (name, location, lat, lon, raw_data, source_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name_val[:500], loc_val[:500] if loc_val else None,
                  lat_val, lon_val, json.dumps(row.to_dict(), default=str), url))
            inserted += 1
        
        os.unlink(tmp.name)
        log(f"    Inserted {inserted} rows into {source_table}")
        total += inserted
    
    conn.commit()
    conn.close()
    return total

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python ckan_mosque_import.py <portal_url> <package_id> [country]")
        print("Example: python ckan_mosque_import.py https://opendata.gov.jo mosques-2490-2023 Jordan")
        sys.exit(1)
    
    portal = sys.argv[1].rstrip('/')
    pkg_id = sys.argv[2]
    country = sys.argv[3] if len(sys.argv) > 3 else 'Unknown'
    
    n = import_ckan_package(portal, pkg_id, country)
    log(f"\nDone. Total imported: {n}")
