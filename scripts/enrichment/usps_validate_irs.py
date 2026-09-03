"""
USPS Address Validation for IRS-sourced GRID records.
Standardizes addresses using the USPS Address Validation API v3 (OAuth 2.0).
Updates: address, city, state, zip5, zip4 with USPS-standardized versions.
Adds: usps_validated, usps_dpv_confirmation, usps_standardized_at columns.
"""
import sqlite3, requests, time, json, os, sys
from datetime import datetime, timezone
from collections import defaultdict

DB = r"E:\grid\churches.db"
CONSUMER_KEY = "40vXp30j8ZXVBTkeBVzLvyKHfdlvQi4WXA2Sbz"
CONSUMER_SECRET = "GgUFgGNF169IuAqvNxa7ADedzGIeFLZOCXtX2Xwfr0a79XhAnDbjFPuGCjBZXmPC"

TOKEN_URL = "https://apis.usps.com/oauth2/v3/token"
ADDRESS_URL = "https://apis.usps.com/addresses/v3/address"

# ── OAuth token ──
def get_token():
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": CONSUMER_KEY,
        "client_secret": CONSUMER_SECRET,
        "scope": "addresses",
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    if resp.status_code != 200:
        print(f"OAuth failed: {resp.status_code} {resp.text[:200]}")
        print("The API key may need activation at: https://developer.usps.com/")
        sys.exit(1)
    return resp.json()["access_token"]

# ── Validate single address (GET, per OpenAPI spec) ──
def validate_address(token, street, city, state, zip5=None):
    params = {
        "streetAddress": street,
        "state": state,
    }
    if city:
        params["city"] = city
    if zip5 and len(str(zip5)) >= 5:
        params["ZIPCode"] = str(zip5)[:5]
    
    resp = requests.get(ADDRESS_URL, params=params, headers={
        "Authorization": f"Bearer {token}",
    }, timeout=30)
    
    if resp.status_code == 200:
        return resp.json()
    elif resp.status_code == 401:
        return None  # token expired, refresh
    elif resp.status_code == 429:
        time.sleep(1)
        return None
    else:
        return {"error": resp.status_code, "body": resp.text[:200]}

# ── Main ──
def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Add USPS columns if not exist
    for col, coltype in [("usps_standardized_at", "TEXT"), ("usps_dpv", "TEXT"), 
                          ("usps_address", "TEXT"), ("usps_city", "TEXT"),
                          ("usps_state", "TEXT"), ("usps_zip5", "TEXT"), ("usps_zip4", "TEXT")]:
        try:
            c.execute(f"ALTER TABLE churches ADD COLUMN {col} {coltype}")
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    
    # Get IRS records needing validation (no lat/lon or not USPS-validated)
    c.execute("""
        SELECT id, name, address, city, state, zip5
        FROM churches 
        WHERE source LIKE '%irs%' AND country='US'
          AND address IS NOT NULL AND address != ''
          AND city IS NOT NULL AND city != ''
          AND state IS NOT NULL AND state != ''
          AND usps_standardized_at IS NULL
        ORDER BY id
        LIMIT 50000
    """)
    records = c.fetchall()
    print(f"IRS records to validate: {len(records):,}")
    
    if not records:
        print("All IRS records already validated!")
        conn.close()
        return
    
    token = get_token()
    print(f"OAuth token obtained: {token[:10]}...")
    
    BATCH_SIZE = 500
    validated = 0
    failed = 0
    dpv_yes = 0
    dpv_no = 0
    
    for i, r in enumerate(records):
        if i % 100 == 0:
            print(f"  {i:,}/{len(records):,} | validated: {validated:,} | DPV: {dpv_yes} yes / {dpv_no} no | failed: {failed}")
        
        result = validate_address(token, r['address'], r['city'], r['state'], r['zip5'])
        
        if result is None:
            # Token expired, refresh
            token = get_token()
            result = validate_address(token, r['address'], r['city'], r['state'], r['zip5'])
        
        if result and 'error' not in result:
            addr = result.get('address', {})
            extra = result.get('additionalInfo', {})
            dpv = extra.get('DPVConfirmation', '')
            
            c.execute("""
                UPDATE churches SET 
                    usps_address=?, usps_city=?, usps_state=?, usps_zip5=?, usps_zip4=?,
                    usps_dpv=?, usps_standardized_at=?
                WHERE id=?
            """, (
                addr.get('streetAddress', ''),
                addr.get('city', ''),
                addr.get('state', ''),
                addr.get('ZIPCode', ''),
                addr.get('ZIPPlus4', ''),
                dpv,
                datetime.now(timezone.utc).isoformat(),
                r['id'],
            ))
            
            validated += 1
            if dpv == 'Y':
                dpv_yes += 1
            elif dpv == 'N':
                dpv_no += 1
        else:
            failed += 1
        
        if i % BATCH_SIZE == 0 and i > 0:
            conn.commit()
            time.sleep(0.5)  # rate limit
    
    conn.commit()
    
    print(f"\n{'='*50}")
    print(f"USPS Validation Complete")
    print(f"{'='*50}")
    print(f"  Validated:  {validated:,}")
    print(f"  DPV Yes:    {dpv_yes:,}")
    print(f"  DPV No:     {dpv_no:,}")
    print(f"  Failed:     {failed:,}")
    
    conn.close()

if __name__ == "__main__":
    main()
