#!/usr/bin/env python3
"""Import PCUSA congregations from cleaned CSV into DB."""
import csv, re, sqlite3

db = sqlite3.connect("churches.db")
cur = db.cursor()

with open("data/denom/pcusa_congregations.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    matched = 0
    inserted = 0
    
    for row in reader:
        raw_name = row.get("name", "")
        name = re.sub(r",\s*[^,]+,\s*[A-Z]{2}\s*$", "", raw_name).strip().upper()
        city = row.get("city", "").strip().upper()
        state = row.get("state", "").strip().upper()
        address = row.get("address1", "").strip()
        website = row.get("website", "").strip()
        zip_code = row.get("zip", "").strip()
        
        if not name or not state:
            continue
        
        # Try matching
        cur.execute("SELECT id, denomination, website FROM churches WHERE UPPER(name)=? AND state=? LIMIT 1", (name, state))
        r = cur.fetchone()
        
        if not r and city:
            cur.execute("SELECT id, denomination, website FROM churches WHERE UPPER(name)=? AND city=? AND state=? LIMIT 1", (name, city, state))
            r = cur.fetchone()
        
        if not r:
            # Try prefix match for "FIRST PRESBYTERIAN CHURCH OF X" variants
            prefix = name[:20]
            cur.execute("SELECT id, denomination, website FROM churches WHERE SUBSTR(UPPER(name),1,?)=? AND state=? LIMIT 1", (len(prefix), prefix, state))
            r = cur.fetchone()
        
        if r:
            matched += 1
            cid, existing_denom, existing_web = r
            updates = []
            uparams = []
            if not existing_denom:
                updates.append("denomination=?")
                uparams.append("Presbyterian Church (U.S.A.)")
            if website and not existing_web:
                updates.append("website=?")
                uparams.append(website)
            if updates:
                uparams.append(cid)
                cur.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id=?", uparams)
        else:
            inserted += 1
            cur.execute("INSERT OR IGNORE INTO churches (name, city, state, address, zip, website, denomination, source) VALUES (?,?,?,?,?,?,?,?)",
                       (name, city, state, address, zip_code, website, "Presbyterian Church (U.S.A.)", "pcusa_api"))
        
        if (matched + inserted) % 2000 == 0:
            print(f"  {matched + inserted:,}...")
            db.commit()

db.commit()
db.close()
print(f"\nPCUSA import complete!")
print(f"  Matched existing: {matched:,}")
print(f"  New churches: {inserted:,}")

# Verify
db2 = sqlite3.connect("churches.db")
c = db2.cursor()
c.execute("SELECT COUNT(*) FROM churches WHERE source='pcusa_api'")
print(f"  Total pcusa_api records: {c.fetchone()[0]:,}")
c.execute("SELECT COUNT(*) FROM churches WHERE denomination='Presbyterian Church (U.S.A.)'")
print(f"  Total PCUSA denom: {c.fetchone()[0]:,}")
db2.close()
