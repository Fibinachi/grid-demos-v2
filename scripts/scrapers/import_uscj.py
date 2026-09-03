"""
Import USCJ synagogues into GRID — fast in-memory version.
Loads existing churches → matches in Python → batch-writes results.
"""
import csv, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gw_db import connect

CSV_PATH = os.path.join(PROJ_ROOT, "data", "denom", "uscj_synagogues.csv")
SOURCE = "uscj_api"
TAXONOMY_ID = 547
CHUNK = 500

# State name → abbreviation mapping for normalization
STATE_MAP = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
    "dc": "DC", "district of columbia": "DC",
}

def norm_state(s):
    """Normalize state to 2-letter abbreviation."""
    s = (s or "").strip().lower()
    if len(s) == 2:
        return s.upper()
    return STATE_MAP.get(s, s.upper()[:2])

def load_csv():
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def load_existing(db):
    """Load all existing churches into memory for fast matching."""
    print("Loading existing churches index (this takes ~30s for 5.2M rows)...")
    rows = db.execute("""
        SELECT id, name, city, state, latitude, longitude, taxonomy_id, faith, source
        FROM churches
    """).fetchall()
    print(f"  {len(rows):,} churches loaded")
    return rows

def normalize_name(n):
    """Normalize name for matching: lowercase, strip punctuation."""
    return (n or "").lower().replace("'", "").replace("’", "").replace("  ", " ").strip()

def main():
    db = connect()
    
    uscj = load_csv()
    existing = load_existing(db)
    
    # Build (city, state_abbr) → [churches] index
    print("Building lookup indexes...")
    by_city_state = {}
    city_only_index = {}
    for c in existing:
        key = (c[2] or "", c[3] or "")  # (city, state_abbr)
        by_city_state.setdefault(key, []).append(c)
        # Also index by city only
        ckey = (c[2] or "").lower()
        city_only_index.setdefault(ckey, []).append(c)
    print(f"  {len(by_city_state):,} unique (city,state) keys")
    
    # Process
    matched_cids = set()
    new_records = []
    enrich_logs = []
    contact_adds = []
    taxonomy_fixes = []
    
    next_id = max(c[0] for c in existing) + 1
    
    for i, row in enumerate(uscj):
        title = row["title"]
        city = row["city"] or ""
        state_raw = row["state"] or ""
        state = norm_state(state_raw)
        phone = row["phone"] or ""
        website = row["url"] or ""
        size_cat = row["size"] or ""
        lat = row.get("latitude", "")
        lon = row.get("longitude", "")
        street1 = row.get("street1", "")
        zipcode = row.get("zip", "")
        district = row.get("district_name", "")
        
        cid = None
        title_norm = normalize_name(title)
        candidates = by_city_state.get((city, state), [])
        
        # 1. Exact name match in same city+state
        for c in candidates:
            if title_norm == normalize_name(c[1]):
                cid = c[0]; break
        
        # 2. Substring match in same city+state
        if not cid:
            for c in candidates:
                cn = normalize_name(c[1])
                if title_norm in cn or cn in title_norm:
                    cid = c[0]; break
        
        # 3. GPS proximity (within ~1km) in same city+state
        if not cid and lat and lon:
            lat_f, lon_f = float(lat), float(lon)
            for c in candidates:
                if c[4] and c[5] and abs(c[4] - lat_f) < 0.01 and abs(c[5] - lon_f) < 0.01:
                    cid = c[0]; break
        
        # 4. Fallback: city-only match (for state mismatches)
        if not cid and candidates:
            # Already tried all candidates above; skip
            pass
        
        if not cid and city:
            # Try city-only candidates
            city_candidates = city_only_index.get(city.lower(), [])
            for c in city_candidates:
                cn = normalize_name(c[1])
                if title_norm == cn:
                    cid = c[0]; break
            if not cid:
                for c in city_candidates:
                    cn = normalize_name(c[1])
                    if title_norm in cn or cn in title_norm:
                        cid = c[0]; break
        
        if cid:
            if cid in matched_cids:
                cid = None  # Already matched; create new
            else:
                matched_cids.add(cid)
                c_info = next((c for c in candidates if c[0] == cid), None)
                if c_info:
                    if c_info[6] is None or c_info[6] == 0 or c_info[7] != "Judaism" or c_info[6] == 242:
                        taxonomy_fixes.append(cid)
                if phone:
                    contact_adds.append((cid, "phone", phone))
                if website:
                    contact_adds.append((cid, "website", website))
                if size_cat:
                    enrich_logs.append((cid, size_cat))
        
        if not cid:
            cid = next_id
            next_id += 1
            new_records.append((cid, title, street1, city, state, zipcode, lat, lon, district, phone, website, size_cat))
        
        if (i+1) % 100 == 0:
            print(f"  [{i+1}/{len(uscj)}] {len(matched_cids)} matched, {len(new_records)} new")
    
    print(f"\nMatching done: {len(matched_cids)} matched, {len(new_records)} new")
    
    # Write to DB
    print("\nWriting to database...")
    
    if new_records:
        print(f"  Inserting {len(new_records)} new churches...")
        for bs in range(0, len(new_records), CHUNK):
            batch = new_records[bs:bs+CHUNK]
            db.executemany("""
                INSERT INTO churches (id, name, address, city, state, zip, latitude, longitude,
                    country, taxonomy_id, faith, tradition, landmark_type, source, confidence_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'US', ?, 'Judaism', 'Conservative', 'synagogue', ?, 0.85)
            """, [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], TAXONOMY_ID, SOURCE) for r in batch])
            db.commit()
            print(f"    {bs+len(batch)}/{len(new_records)}")
    
    if contact_adds:
        print(f"  Inserting {len(contact_adds)} contacts...")
        for bs in range(0, len(contact_adds), CHUNK):
            batch = contact_adds[bs:bs+CHUNK]
            db.executemany("""INSERT INTO church_contact_values (church_id, contact_type, value, confidence, source, is_primary)
                VALUES (?, ?, ?, 0.85, ?, 0)""", [(c[0], c[1], c[2], SOURCE) for c in batch])
            db.commit()
    
    if enrich_logs:
        print(f"  Inserting {len(enrich_logs)} size logs...")
        for bs in range(0, len(enrich_logs), CHUNK):
            batch = enrich_logs[bs:bs+CHUNK]
            db.executemany("""INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at)
                VALUES (?, 'uscj_size', NULL, ?, ?, datetime('now'))""",
                [(e[0], e[1], SOURCE) for e in batch])
            db.commit()
    
    if taxonomy_fixes:
        print(f"  Fixing {len(taxonomy_fixes)} taxonomies...")
        for bs in range(0, len(taxonomy_fixes), CHUNK):
            batch = taxonomy_fixes[bs:bs+CHUNK]
            db.executemany("""UPDATE churches SET taxonomy_id=?, faith='Judaism', tradition='Conservative', landmark_type='synagogue',
                source=CASE WHEN source IS NULL OR source='' THEN ? ELSE source END WHERE id=?""",
                [(TAXONOMY_ID, SOURCE, cid) for cid in batch])
            db.commit()
    
    # Summary
    total_new = db.execute("SELECT COUNT(*) FROM churches WHERE source=?", (SOURCE,)).fetchone()[0]
    total_contacts = db.execute("SELECT COUNT(*) FROM church_contact_values WHERE source=?", (SOURCE,)).fetchone()[0]
    total_enrich = db.execute("SELECT COUNT(*) FROM enrichment_change_log WHERE change_source=?", (SOURCE,)).fetchone()[0]
    
    print(f"\n{'='*60}")
    print("IMPORT COMPLETE")
    print(f"{'='*60}")
    print(f"  USCJ records:       {len(uscj)}")
    print(f"  Matched existing:   {len(matched_cids)}")
    print(f"  Created new:        {len(new_records)} (DB: {total_new})")
    print(f"  Contacts enriched:  {total_contacts}")
    print(f"  Taxonomy fixed:     {len(taxonomy_fixes)}")
    print(f"  Size logged:        {total_enrich}")
    
    db.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at, churches_updated, churches_inserted, status, notes)
        VALUES (?, ?, datetime('now'), datetime('now'), ?, ?, 'completed', ?)""",
        (SOURCE, "scripts/scrapers/import_uscj.py", len(matched_cids), len(new_records),
         f"USCJ: {len(matched_cids)} matched, {len(new_records)} new. {total_contacts} contacts, {total_enrich} size."))
    db.commit()
    db.close()
    print("Done.")


if __name__ == "__main__":
    main()
