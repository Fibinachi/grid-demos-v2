#!/usr/bin/env python3
"""
Build TN Religious Parcels staging database with churches-compatible schema.
Downloads all 95 TN county parcel ZIPs, extracts CLASS='05 RELIGIOUS' records,
and loads into a staging DB for local cleanup before merge into churches.db.

Usage:
  python scripts/ingest/build_tn_parcel_db.py --init        # Create DB schema only
  python scripts/ingest/build_tn_parcel_db.py --county NAME  # Download + parse one county
  python scripts/ingest/build_tn_parcel_db.py --all          # Download + parse all counties
  python scripts/ingest/build_tn_parcel_db.py --status       # Show progress
"""
import sqlite3, os, sys, re, zipfile, io, tempfile, urllib.request, time
from pathlib import Path
from collections import defaultdict

# ── Configuration ──
STAGING_DB = Path("E:/grid/data/tn_parcels/tn_religious_parcels.db")
DOWNLOAD_DIR = Path("E:/grid/data/tn_parcels/zips")
EXTRACT_DIR = Path("E:/grid/data/tn_parcels/extracted")
BASE_URL = "https://comptroller.tn.gov/content/dam/cot/pa/documents/landuse/maps/parcel-maps-data"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)

# TN counties (95)
TN_COUNTIES = [
    "Anderson", "Bedford", "Benton", "Bledsoe", "Blount", "Bradley", "Campbell",
    "Cannon", "Carroll", "Carter", "Cheatham", "Chester", "Claiborne", "Clay",
    "Cocke", "Coffee", "Crockett", "Cumberland", "Davidson", "Decatur", "DeKalb",
    "Dickson", "Dyer", "Fayette", "Fentress", "Franklin", "Gibson", "Giles",
    "Grainger", "Greene", "Grundy", "Hamblen", "Hamilton", "Hancock", "Hardeman",
    "Hardin", "Hawkins", "Haywood", "Henderson", "Henry", "Hickman", "Houston",
    "Humphreys", "Jackson", "Jefferson", "Johnson", "Knox", "Lake", "Lauderdale",
    "Lawrence", "Lewis", "Lincoln", "Loudon", "Macon", "Madison", "Marion",
    "Marshall", "Maury", "McMinn", "McNairy", "Meigs", "Monroe", "Montgomery",
    "Moore", "Morgan", "Obion", "Overton", "Perry", "Pickett", "Polk", "Putnam",
    "Rhea", "Roane", "Robertson", "Rutherford", "Scott", "Sequatchie", "Sevier",
    "Shelby", "Smith", "Stewart", "Sullivan", "Sumner", "Tipton", "Trousdale",
    "Unicoi", "Union", "Van Buren", "Warren", "Washington", "Wayne", "Weakley",
    "White", "Williamson", "Wilson",
]

# ── Field mapping: ASSESSMENT_DATA DBF → churches columns ──
# (DBF_index, churches_column, transform_fn)
FIELD_MAP = [
    # Owner → church name
    ("OWNER", "name", lambda v: clean_owner_name(v)),
    # Address
    ("ADDRESS", "address", lambda v: str(v).strip() if v else None),
    # City
    ("CITY", "city", lambda v: str(v).strip() if v and v != "000" else None),
    # State
    ("STATE", "state", lambda v: str(v).strip() if v else "TN"),
    # ZIP
    ("ZIP", "zip", lambda v: str(v).strip()[:10] if v else None),
    # Year built
    ("YRBLT", "building_year", lambda v: int(v) if v and int(v) > 0 else None),
    # Land use description
    ("LANDUSE", "notes", lambda v: f"LANDUSE: {str(v).strip()}" if v else None),
]


def clean_owner_name(owner):
    """Clean TN parcel owner name into a church name."""
    if not owner:
        return None
    o = str(owner).strip()
    if o == "0" or o == "":
        return None
    
    # Common patterns in TN owner data
    # "CHURCH FIRST BAPTIST" → "First Baptist Church"
    # "CEMETERY JONES" → "Jones Cemetery"
    # "ROMAN CATHOLIC DIOCESE" → "Roman Catholic Diocese"
    
    prefixes = ["CHURCH ", "CEMETERY ", "CHAPEL ", "TEMPLE ", "SYNAGOGUE ", "MOSQUE "]
    for p in prefixes:
        if o.upper().startswith(p):
            rest = o[len(p):].strip()
            ptype = p.strip().title()
            return f"{rest} {ptype}"
    
    return o


def get_db():
    """Get connection to staging DB."""
    conn = sqlite3.connect(str(STAGING_DB))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


# ════════════════════════════════════════════════════════════════════════
# INIT: Create staging DB with churches-compatible schema
# ════════════════════════════════════════════════════════════════════════

def init_staging_db():
    """Create the staging database with churches-compatible schema."""
    print(f"Creating staging DB: {STAGING_DB}")
    
    # Get churches schema from main DB
    main = sqlite3.connect("E:/grid/churches.db")
    church_schema = main.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='churches'"
    ).fetchone()
    main.close()
    
    if not church_schema:
        print("❌ Could not find churches table schema!")
        return
    
    conn = get_db()
    
    # Drop existing if any
    conn.execute("DROP TABLE IF EXISTS tn_religious_parcels")
    conn.execute("DROP TABLE IF EXISTS tn_import_log")
    
    # Create churches-compatible table (just the core columns we need)
    # Using the same column definitions as churches but starting fresh
    conn.execute("""
        CREATE TABLE tn_religious_parcels (
            id INTEGER PRIMARY KEY,
            name TEXT,
            name_original TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            zip5 TEXT,
            zip4 TEXT,
            country TEXT DEFAULT 'US',
            county TEXT,
            county_fips_5 TEXT,
            fips TEXT,
            latitude REAL,
            longitude REAL,
            geocode_source TEXT,
            address_source TEXT DEFAULT 'tn_comptroller_parcel',
            faith TEXT DEFAULT 'Christian',
            faith_id INT DEFAULT 2,
            taxonomy_id INT DEFAULT 2,
            tradition TEXT,
            tradition_id INT,
            movement_id INT,
            civilizational_family TEXT,
            legacy TEXT,
            source TEXT DEFAULT 'tn_parcel_import',
            confidence_score REAL DEFAULT 0.75,
            is_landmark INT DEFAULT 0,
            landmark_type TEXT DEFAULT 'church',
            building_year INTEGER,
            building_sqft REAL,
            building_source TEXT DEFAULT 'tn_assessment',
            capacity_estimate INTEGER,
            parking_spots INTEGER,
            closed_year INTEGER,
            continent TEXT DEFAULT 'North America',
            region_un TEXT DEFAULT 'Americas',
            subregion TEXT DEFAULT 'Northern America',
            notes TEXT,
            last_updated TEXT DEFAULT (datetime('now')),
            -- TN-specific columns
            tn_county TEXT,
            tn_parcel_id TEXT,
            tn_gislink TEXT,
            tn_class TEXT,
            tn_landuse TEXT,
            tn_owner_raw TEXT,
            tn_owner2 TEXT,
            tn_mail_addr TEXT,
            tn_mail_city TEXT,
            tn_mail_state TEXT,
            tn_mail_zip TEXT,
            tn_land_market_value REAL,
            tn_improvement_value REAL,
            tn_appraisal_value REAL,
            tn_assessment_value REAL,
            tn_sale_date TEXT,
            tn_sale_price REAL,
            tn_yrblt INTEGER,
            tn_stories INTEGER,
            tn_sqft INTEGER,
            tn_import_batch TEXT
        )
    """)
    
    # Create import log
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tn_import_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            county TEXT NOT NULL,
            total_parcels INTEGER,
            religious_parcels INTEGER,
            imported INTEGER,
            status TEXT,
            error_msg TEXT,
            started_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        )
    """)
    
    # Create indices
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tn_county ON tn_religious_parcels(tn_county)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tn_gislink ON tn_religious_parcels(tn_gislink)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tn_state ON tn_religious_parcels(state)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tn_name ON tn_religious_parcels(name)")
    
    conn.commit()
    conn.close()
    
    print("✅ Staging DB created with tn_religious_parcels table")


# ════════════════════════════════════════════════════════════════════════
# DOWNLOAD + PARSE: Process one county
# ════════════════════════════════════════════════════════════════════════

def download_county(county_name):
    """Download a county ZIP file. Returns path or None."""
    zip_path = DOWNLOAD_DIR / f"{county_name}.zip"
    
    if zip_path.exists():
        # Verify it's valid
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                if len(zf.namelist()) > 0:
                    return zip_path
        except:
            pass
        # Corrupt - re-download
        zip_path.unlink()
    
    url = f"{BASE_URL}/{county_name}.zip"
    print(f"  Downloading {county_name}...", end=" ", flush=True)
    
    try:
        urllib.request.urlretrieve(url, zip_path)
        size_kb = zip_path.stat().st_size / 1024
        print(f"{size_kb:.0f} KB")
        return zip_path
    except Exception as e:
        print(f"FAILED: {e}")
        if zip_path.exists():
            zip_path.unlink()
        return None


def parse_county(county_name, zip_path):
    """Extract religious parcels from a county ZIP. Returns list of dicts."""
    parcels = []
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Find the ASSESSMENT_DATA dbf
            dbf_name = None
            for name in zf.namelist():
                if "ASSESSMENT_DATA" in name.upper() and name.endswith('.dbf'):
                    dbf_name = name
                    break
            
            if not dbf_name:
                print(f"    ⚠ No ASSESSMENT_DATA.dbf found in {county_name}")
                return parcels
            
            # Extract DBF to memory and parse
            dbf_bytes = zf.read(dbf_name)
            
            # Also check for Parcels.dbf for geometry
            parcels_dbf = None
            for name in zf.namelist():
                if name.upper().endswith('/PARCELS.DBF') or name.upper() == 'PARCELS.DBF':
                    parcels_dbf = name
                    break
            
            # Parse using shapefile library
            import shapefile
            
            # Parse assessment data
            tmpdir = tempfile.mkdtemp()
            tmppath = os.path.join(tmpdir, 'assessment.dbf')
            with open(tmppath, 'wb') as f:
                f.write(dbf_bytes)
            
            try:
                sf = shapefile.Reader(tmppath)
                fields = [f[0] for f in sf.fields[1:]]  # Field names
                
                total = len(sf)
                religious = 0
                
                for rec in sf.iterRecords():
                    record = dict(zip(fields, rec))
                    cls = str(record.get("CLASS", "")).strip()
                    
                    if cls == "05 RELIGIOUS":
                        religious += 1
                        parcel = map_tn_to_churches(record, county_name)
                        parcels.append(parcel)
                
                print(f"    {total:,} total, {religious} religious → {len(parcels)} imported")
                
            finally:
                sf.close() if hasattr(sf, 'close') else None
                try:
                    os.remove(tmppath)
                    os.rmdir(tmpdir)
                except:
                    pass
                    
    except Exception as e:
        print(f"    ❌ Error parsing {county_name}: {e}")
    
    return parcels


def map_tn_to_churches(record, county_name):
    """Map a TN assessment record to a churches-compatible dict."""
    parcel = {
        "country": "US",
        "state": str(record.get("STATE", "TN")).strip() or "TN",
        "faith": "Christian",
        "faith_id": 2,
        "taxonomy_id": 2,
        "source": "tn_parcel_import",
        "confidence_score": 0.75,
        "is_landmark": 0,
        "landmark_type": "church",
        "continent": "North America",
        "region_un": "Americas",
        "subregion": "Northern America",
        "address_source": "tn_comptroller_parcel",
        "building_source": "tn_assessment",
        # TN-specific
        "tn_county": county_name,
        "tn_parcel_id": str(record.get("PARCELID", "")).strip(),
        "tn_gislink": str(record.get("GISLINK", "")).strip(),
        "tn_class": str(record.get("CLASS", "")).strip(),
        "tn_landuse": str(record.get("LANDUSE", "")).strip(),
        "tn_owner_raw": str(record.get("OWNER", "")).strip(),
        "tn_owner2": str(record.get("OWNER2", "")).strip(),
        "tn_mail_addr": str(record.get("MAILADDR", "")).strip(),
        "tn_mail_city": str(record.get("MAILCITY", "")).strip(),
        "tn_mail_state": str(record.get("STATE", "")).strip(),
        "tn_mail_zip": str(record.get("ZIP", "")).strip(),
    }
    
    # Map standard fields
    owner = str(record.get("OWNER", "")).strip()
    parcel["name"] = clean_owner_name(owner)
    parcel["name_original"] = owner if owner and owner != "0" else None
    
    addr = str(record.get("ADDRESS", "")).strip()
    parcel["address"] = addr if addr else None
    
    city = str(record.get("CITY", "")).strip()
    parcel["city"] = city if city and city != "000" else None
    
    zipcode = str(record.get("ZIP", "")).strip()
    parcel["zip"] = zipcode if zipcode else None
    if zipcode and len(zipcode) >= 5:
        parcel["zip5"] = zipcode[:5]
    
    yrblt = record.get("YRBLT")
    if yrblt and int(yrblt) > 0:
        parcel["building_year"] = int(yrblt)
        parcel["tn_yrblt"] = int(yrblt)
    
    # Valuation fields
    for tn_field, db_field in [
        ("LANDMKTVAL", "tn_land_market_value"),
        ("IMPVAL", "tn_improvement_value"),
        ("APPRAISAL", "tn_appraisal_value"),
        ("ASSESSMENT", "tn_assessment_value"),
    ]:
        val = record.get(tn_field)
        if val and float(val) > 0:
            parcel[db_field] = float(val)
    
    # Sale info
    sale_date = record.get("SALEDATE")
    if sale_date:
        parcel["tn_sale_date"] = str(sale_date)
    sale_price = record.get("PRICE")
    if sale_price and float(sale_price) > 0:
        parcel["tn_sale_price"] = float(sale_price)
    
    # Building details
    stories = record.get("STORIES")
    if stories and int(stories) > 0:
        parcel["tn_stories"] = int(stories)
    sfla = record.get("SFLA")
    if sfla and int(sfla) > 0:
        parcel["tn_sqft"] = int(sfla)
    
    # Notes: land use + any other info
    notes_parts = []
    landuse = str(record.get("LANDUSE", "")).strip()
    if landuse:
        notes_parts.append(f"LANDUSE: {landuse}")
    imp = str(record.get("IMP", "")).strip()
    if imp and imp != "0":
        notes_parts.append(f"IMP: {imp}")
    parcel["notes"] = "; ".join(notes_parts) if notes_parts else None
    
    return parcel


def import_county_parcels(county_name, parcels):
    """Insert parsed parcels into staging DB."""
    if not parcels:
        return 0
    
    conn = get_db()
    
    # Get next ID
    max_id = conn.execute(
        "SELECT COALESCE(MAX(id), 5000000) FROM tn_religious_parcels"
    ).fetchone()[0]
    
    from datetime import datetime
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Column order for INSERT
    columns = [
        "id", "name", "name_original",
        "address", "city", "state", "zip", "zip5", "zip4", "country",
        "county", "county_fips_5", "fips",
        "latitude", "longitude", "geocode_source", "address_source",
        "faith", "faith_id", "taxonomy_id",
        "tradition", "tradition_id", "movement_id",
        "civilizational_family", "legacy",
        "source", "confidence_score", "is_landmark", "landmark_type",
        "building_year", "building_sqft", "building_source",
        "capacity_estimate", "parking_spots", "closed_year",
        "continent", "region_un", "subregion", "notes",
        "tn_county", "tn_parcel_id", "tn_gislink",
        "tn_class", "tn_landuse",
        "tn_owner_raw", "tn_owner2",
        "tn_mail_addr", "tn_mail_city", "tn_mail_state", "tn_mail_zip",
        "tn_land_market_value", "tn_improvement_value",
        "tn_appraisal_value", "tn_assessment_value",
        "tn_sale_date", "tn_sale_price",
        "tn_yrblt", "tn_stories", "tn_sqft",
        "tn_import_batch",
    ]
    
    col_str = ", ".join(columns)
    placeholders = ", ".join(["?"] * len(columns))
    
    batch = []
    for i, p in enumerate(parcels):
        p["id"] = max_id + i + 1
        p["tn_import_batch"] = batch_id
        row = tuple(p.get(col) for col in columns)
        batch.append(row)
    
    sql = f"INSERT INTO tn_religious_parcels ({col_str}) VALUES ({placeholders})"
    conn.executemany(sql, batch)
    
    conn.commit()
    conn.close()
    
    return len(batch)


# ════════════════════════════════════════════════════════════════════════
# STATUS
# ════════════════════════════════════════════════════════════════════════

def print_status():
    """Print import status."""
    conn = get_db()
    
    # Check if table exists
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tn_religious_parcels'"
    ).fetchone()
    
    if not exists:
        print("❌ tn_religious_parcels table does not exist. Run --init first.")
        conn.close()
        return
    
    total = conn.execute("SELECT COUNT(*) FROM tn_religious_parcels").fetchone()[0]
    counties = conn.execute(
        "SELECT COUNT(DISTINCT tn_county) FROM tn_religious_parcels"
    ).fetchone()[0]
    
    print(f"\nTN Religious Parcels Status")
    print(f"{'='*50}")
    print(f"  Total religious parcels:  {total:,}")
    print(f"  Counties processed:       {counties} / 95")
    print(f"  DB location:              {STAGING_DB}")
    
    if total > 0:
        print(f"\n  By county (top 15):")
        for r in conn.execute("""
            SELECT tn_county, COUNT(*) as cnt 
            FROM tn_religious_parcels 
            GROUP BY tn_county 
            ORDER BY cnt DESC 
            LIMIT 15
        """):
            print(f"    {r[0]:25s} {r[1]:>6,}")
        
        print(f"\n  Names with no owner:")
        null_names = conn.execute(
            "SELECT COUNT(*) FROM tn_religious_parcels WHERE name IS NULL"
        ).fetchone()[0]
        print(f"    {null_names:,}")
        
        print(f"\n  Address coverage:")
        with_addr = conn.execute(
            "SELECT COUNT(*) FROM tn_religious_parcels WHERE address IS NOT NULL"
        ).fetchone()[0]
        print(f"    With address: {with_addr:,} ({with_addr/total*100:.1f}%)" if total else "    N/A")
        
        print(f"\n  Value summary:")
        for r in conn.execute("""
            SELECT 
                COUNT(CASE WHEN tn_appraisal_value > 0 THEN 1 END) as with_val,
                ROUND(AVG(CASE WHEN tn_appraisal_value > 0 THEN tn_appraisal_value END)) as avg_appr,
                ROUND(SUM(tn_appraisal_value)/1000000) as total_appr_m
            FROM tn_religious_parcels
        """):
            print(f"    With appraisal: {r[0]:,} | Avg: ${r[1]:,} | Total: ${r[2]:,}M")
    
    conn.close()


# ════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description="TN Religious Parcels Pipeline")
    parser.add_argument("--init", action="store_true", help="Create staging DB schema")
    parser.add_argument("--county", type=str, help="Download and parse one county")
    parser.add_argument("--all", action="store_true", help="Download and parse all 95 counties")
    parser.add_argument("--status", action="store_true", help="Show import status")
    parser.add_argument("--skip-download", action="store_true", help="Skip download, parse existing ZIPs")
    
    args = parser.parse_args()
    
    if args.init:
        init_staging_db()
        return
    
    if args.status:
        print_status()
        return
    
    if args.county:
        county = args.county
        print(f"\nProcessing {county} County...")
        
        # Init DB if needed
        if not STAGING_DB.exists():
            init_staging_db()
        
        # Download
        if not args.skip_download:
            zip_path = download_county(county)
            if not zip_path:
                print(f"❌ Failed to download {county}")
                return
        else:
            zip_path = DOWNLOAD_DIR / f"{county}.zip"
            if not zip_path.exists():
                print(f"❌ ZIP not found: {zip_path}")
                return
        
        # Parse
        parcels = parse_county(county, zip_path)
        
        # Import
        if parcels:
            n = import_county_parcels(county, parcels)
            print(f"  ✅ Imported {n} parcels from {county} County")
        
        print_status()
        return
    
    if args.all:
        print(f"\n{'='*60}")
        print("TN RELIGIOUS PARCELS — FULL PIPELINE (95 COUNTIES)")
        print(f"{'='*60}\n")
        
        # Init DB if needed
        if not STAGING_DB.exists():
            init_staging_db()
        
        t0 = time.time()
        total_imported = 0
        success = 0
        fail = 0
        
        for i, county in enumerate(TN_COUNTIES):
            t_county = time.time()
            print(f"[{i+1:3d}/{len(TN_COUNTIES)}] {county}:", end=" ", flush=True)
            
            # Check if already processed
            conn = get_db()
            existing = conn.execute(
                "SELECT COUNT(*) FROM tn_religious_parcels WHERE tn_county=?",
                (county,)
            ).fetchone()[0]
            conn.close()
            
            if existing > 0:
                print(f"⏭ Already imported ({existing} parcels)")
                total_imported += existing
                success += 1
                continue
            
            # Download
            zip_path = download_county(county)
            if not zip_path:
                fail += 1
                continue
            
            # Parse
            parcels = parse_county(county, zip_path)
            if parcels:
                n = import_county_parcels(county, parcels)
                total_imported += n
                success += 1
            
            elapsed_county = time.time() - t_county
            if elapsed_county > 5:
                print(f"      ({elapsed_county:.0f}s)")
        
        elapsed = time.time() - t0
        print(f"\n{'='*60}")
        print(f"COMPLETE: {success} counties, {fail} failed")
        print(f"Total religious parcels: {total_imported:,}")
        print(f"Time: {elapsed/60:.1f} min")
        
        print_status()
        return
    
    parser.print_help()


if __name__ == "__main__":
    main()
