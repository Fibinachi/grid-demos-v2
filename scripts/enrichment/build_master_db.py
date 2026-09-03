"""
Build Master Church Database (SQLite)
======================================
Imports all church data sources into a single SQLite database
with proper schema, indexes, and deduplication.

Usage: python build_master_db.py
"""

import sqlite3, csv, os, re, time
from datetime import datetime

DB_PATH = r"E:\grid\churches.db"

def create_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS churches (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            denomination    TEXT DEFAULT '',
            family          TEXT DEFAULT '',
            website         TEXT DEFAULT '',
            email           TEXT DEFAULT '',
            phone           TEXT DEFAULT '',
            address         TEXT DEFAULT '',
            city            TEXT DEFAULT '',
            state           TEXT DEFAULT '',
            zip             TEXT DEFAULT '',
            ein             TEXT DEFAULT '',
            source          TEXT DEFAULT '',
            target_group    TEXT DEFAULT '',
            email_validated INTEGER DEFAULT 0,
            has_website     INTEGER DEFAULT 0,
            last_updated    TEXT DEFAULT (datetime('now')),
            notes           TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_churches_state ON churches(state);
        CREATE INDEX IF NOT EXISTS idx_churches_denom ON churches(denomination);
        CREATE INDEX IF NOT EXISTS idx_churches_group ON churches(target_group);
        CREATE INDEX IF NOT EXISTS idx_churches_email ON churches(email);
        CREATE INDEX IF NOT EXISTS idx_churches_website ON churches(website);
        CREATE INDEX IF NOT EXISTS idx_churches_ein ON churches(ein);
        CREATE INDEX IF NOT EXISTS idx_churches_name ON churches(name);

    """)
    conn.commit()

def normalize_name(name):
    n = (name or '').strip().upper()
    n = re.sub(r'[^A-Z0-9 ]', ' ', n)
    n = re.sub(r'\s+', ' ', n)
    return n.strip()

def parse_city_state(cs):
    if not cs or ',' not in cs:
        return ('', '')
    parts = cs.split(',')
    city = parts[0].strip()
    state = parts[-1].strip().upper()[:2] if len(parts) > 1 else ''
    return (city, state)

def import_contacts(conn):
    """Import church_contacts.csv (8,349 records)."""
    d = r"E:\grid"
    path = os.path.join(d, "church_contacts.csv")
    
    cur = conn.cursor()
    imported = 0
    skipped = 0
    
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            name = (r.get("church_name", "") or "").strip()
            if not name:
                skipped += 1
                continue
            
            city, state = parse_city_state(r.get("city_state", ""))
            website = (r.get("website", "") or "").strip()
            
            # Check if this church already exists (by normalized name + state)
            nname = normalize_name(name)
            existing = cur.execute(
                "SELECT id FROM churches WHERE name = ? AND state = ?",
                (nname, state)
            ).fetchone()
            
            if existing:
                # Update existing
                cur.execute("""
                    UPDATE churches SET
                        denomination = CASE WHEN ? != '' THEN ? ELSE denomination END,
                        website = CASE WHEN ? != '' THEN ? ELSE website END,
                        phone = CASE WHEN ? != '' THEN ? ELSE phone END,
                        address = CASE WHEN ? != '' THEN ? ELSE address END,
                        city = CASE WHEN ? != '' THEN ? ELSE city END,
                        zip = CASE WHEN ? != '' THEN ? ELSE zip END,
                        family = CASE WHEN ? != '' THEN ? ELSE family END,
                        has_website = CASE WHEN ? != '' THEN 1 ELSE has_website END,
                        source = CASE WHEN source = '' THEN 'contacts' ELSE source || ',contacts' END,
                        last_updated = datetime('now')
                    WHERE id = ?
                """, (
                    r.get("denomination",""), r.get("denomination",""),
                    website, website,
                    r.get("phone",""), r.get("phone",""),
                    r.get("address",""), r.get("address",""),
                    city, city,
                    r.get("zip",""), r.get("zip",""),
                    r.get("family",""), r.get("family",""),
                    website,
                    existing[0],
                ))
            else:
                cur.execute("""
                    INSERT INTO churches (name, denomination, family, website, phone,
                                          address, city, state, zip, source, has_website)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'contacts', ?)
                """, (
                    nname,
                    r.get("denomination", ""),
                    r.get("family", ""),
                    website,
                    r.get("phone", ""),
                    r.get("address", ""),
                    city,
                    state,
                    r.get("zip", ""),
                    1 if website else 0,
                ))
            imported += 1
    
    conn.commit()
    print(f"Contacts: {imported} imported, {skipped} skipped (no name)")

def import_irs(conn):
    """Import irs_churches.csv (273,432 records)."""
    d = r"E:\grid"
    path = os.path.join(d, "irs_churches.csv")
    
    cur = conn.cursor()
    imported = 0
    skipped = 0
    merged = 0
    
    batch = []
    
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            name = (r.get("NAME", "") or "").strip()
            if not name:
                skipped += 1
                continue
            
            nname = normalize_name(name)
            state = (r.get("STATE", "") or "").strip().upper()[:2]
            ein = (r.get("EIN", "") or "").strip()
            street = (r.get("STREET", "") or "").strip()
            city = (r.get("CITY", "") or "").strip()
            zipcode = (r.get("ZIP", "") or "").strip()
            
            # Check if church exists
            existing = cur.execute(
                "SELECT id, ein FROM churches WHERE name = ? AND state = ?",
                (nname, state)
            ).fetchone()
            
            if existing:
                # Merge: add IRS data but keep existing data
                cur.execute("""
                    UPDATE churches SET
                        address = CASE WHEN ? != '' THEN ? ELSE address END,
                        city = CASE WHEN city = '' AND ? != '' THEN ? ELSE city END,
                        zip = CASE WHEN zip = '' AND ? != '' THEN ? ELSE zip END,
                        ein = CASE WHEN ? != '' THEN ? ELSE ein END,
                        source = CASE WHEN source NOT LIKE '%irs%' THEN source || ',irs' ELSE source END,
                        last_updated = datetime('now')
                    WHERE id = ?
                """, (
                    street, street,
                    city, city,
                    zipcode, zipcode,
                    ein, ein,
                    existing[0],
                ))
                merged += 1
            else:
                batch.append((
                    nname, state, ein, street, city, zipcode
                ))
                imported += 1
            
            # Batch insert for performance
            if len(batch) >= 500:
                cur.executemany("""
                    INSERT INTO churches (name, state, ein, address, city, zip, source)
                    VALUES (?, ?, ?, ?, ?, ?, 'irs')
                """, batch)
                batch = []
        
        # Final batch
        if batch:
            cur.executemany("""
                INSERT INTO churches (name, state, ein, address, city, zip, source)
                VALUES (?, ?, ?, ?, ?, ?, 'irs')
            """, batch)
    
    conn.commit()
    print(f"IRS: {imported} new, {merged} merged with existing, {skipped} skipped")

def import_scraped(conn):
    """Import scraped results from EC2 chunks if available."""
    d = r"E:\grid"
    cur = conn.cursor()
    
    for chunk_id in range(3):
        path = os.path.join(d, f"scraped_chunk_{chunk_id}.csv")
        if not os.path.exists(path):
            continue
        
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            imported = 0
            for r in reader:
                name = normalize_name(r.get("church_name", ""))
                state = (r.get("city_state", "") or "").split(",")[-1].strip().upper()[:2] if "," in (r.get("city_state","") or "") else ""
                email = (r.get("email", "") or "").strip().lower()
                phone = (r.get("phone", "") or "").strip()
                website = (r.get("website", "") or "").strip()
                
                if not name:
                    continue
                
                existing = cur.execute(
                    "SELECT id FROM churches WHERE name = ? AND state = ?",
                    (name, state)
                ).fetchone()
                
                if existing:
                    cur.execute("""
                        UPDATE churches SET
                            email = CASE WHEN ? != '' THEN ? ELSE email END,
                            phone = CASE WHEN ? != '' THEN ? ELSE phone END,
                            website = CASE WHEN website = '' AND ? != '' THEN ? ELSE website END,
                            email_validated = CASE WHEN ? != '' THEN 1 ELSE email_validated END,
                            has_website = 1,
                            last_updated = datetime('now')
                        WHERE id = ?
                    """, (
                        email, email,
                        phone, phone,
                        website, website,
                        email,
                        existing[0],
                    ))
                else:
                    cur.execute("""
                        INSERT INTO churches (name, website, email, phone, state, 
                                              source, has_website, email_validated)
                        VALUES (?, ?, ?, ?, ?, 'scraped', 1, ?)
                    """, (
                        name, website, email, phone, state,
                        1 if email else 0,
                    ))
                imported += 1
            
            conn.commit()
            print(f"Scraped chunk {chunk_id}: {imported} imported")
    
    # Also check for found_chunk files (Phase 1b+2 results)
    for prefix in ["found_chunk"]:
        for i in range(3):
            path = os.path.join(d, f"{prefix}_{i}.csv")
            if not os.path.exists(path):
                continue
            
            with open(path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                imported = 0
                for r in reader:
                    name = normalize_name(r.get("church_name", ""))
                    state = (r.get("state", "") or "").strip().upper()[:2]
                    website = (r.get("website", "") or "").strip()
                    email = (r.get("email", "") or "").strip().lower()
                    phone = (r.get("phone", "") or "").strip()
                    
                    if not name:
                        continue
                    
                    existing = cur.execute(
                        "SELECT id FROM churches WHERE name = ? AND state = ?",
                        (name, state)
                    ).fetchone()
                    
                    if existing:
                        cur.execute("""
                            UPDATE churches SET
                                website = CASE WHEN ? != '' THEN ? ELSE website END,
                                email = CASE WHEN ? != '' THEN ? ELSE email END,
                                phone = CASE WHEN ? != '' THEN ? ELSE phone END,
                                has_website = CASE WHEN ? != '' THEN 1 ELSE has_website END,
                                email_validated = CASE WHEN ? != '' THEN 1 ELSE email_validated END,
                                last_updated = datetime('now')
                            WHERE id = ?
                        """, (
                            website, website,
                            email, email,
                            phone, phone,
                            website,
                            email,
                            existing[0],
                        ))
                    else:
                        cur.execute("""
                            INSERT INTO churches (name, website, email, phone, state,
                                                  source, has_website, email_validated)
                            VALUES (?, ?, ?, ?, ?, 'finder', ?, ?)
                        """, (
                            name, website, email, phone, state,
                            1 if website else 0,
                            1 if email else 0,
                        ))
                    imported += 1
                
                conn.commit()
                print(f"Found chunk {i}: {imported} imported")

def summary(conn):
    cur = conn.cursor()
    
    total = cur.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
    with_email = cur.execute("SELECT COUNT(*) FROM churches WHERE email != ''").fetchone()[0]
    with_website = cur.execute("SELECT COUNT(*) FROM churches WHERE has_website = 1").fetchone()[0]
    with_phone = cur.execute("SELECT COUNT(*) FROM churches WHERE phone != ''").fetchone()[0]
    with_ein = cur.execute("SELECT COUNT(*) FROM churches WHERE ein != ''").fetchone()[0]
    
    by_source = cur.execute("""
        SELECT source, COUNT(*) FROM churches GROUP BY source ORDER BY COUNT(*) DESC
    """).fetchall()
    
    by_state = cur.execute("""
        SELECT state, COUNT(*) FROM churches WHERE state != '' 
        GROUP BY state ORDER BY COUNT(*) DESC LIMIT 10
    """).fetchall()
    
    print(f"\n{'='*50}")
    print(f"MASTER CHURCH DATABASE SUMMARY")
    print(f"{'='*50}")
    print(f"Total churches:  {total:,}")
    print(f"With email:      {with_email:,} ({with_email/total*100:.1f}%)")
    print(f"With website:    {with_website:,} ({with_website/total*100:.1f}%)")
    print(f"With phone:      {with_phone:,} ({with_phone/total*100:.1f}%)")
    print(f"With EIN:        {with_ein:,}")
    print(f"\nBy source:")
    for s, c in by_source:
        print(f"  {s}: {c:,}")
    print(f"\nTop states:")
    for s, c in by_state:
        print(f"  {s}: {c:,}")
    
    return total, with_email

def main():
    print("Building Master Church Database...")
    print(f"SQLite DB: {DB_PATH}")
    print()
    
    if os.path.exists(DB_PATH):
        back = DB_PATH.replace(".db", f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
        os.rename(DB_PATH, back)
        print(f"Backed up existing DB to: {back}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    
    create_schema(conn)
    print("Schema created.")
    print()
    
    import_contacts(conn)
    import_irs(conn)
    import_scraped(conn)
    
    # Final vacuum & optimize
    conn.execute("PRAGMA analysis_limit=400")
    conn.execute("PRAGMA optimize")
    conn.commit()
    
    total, with_email = summary(conn)
    
    conn.close()
    
    size_mb = os.path.getsize(DB_PATH) / (1024*1024)
    print(f"\nDatabase file: {size_mb:.1f} MB")

if __name__ == "__main__":
    main()
