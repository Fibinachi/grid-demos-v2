"""Final pass: catch remaining misclassifications."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gw_db import connect, Provenance

conn = connect()
c = conn.cursor()

# === TH final patterns ===
with Provenance(conn, "_fix_jewish_final.py", source="holy_sites_import",
                action="updated", fields="faith,faith_tradition,landmark_type",
                params="fix_th_final") as prov:
    
    # Catch ALL remaining TH holy_sites_import Jewish entries except "Beth Elisheva"
    c.execute("""
        UPDATE churches SET faith='Buddhist', faith_tradition='Theravada', landmark_type='temple'
        WHERE faith='Jewish' AND country='TH' AND source='holy_sites_import'
        AND name NOT LIKE '%Beth Elisheva%' AND name NOT LIKE '%Israeli%'
    """)
    cnt = c.execute("SELECT changes()").fetchone()[0]
    prov.churches_updated = cnt
    print(f"TH remaining holy_sites Buddhist reclassified: {cnt}")

# === TH osm_import: "The Israeli House" — keep as Jewish ===
# (this is likely a real Israeli-related place)

# === ID final patterns ===
with Provenance(conn, "_fix_jewish_final.py", source="holy_sites_import",
                action="updated", fields="faith,faith_tradition,landmark_type",
                params="fix_id_final_kelenteng_wihara") as prov:
    
    # Clear Kelenteng and Wihara (Chinese/Buddhist temples)
    c.execute("""
        UPDATE churches SET faith='unclassified', faith_tradition='', landmark_type='unknown'
        WHERE faith='Jewish' AND country='ID' AND source='holy_sites_import'
        AND (name LIKE '%Kelenteng%' OR name LIKE '%Wihara%' OR name LIKE '%Puri%'
             OR name LIKE '%Pondok%' OR name LIKE '%Sekaa%' OR name LIKE '%Maksan%'
             OR name LIKE '%Mbah%' OR name LIKE '%Bdi%' OR name LIKE '%Gua%')
    """)
    cnt = c.execute("SELECT changes()").fetchone()[0]
    prov.churches_updated = cnt
    print(f"ID additional cleared: {cnt}")

# Also fix the Christian church in ID from osm_import
with Provenance(conn, "_fix_jewish_final.py", source="osm_import",
                action="updated", fields="faith,landmark_type",
                params="fix_id_gereja") as prov:
    c.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith='Jewish' AND country='ID' AND name LIKE '%Gereja%'
    """).fetchone()[0]
    c.execute("""
        UPDATE churches SET faith='Christian', faith_tradition='Catholic', landmark_type='church'
        WHERE faith='Jewish' AND country='ID' AND name LIKE '%Gereja%'
    """)
    cnt = c.execute("SELECT changes()").fetchone()[0]
    if cnt:
        prov.churches_updated = cnt
        print(f"ID Gereja Mater Dei reclassified Christian: {cnt}")

conn.commit()

# === Final verification ===
c2 = conn.cursor()
sa = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='SA'").fetchone()[0]
jo = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='JO'").fetchone()[0]
th = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='TH'").fetchone()[0]
st = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='ST'").fetchone()[0]
id_ = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='ID'").fetchone()[0]
total = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]

print(f"\n{'='*50}")
print(f"  FINAL JEWISH COUNTS")
print(f"{'='*50}")
print(f"  SA: {sa:,}  JO: {jo:,}  TH: {th:,}  ST: {st:,}  ID: {id_:,}")
print(f"  Total Jewish worldwide: {total:,}")
print(f"  (was 38,185 before fix)")

# Show the remaining TH entries (should be just Beth Elisheva + The Israeli House)
print(f"\nRemaining TH Jewish:")
rows = c2.execute("SELECT name, source FROM churches WHERE faith='Jewish' AND country='TH'").fetchall()
for r in rows:
    print(f"  {r[0][:70]:70s} source={r[1][:25]}" if r[0] else '')

print(f"\nRemaining ID Jewish:")
rows = c2.execute("SELECT name, source FROM churches WHERE faith='Jewish' AND country='ID'").fetchall()
for r in rows:
    print(f"  {r[0][:70]:70s} source={r[1][:25]}" if r[0] else '')

conn.close()
