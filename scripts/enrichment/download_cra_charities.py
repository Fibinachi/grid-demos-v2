
"""Download CRA Charities Directorate data and import Canadian religious orgs.
CRA Charities Listings = Canadian equivalent of IRS EO BMF.
Source: https://open.canada.ca/data/en/dataset/4f0f9ee-eb6b-4bb8-8f2b-b6e5f5a1c4e0

Key fields: BN (Business Number), charity name, address, city, province,
postal code, charity type, category (0001=religion), revenue, expenses, assets.

Usage:
    python scripts/enrichment/download_cra_charities.py           # full download
    python scripts/enrichment/download_cra_charities.py --dry-run  # preview
"""
import csv, io, os, re, sqlite3, sys, time, urllib.request, zipfile
from datetime import datetime

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT, 'churches.db')
DATA_DIR = os.path.join(PROJECT, 'data', 'cra')
os.makedirs(DATA_DIR, exist_ok=True)

DRY_RUN = '--dry-run' in sys.argv

# CRA open data portal URLs
# The bulk data zip containing all registered charities
CRA_ZIP_URL = 'https://apps.cra-arc.gc.ca/ebci/hacc/disp_pb/0896/1_2023_10_01_t3010.zip'

# Alternative: direct CSV from open.canada.ca
CRA_CSV_URL = 'https://open.canada.ca/data/dataset/4f0f9ee-eb6b-4bb8-8f2b-b6e5f5a1c4e0/resource/7d9e1c1c-5b5c-4f43-8cf6-6e1d4b9c7f3a/download/charities.csv'

def log(msg):
    print(f"  {msg}", flush=True)

def download_cra():
    """Download CRA charities data. Try zip first, fall back to CSV."""
    zip_path = os.path.join(DATA_DIR, 'cra_charities.zip')
    csv_path = os.path.join(DATA_DIR, 'cra_charities.csv')
    
    if os.path.exists(csv_path):
        log(f"Using cached {csv_path}")
        return csv_path
    
    # Try zip download
    log("Downloading CRA Charities data...")
    try:
        req = urllib.request.Request(CRA_ZIP_URL, headers={'User-Agent': 'GrantWizard/1.0'})
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(zip_path, 'wb') as f:
                f.write(resp.read())
        log(f"  Downloaded {os.path.getsize(zip_path):,} bytes")
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.endswith('.csv') or name.endswith('.txt'):
                    log(f"  Extracting {name}...")
                    zf.extract(name, DATA_DIR)
                    # Standardize name
                    extracted = os.path.join(DATA_DIR, name)
                    if not os.path.exists(csv_path):
                        os.rename(extracted, csv_path)
                    else:
                        os.unlink(extracted)
        return csv_path
    except Exception as e:
        log(f"  Zip download failed: {e}")
        log(f"  Trying direct download...")
        try:
            req = urllib.request.Request(CRA_CSV_URL, headers={'User-Agent': 'GrantWizard/1.0'})
            with urllib.request.urlopen(req, timeout=300) as resp:
                with open(csv_path, 'wb') as f:
                    f.write(resp.read())
            log(f"  Downloaded {os.path.getsize(csv_path):,} bytes")
            return csv_path
        except Exception as e2:
            log(f"  Direct download also failed: {e2}")
            return None

def create_import_table(conn):
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS cra_charities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_number TEXT UNIQUE,     -- BN: 9 digits + RR0001
            legal_name TEXT,
            operating_name TEXT,
            address TEXT,
            city TEXT,
            province TEXT,
            postal_code TEXT,
            charity_type TEXT,               -- 'charitable organization', 'public foundation', 'private foundation'
            charity_status TEXT,             -- 'Registered', 'Revoked'
            category_code TEXT,              -- '0001' = religion
            category_name TEXT,              -- 'Religious Organizations'
            total_revenue REAL,
            total_expenses REAL,
            total_assets REAL,
            total_gifts_receipted REAL,      -- Tax-receipted donations
            total_gifts_non_receipted REAL,
            executive_compensation REAL,
            employee_count INTEGER,
            volunteer_count INTEGER,
            fiscal_period_end TEXT,
            filing_date TEXT,
            source TEXT DEFAULT 'cra_charities_directorate',
            imported_at TEXT
        )
    """)
    conn.commit()
    log("Table cra_charities ready")

def parse_cra_csv(csv_path, conn):
    """Parse CRA charities CSV and import religious orgs."""
    c = conn.cursor()
    
    # Detect delimiter (CRA sometimes uses comma, sometimes pipe)
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        first_line = f.readline()
    delim = '|' if '|' in first_line else ','
    
    log(f"Reading {csv_path} (delimiter: '{delim}')...")
    
    religious = 0
    total = 0
    skipped = 0
    
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f, delimiter=delim)
        
        for row in reader:
            total += 1
            if total % 20000 == 0:
                log(f"  ... {total:,} rows, {religious:,} religious")
            
            # Normalize field names (CRA changes them occasionally)
            fields = {k.strip().lower().replace(' ', '_'): v.strip() if v else '' 
                     for k, v in row.items()}
            
            # Key fields - try multiple possible names
            bn = (fields.get('bn') or fields.get('business_number') or 
                  fields.get('registration_number') or '')
            name = (fields.get('legal_name') or fields.get('charity_name') or 
                   fields.get('name') or '')
            category = (fields.get('category_code') or fields.get('category') or 
                       fields.get('sector_code') or '')
            
            if not bn or not name:
                skipped += 1
                continue
            
            # Filter: religion category or church-related keywords
            is_religious = False
            if category in ('0001', '1', 'Religious Organizations', 'Religion'):
                is_religious = True
            elif any(kw in name.upper() for kw in [
                'CHURCH', 'PARISH', 'CATHEDRAL', 'DIOCESE', 'SYNOD',
                'MINISTRY', 'FELLOWSHIP', 'CONGREGATION', 'TEMPLE',
                'MOSQUE', 'SYNAGOGUE', 'BUDDHIST', 'HINDU', 'SIKH',
                'GURDWARA', 'ISLAMIC', 'MUSLIM', 'CATHOLIC', 'BAPTIST',
                'PRESBYTERIAN', 'METHODIST', 'LUTHERAN', 'ANGLICAN',
                'PENTECOSTAL', 'EVANGELICAL', 'ORTHODOX', 'MENNONITE',
                'WESLEYAN', 'NAZARENE', 'ADVENTIST', 'COVENANT',
                'ALLIANCE', 'BRETHREN', 'GOSPEL', 'CHRISTIAN',
                'JEHOVAH', 'LATTER-DAY', 'MORMON', 'CHABAD',
                'ASSEMBLIES OF GOD', 'CHURCHES OF CHRIST',
                'SALVATION ARMY', 'UNITED CHURCH',
                'RELIGIOUS', 'SPIRITUAL', 'FAITH', 'WORSHIP',
                'PASTORAL', 'CHAPLAINCY', 'MISSIONARY',
            ]):
                is_religious = True
            
            if not is_religious:
                continue
            
            religious += 1
            
            # Parse financials
            def safe_float(val):
                try: return float(str(val).replace('$','').replace(',','').strip())
                except: return None
            
            def safe_int(val):
                try: return int(float(str(val).replace(',','').strip()))
                except: return None
            
            # Province normalization
            province = (fields.get('province') or fields.get('province_territory') or '').upper()
            ca_provinces = {
                'ONTARIO':'ON','BRITISH COLUMBIA':'BC','ALBERTA':'AB','QUEBEC':'QC',
                'MANITOBA':'MB','SASKATCHEWAN':'SK','NOVA SCOTIA':'NS',
                'NEW BRUNSWICK':'NB','NEWFOUNDLAND AND LABRADOR':'NL',
                'PRINCE EDWARD ISLAND':'PE','YUKON':'YT',
                'NORTHWEST TERRITORIES':'NT','NUNAVUT':'NU',
            }
            province = ca_provinces.get(province, province[:2] if len(province) > 2 else province)
            
            if DRY_RUN:
                continue
            
            c.execute("""
                INSERT OR REPLACE INTO cra_charities 
                (business_number, legal_name, operating_name, address, city, 
                 province, postal_code, charity_type, charity_status,
                 category_code, total_revenue, total_expenses, total_assets,
                 total_gifts_receipted, employee_count, fiscal_period_end,
                 imported_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bn,
                name,
                fields.get('operating_name') or '',
                fields.get('address') or fields.get('street') or '',
                fields.get('city') or '',
                province,
                fields.get('postal_code') or fields.get('postcode') or '',
                fields.get('charity_type') or fields.get('type') or '',
                fields.get('charity_status') or fields.get('status') or '',
                category,
                safe_float(fields.get('total_revenue') or fields.get('total_revenue_')) or 0,
                safe_float(fields.get('total_expenses') or fields.get('total_expenditures')) or 0,
                safe_float(fields.get('total_assets') or fields.get('total_assets_')) or 0,
                safe_float(fields.get('total_gifts') or fields.get('total_eligible_gifts')) or 0,
                safe_int(fields.get('employee_count') or fields.get('full_time_employees')),
                fields.get('fiscal_period_end') or fields.get('period_ending') or '',
                datetime.utcnow().isoformat()
            ))
        
        if not DRY_RUN:
            conn.commit()
    
    log(f"\nResults:")
    log(f"  Total rows in CSV: {total:,}")
    log(f"  Religious orgs identified: {religious:,}")
    log(f"  Skipped (no BN/name): {skipped:,}")
    
    # Summary
    if not DRY_RUN:
        c.execute("SELECT province, COUNT(1) FROM cra_charities GROUP BY province ORDER BY COUNT(1) DESC")
        log("\n  By province:")
        for r in c.fetchall():
            log(f"    {r[0]}: {r[1]:,}")
        
        c.execute("SELECT charity_type, COUNT(1) FROM cra_charities GROUP BY charity_type")
        log("\n  By type:")
        for r in c.fetchall():
            log(f"    {r[0]}: {r[1]:,}")
    
    return religious

def cross_reference(conn):
    """Match CRA charities to existing Canadian churches."""
    c = conn.cursor()
    log("\nCross-referencing with existing Canadian churches...")
    
    if DRY_RUN:
        # Count potential matches
        c.execute("""
            SELECT COUNT(1) FROM churches c
            INNER JOIN cra_charities cr ON c.name = cr.legal_name
            WHERE c.country = 'CA'
        """)
        log(f"  Would match {c.fetchone()[0]:,} by exact name")
        c.execute("""
            SELECT COUNT(1) FROM churches c
            INNER JOIN cra_charities cr ON c.city = cr.city AND c.state = cr.province
            WHERE c.country = 'CA'
        """)
        log(f"  Would match {c.fetchone()[0]:,} by city+province (fuzzy)")
        return
    
    # Exact name match
    c.execute("""
        UPDATE churches SET 
            ein = (SELECT cr.business_number FROM cra_charities cr 
                   WHERE cr.legal_name = churches.name AND churches.country = 'CA'
                   LIMIT 1),
            notes = COALESCE(notes || '; ', '') || 'CRA BN matched by name',
            last_updated = ?
        WHERE country = 'CA' 
        AND EXISTS (SELECT 1 FROM cra_charities cr WHERE cr.legal_name = churches.name)
    """, (datetime.utcnow().isoformat(),))
    exact = c.rowcount
    log(f"  Exact name matches: {exact:,}")
    
    # City + province + name similarity
    c.execute("""
        UPDATE churches SET 
            ein = (SELECT cr.business_number FROM cra_charities cr 
                   WHERE cr.city = churches.city 
                   AND cr.province = churches.state
                   AND churches.country = 'CA'
                   AND (cr.legal_name LIKE '%' || churches.name || '%'
                        OR churches.name LIKE '%' || cr.legal_name || '%')
                   LIMIT 1),
            notes = COALESCE(notes || '; ', '') || 'CRA BN matched by city/name',
            last_updated = ?
        WHERE country = 'CA' 
        AND ein IS NULL
        AND EXISTS (SELECT 1 FROM cra_charities cr 
                    WHERE cr.city = churches.city 
                    AND cr.province = churches.state
                    AND (cr.legal_name LIKE '%' || churches.name || '%'
                         OR churches.name LIKE '%' || cr.legal_name || '%'))
    """, (datetime.utcnow().isoformat(),))
    fuzzy = c.rowcount
    log(f"  City + name fuzzy matches: {fuzzy:,}")
    
    conn.commit()
    
    # Final count
    c.execute("SELECT COUNT(1) FROM churches WHERE country='CA' AND ein IS NOT NULL AND ein != ''")
    log(f"\n  Canadian churches with BN now: {c.fetchone()[0]:,}")

def main():
    log("=== CRA Charities Directorate Import ===")
    
    csv_path = download_cra()
    if not csv_path:
        log("Failed to download CRA data. Manual download may be needed.")
        return
    
    conn = sqlite3.connect(DB_PATH, timeout=120)
    conn.execute("PRAGMA journal_mode=DELETE")
    
    create_import_table(conn)
    religious = parse_cra_csv(csv_path, conn)
    
    if religious > 0:
        cross_reference(conn)
    
    conn.close()
    log("\nDone.")

if __name__ == '__main__':
    main()
