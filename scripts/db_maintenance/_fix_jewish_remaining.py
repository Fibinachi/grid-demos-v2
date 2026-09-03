"""Second pass: fix remaining Jewish misclassifications missed in first pass."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gw_db import connect, Provenance

conn = connect()
c = conn.cursor()

# === FIX SA remaining: Moses Ben Maimon → UAE ===
with Provenance(conn, "_fix_jewish_remaining.py", source="osm_import", action="updated",
                fields="country", params="fix_sa_uae") as prov:
    c.execute("""
        UPDATE churches SET country='AE'
        WHERE faith='Jewish' AND country='SA' AND name LIKE '%Moses Ben Maimon%'
    """)
    sa_fixed = c.execute("SELECT changes()").fetchone()[0]
    prov.churches_updated = sa_fixed
    print(f"SA→AE (Moses Ben Maimon → Abu Dhabi): {sa_fixed}")

# === TH: broader Buddhist/Thai religious patterns ===
with Provenance(conn, "_fix_jewish_remaining.py", source="holy_sites_import", 
                action="updated", fields="faith,faith_tradition,landmark_type",
                params="fix_th_remaining") as prov:
    
    # Thai keywords I missed: โรง (rong - hall), พระ (phra - monk/sacred), 
    # มูลนิธิ (munlanithi - foundation), สมาคม (samakom - association),
    # ศูนย์ (sun - center), สุสาน (susaan - cemetery), มณฑป (monthop - mandapa),
    # ISKCON, โรงเจ (rong jae - Chinese vegetarian), บ่อน้ำพระพุทธมนต์ (Buddha water),
    # โหราศาสตร์ (horasart - astrology)
    th_more = c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE faith='Jewish' AND country='TH' AND source='holy_sites_import'
        AND (name LIKE '%พระ%' OR name LIKE '%โรง%' OR name LIKE '%มูลนิธิ%'
             OR name LIKE '%สมาคม%' OR name LIKE '%สุสาน%' OR name LIKE '%มณฑป%'
             OR name LIKE '%ISKCON%' OR name LIKE '%โหรา%' OR name LIKE '%White Dragon%'
             OR name LIKE '%สี่แยก%' OR name LIKE '%มหาวิทยาลัย%'
             OR name LIKE '%ตำหนัก%' OR name LIKE '%หลวงพ่อ%')
    """).fetchone()[0]
    
    c.execute("""
        UPDATE churches SET faith='Buddhist', faith_tradition='Theravada', landmark_type='temple'
        WHERE faith='Jewish' AND country='TH' AND source='holy_sites_import'
        AND (name LIKE '%พระ%' OR name LIKE '%โรง%' OR name LIKE '%มูลนิธิ%'
             OR name LIKE '%สมาคม%' OR name LIKE '%สุสาน%' OR name LIKE '%มณฑป%'
             OR name LIKE '%ISKCON%' OR name LIKE '%โหรา%' OR name LIKE '%White Dragon%'
             OR name LIKE '%สี่แยก%' OR name LIKE '%มหาวิทยาลัย%'
             OR name LIKE '%ตำหนัก%' OR name LIKE '%หลวงพ่อ%')
    """)
    print(f"TH additional Buddhist reclassified: {th_more}")
    prov.churches_updated = th_more

# === ID: broader Balinese/Islamic/Chinese patterns ===
with Provenance(conn, "_fix_jewish_remaining.py", source="holy_sites_import",
                action="updated", fields="faith,faith_tradition,landmark_type",
                params="fix_id_remaining") as prov:
    
    id_more = c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE faith='Jewish' AND country='ID' AND source='holy_sites_import'
        AND (name LIKE '%Pemerajan%' OR name LIKE '%Merajan%' OR name LIKE '%Sanggah%'
             OR name LIKE '%Pure%' OR name LIKE '%Masjid%' OR name LIKE '%Musholla%'
             OR name LIKE '%Candi%' OR name LIKE '%Pesraman%' OR name LIKE '%佛%'
             OR name LIKE '%Gedung%' OR name LIKE '%FISIP%' OR name LIKE '%Danny%'
             OR name LIKE '%Pura%' OR name LIKE '%Klenteng%' OR name LIKE '%Makam%'
             OR name LIKE '%Panti%' OR name LIKE '%Vihara%')
    """).fetchone()[0]
    
    c.execute("""
        UPDATE churches SET faith='unclassified', faith_tradition='', landmark_type='unknown'
        WHERE faith='Jewish' AND country='ID' AND source='holy_sites_import'
        AND (name LIKE '%Pemerajan%' OR name LIKE '%Merajan%' OR name LIKE '%Sanggah%'
             OR name LIKE '%Pure%' OR name LIKE '%Masjid%' OR name LIKE '%Musholla%'
             OR name LIKE '%Candi%' OR name LIKE '%Pesraman%' OR name LIKE '%佛%'
             OR name LIKE '%Gedung%' OR name LIKE '%FISIP%' OR name LIKE '%Danny%'
             OR name LIKE '%Pura%' OR name LIKE '%Klenteng%' OR name LIKE '%Makam%'
             OR name LIKE '%Panti%' OR name LIKE '%Vihara%')
    """)
    print(f"ID additional non-Jewish cleared: {id_more}")
    prov.churches_updated = id_more

conn.commit()

# === Verify ===
c2 = conn.cursor()
sa_rem = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='SA'").fetchone()[0]
th_rem = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='TH'").fetchone()[0]
id_rem = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='ID'").fetchone()[0]
total = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]
print(f"\nRemaining: SA={sa_rem}  TH={th_rem}  ID={id_rem}")
print(f"Total Jewish worldwide: {total:,}")

# Show what's left in TH
print("\n=== Remaining TH Jewish ===")
rows = c2.execute("""
    SELECT name, source FROM churches 
    WHERE faith='Jewish' AND country='TH'
    ORDER BY source, name
""").fetchall()
for r in rows:
    print(f"  {r[0][:70]:70s} source={r[1][:25]}" if r[0] else '')

# Show what's left in ID
print("\n=== Remaining ID Jewish ===")
rows = c2.execute("""
    SELECT name, source FROM churches 
    WHERE faith='Jewish' AND country='ID'
    ORDER BY source, name
""").fetchall()
for r in rows:
    print(f"  {r[0][:70]:70s} source={r[1][:25]}" if r[0] else '')

conn.close()
