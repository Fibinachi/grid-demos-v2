"""_audit_name_signals.py — quantify how many shared-coord churches have a
state or city hint in their name (usable for corruption detection)."""
import sqlite3, sys, re
sys.path.insert(0, r"E:\grid")
from _recover_shared_coords_v2 import extract_state_hint, SHARED_SQL

DB = "E:/grid/churches.db"
db = sqlite3.connect(DB)
db.execute("PRAGMA busy_timeout=600000")

rows = db.execute(f"""
    SELECT c.id, c.name, l.state,
      (SELECT ac.component_value FROM church_addresses ca
       JOIN address_components ac ON ac.address_id=ca.address_id
         AND ac.component_type='city'
       WHERE ca.church_id=c.id AND ca.is_current=1 LIMIT 1) AS city
    FROM churches c
    LEFT JOIN church_location l ON c.id = l.church_id
    WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL
      AND {SHARED_SQL}
      AND EXISTS (SELECT 1 FROM church_addresses ca
        WHERE ca.church_id=c.id AND ca.is_current=1 AND ca.geocode_source IS NULL)
""").fetchall()
print(f"total targets: {len(rows):,}")

state_hint = 0
city_hint = 0
both = 0
addr_state_conflict = 0
addr_city_conflict = 0
no_hint = 0
for cid, name, state, city in rows:
    sh, _ = extract_state_hint(name)
    if sh:
        state_hint += 1
        if state and state.upper() != sh:
            addr_state_conflict += 1
    # city hint: last capitalized word(s) before a state, or trailing city
    # crude: check if the address city appears in the name
    if city and city.strip().upper() and city.strip().upper() in (name or "").upper():
        city_hint += 1
        if state and state.upper() != sh:
            pass
    if not sh and not (city and city.strip().upper() in (name or "").upper()):
        no_hint += 1

print(f"state hint in name:      {state_hint:,} ({100*state_hint/len(rows):.1f}%)")
print(f"  of those, addr state conflicts: {addr_state_conflict:,}")
print(f"city appears in name:    {city_hint:,} ({100*city_hint/len(rows):.1f}%)")
print(f"no state or city hint:   {no_hint:,} ({100*no_hint/len(rows):.1f}%)")
db.close()
