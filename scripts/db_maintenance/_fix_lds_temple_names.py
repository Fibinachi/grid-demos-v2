"""
Fix LDS temple names and add missing temples.
1. Standardize all LDS temple names to "LDS Temple — [Location]"
2. Add missing Columbia SC Temple entries to lds_hierarchy
"""
import sqlite3, re

DB = 'E:\\grid\\churches.db'
CHUNK = 500

db = sqlite3.connect(DB)
c = db.cursor()

# ── Step 1: Add missing Columbia SC Temple to lds_hierarchy ──────────
print("=" * 60)
print("STEP 1: Adding missing Columbia SC Temple to lds_hierarchy")
print("=" * 60)

# The church_id for the correct Columbia SC Temple entries
# #794050 has no city, #4920646 has Hopkins, SC - use #4920646 (has city + state)
columbia_ids = [794050, 4920646]

for church_id in columbia_ids:
    r = c.execute("SELECT id, name, city, state, country, latitude, longitude FROM churches WHERE id = ?", (church_id,)).fetchone()
    if r:
        cid, name, city, state, country, lat, lon = r
        # Check if already in lds_hierarchy
        existing = c.execute("SELECT id FROM lds_hierarchy WHERE church_id = ?", (church_id,)).fetchone()
        if existing:
            # Update existing - change from meetinghouse to temple
            c.execute("UPDATE lds_hierarchy SET lds_type = 'temple', lds_detail = 'South Carolina' WHERE id = ?", (existing[0],))
            print(f"  ✓ Updated existing lds_hierarchy entry for #{church_id}: {name} → temple")
        else:
            # Insert new
            c.execute("""
                INSERT INTO lds_hierarchy (church_id, name, lds_type, lds_detail, city, state, country, lat, lon)
                VALUES (?, ?, 'temple', 'South Carolina', ?, ?, ?, ?, ?)
            """, (church_id, name, city, state, country, lat, lon))
            print(f"  ✓ Inserted #{church_id}: {name} as temple")
    else:
        print(f"  ✗ Church #{church_id} not found")

db.commit()

# ── Step 2: Standardize LDS temple names ────────────────────────────
print("\n" + "=" * 60)
print("STEP 2: Standardizing LDS temple names")
print("=" * 60)

# Get all temples
temples = c.execute("""
    SELECT h.id, h.church_id, h.name, h.city, h.state, h.country
    FROM lds_hierarchy h
    WHERE h.lds_type = 'temple'
    ORDER BY h.name
""").fetchall()

def make_temple_name(raw_name, city, state, country):
    """Standardize to 'LDS Temple — [Location]' format."""
    low = raw_name.lower()
    raw_up = raw_name.upper()
    
    # FLDS Temple — keep as-is (splinter group)
    if 'FLDS' in raw_up:
        return raw_name
    
    # "LDS London Temple" → "LDS Temple — London"
    if 'london' in low:
        return "LDS Temple — London"
    
    # Extract meaningful location from the raw name
    
    # Pattern 1: "CITY STATE LDS TEMPLE" → "LDS Temple — City, ST"
    loc_match = re.match(r'^([A-Z\s]+)\s+(AZ|CA|CT|FL|GA|ID|IL|IN|MA|MN|NC|NM|NV|NY|OH|OR|PA|TX|UT|VA|WA|WI|DC)\s+(LDS|MORMON)', raw_up)
    if loc_match:
        city_raw = loc_match.group(1).strip().title()
        st = loc_match.group(2)
        location = f"{city_raw}, {st}"
        return f"LDS Temple — {location}"
    
    # Pattern 2: "CITY STATE LDS TEMPLE" with state as full name  
    loc_match = re.match(r'^([A-Z\s]+)\s+(UTAH|INDIANA|MINNESOTA|CALIFORNIA|TEXAS)\s+LDS\s+TEMPLE', raw_up)
    if loc_match:
        loc_raw = loc_match.group(1).strip().title()
        st_full = loc_match.group(2).title()
        location = f"{loc_raw}, {st_full}"
        return f"LDS Temple — {location}"
    
    # Pattern 3: "X LDS Temple" → extract X as location
    loc_match = re.match(r'^(.+?)\s+(LDS|Mormon|Lds)\s+Temple', raw_name, re.IGNORECASE)
    if loc_match:
        loc_raw = loc_match.group(1).strip()
        # Skip if it's just noise
        if loc_raw.upper() not in ('', 'LDS', 'LDSLA', 'A'):
            loc_clean = re.sub(r'\b(LDS|MORMON|LDSLA)\b', '', loc_raw, flags=re.IGNORECASE).strip()
            if loc_clean:
                location = loc_clean.title()
                return f"LDS Temple — {location}"
    
    # Pattern 4: "X Temple - Church of Jesus Christ..." → extract X as location
    loc_match = re.match(r'^(.+?)\s*(?:TEMPLE|Temple)\s*[-–]\s*(?:THE\s+)?(?:CHURCH|LDS|MORMON)', raw_name)
    if loc_match:
        loc_raw = loc_match.group(1).strip()
        loc_clean = re.sub(r'\b(PA|MN|AZ|UT|CA|TX|NY|VA|OR|WA|ID|IL|IN|NH|VT|RI)\b', '', loc_raw).strip()
        if loc_clean and len(loc_clean) > 2 and loc_clean.upper() not in ('LDS', 'MORMON'):
            location = loc_clean.title()
            return f"LDS Temple — {location}"
    
    # Pattern 5: "X Temple Y LDS Church" → extract X
    loc_match = re.match(r'^(.+?)\s*TEMPLE\s', raw_up)
    if loc_match:
        loc_raw = loc_match.group(1).strip()
        loc_clean = re.sub(r'\b(LDS|MORMON|LDSLA|CHURCH)\b', '', loc_raw, flags=re.IGNORECASE).strip()
        if loc_clean and len(loc_clean) > 2:
            location = loc_clean.title()
            return f"LDS Temple — {location}"
    
    # Pattern 6: "LDS Temple Square" → Salt Lake City
    if 'SQUARE' in raw_up:
        return "LDS Temple — Salt Lake City"
    
    # Pattern 7: "Mormon Temple, White Plains" → extract location
    if ',' in raw_name:
        parts = raw_name.split(',')
        loc_raw = parts[1].strip() if len(parts) > 1 else None
        if loc_raw and loc_raw.lower() not in ('lds', 'mormon', 'latter-day'):
            location = loc_raw.strip().title()
            return f"LDS Temple — {location}"
    
    # Pattern 8: Generic "Mormon Temple" or "Temple Mormon" — use country
    if country == 'PH':
        return "LDS Temple — Philippines"
    if country == 'PF':
        return "LDS Temple — French Polynesia"
    if country == 'TO':
        return "LDS Temple — Tonga"
    
    # Pattern 9: FLDS Temple
    if 'flds' in low:
        return "FLDS Temple"
    
    # Fallback to city/state
    parts = []
    if city and city != 'None':
        parts.append(city)
    if state and state != 'None' and state not in parts:
        parts.append(state)
    if parts:
        location = ', '.join(parts)
        # Avoid 'LDS Temple — Los Angeles, CT' (wrong state)
        location = re.sub(r',\s*CT$', ', CA', location)
        return f"LDS Temple — {location}"
    
    # Carlingford → New South Wales location
    if country == 'AU':
        return f"LDS Temple — {raw_name.replace('Lds Temple', '').replace('LDS Temple', '').strip().title()}"
    
    return raw_name  # Last resort: keep original

count = 0
for hid, church_id, old_name, city, state, country in temples:
    new_name = make_temple_name(old_name, city, state, country)
    if new_name != old_name:
        c.execute("UPDATE lds_hierarchy SET name = ? WHERE id = ?", (new_name, hid))
        print(f"  {old_name[:50]:50s} → {new_name[:50]}")
        count += 1
    else:
        print(f"  {old_name[:50]:50s} → (unchanged)")

db.commit()
print(f"\n✓ Standardized {count} temple names")

# ── Step 3: Verify ──────────────────────────────────────────────────
print("\n" + "=" * 60)
print("FINAL TEMPLE LIST")
print("=" * 60)
for r in c.execute("SELECT name, city, state, country FROM lds_hierarchy WHERE lds_type = 'temple' ORDER BY country, state, name"):
    print(f"  {r[0]:55s} | {str(r[1] or ''):20s} | {str(r[2] or ''):5s} | {r[3]}")

db.close()
print("\nDone.")
