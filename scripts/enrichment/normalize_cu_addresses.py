"""Normalize ChurchUnion addresses: parse ZIP from embedded "City, ST ZIP, United States" pattern."""
import sqlite3, re, time
import pandas as pd
from datetime import datetime

DB = "E:/grid/churches.db"
NOW = datetime.utcnow().isoformat()
TODAY = datetime.utcnow().strftime("%Y-%m-%d")

t0 = time.time()

# ── 1. Load ungeocoded ChurchUnion rows ──
print("Loading ChurchUnion rows with 'United States' in address...", flush=True)
db = sqlite3.connect(DB)
df = pd.read_sql_query("""
    SELECT id, name, address, city, state, zip
    FROM churches 
    WHERE source='churchunion_scraper' 
      AND address LIKE '%United States%'
    ORDER BY id
""", db)
db.close()
print(f"  {len(df):,} rows ({time.time()-t0:.1f}s)", flush=True)

# ── 2. Parse address field ──
print("Parsing addresses...", flush=True)

# Pattern: "Street, City, ST ZIP, United States" or "Street, City, ST ZIP, Canada"
# Also: "Route 18, Burgettstown, PA 15021, United States"
# Also: "RR 1 Box 91, Cuthbert, GA 39840, United States"
# Also: "PO Box 2083, Riverview, FL 33568, United States"

addr_re = re.compile(
    r'^(.*?),\s*'           # street (lazy, up to first comma after city/state)
    r'([^,]+),\s*'          # city
    r'([A-Z]{2})\s*'        # state (2 uppercase letters)
    r'(\d{5}(?:-\d{4})?)'   # ZIP (5 or 5+4)
    r'(?:,\s*(?:United States|USA|Canada|US))?'  # optional country
    r'\s*$'
)

# Simpler approach: find the last occurrence of "ST ZIP" pattern
zip_re = re.compile(r',\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\s*(?:,\s*(?:United States|USA|Canada|US))?\s*$')

fixed_addr = 0
fixed_zip = 0
fixed_state = 0
cleaned_country = 0

new_addresses = []
new_zips = []
new_states = []

for _, row in df.iterrows():
    addr = (row["address"] or "").strip()
    orig_addr = addr
    
    # Try to extract "ST ZIP" from end of address
    m = zip_re.search(addr)
    if m:
        st, zp = m.group(1), m.group(2)
        # Strip the matched portion from address
        addr = addr[:m.start()].strip().rstrip(",").strip()
        
        # If we don't have state, use extracted one
        if not row["state"] or row["state"].strip() == "":
            new_states.append(st)
            fixed_state += 1
        else:
            new_states.append(row["state"])
        
        new_zips.append(zp)
        fixed_zip += 1
    else:
        # Try at least strip "United States" suffix
        addr = re.sub(r',\s*United States\s*$', '', addr, flags=re.IGNORECASE).strip()
        addr = re.sub(r',\s*USA\s*$', '', addr, flags=re.IGNORECASE).strip()
        addr = re.sub(r',\s*Canada\s*$', '', addr, flags=re.IGNORECASE).strip()
        new_states.append(row["state"])
        new_zips.append(row["zip"] or "")
    
    # Strip trailing "United States" / country from address
    if addr != orig_addr:
        cleaned_country += 1
    
    # Clean up address
    addr = re.sub(r',\s*United States\s*$', '', addr, flags=re.IGNORECASE).strip()
    addr = re.sub(r',\s*USA\s*$', '', addr, flags=re.IGNORECASE).strip()
    
    if addr != (row["address"] or "").strip():
        fixed_addr += 1
    
    new_addresses.append(addr)

df["address"] = new_addresses
df["zip"] = new_zips
df["state"] = new_states

print(f"  Fixed address: {fixed_addr:,}", flush=True)
print(f"  Fixed ZIP: {fixed_zip:,}", flush=True)
print(f"  Fixed state: {fixed_state:,}", flush=True)

# ── 3. Write back via temp table ──
print("Writing back to DB...", flush=True)
db = sqlite3.connect(DB)
db.execute("PRAGMA synchronous=OFF")

changed = df[["id", "address", "zip", "state"]].copy()
changed["id"] = changed["id"].astype(int)
changed.to_sql("_cu_addr_fix", db, if_exists="replace", index=False)
db.execute("CREATE INDEX _cu_addr_idx ON _cu_addr_fix(id)")
print(f"  Temp table written ({time.time()-t0:.1f}s)", flush=True)

db.execute("""
    UPDATE churches SET 
        address = COALESCE(t.address, churches.address),
        zip = COALESCE(t.zip, churches.zip),
        state = COALESCE(t.state, churches.state)
    FROM _cu_addr_fix AS t
    WHERE churches.id = t.id
""")
print(f"  UPDATE complete ({time.time()-t0:.1f}s)", flush=True)

db.execute("DROP TABLE _cu_addr_fix")
db.commit()

# Verify fix
before = len(df)
after_addr = db.execute("""
    SELECT COUNT(1) FROM churches 
    WHERE source='churchunion_scraper' 
      AND address LIKE '%United States%'
""").fetchone()[0]
after_zip = db.execute("""
    SELECT COUNT(1) FROM churches 
    WHERE source='churchunion_scraper' 
      AND (zip IS NULL OR zip = '')
""").fetchone()[0]

print(f"  Rows with 'United States' in address: {after_addr:,} (was {before:,})", flush=True)
print(f"  Rows with empty ZIP: {after_zip:,} (was {before:,})", flush=True)

# ── 4. Provenance ──
db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated,
     churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, 0, ?, 'completed', ?)
""", ("churchunion_addr_norm2", "normalize_cu_addresses.py", TODAY, TODAY,
      fixed_addr, "address,zip,state",
      f"Parsed ZIP from embedded 'City, ST ZIP, United States' pattern (all ChurchUnion rows). "
      f"{fixed_zip} ZIPs extracted, {fixed_addr} addresses cleaned."))
db.commit()
db.close()

print(f"\nDONE in {time.time()-t0:.1f}s", flush=True)
