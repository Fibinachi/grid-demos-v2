"""Fix Jewish misclassifications:
1. osm_import country code errors: SA→IL, JO→IL (Israel coords), SA→IR (Iran coords)
2. holy_sites_import Thai Buddhist temples reclassified from Jewish→Buddhist
3. holy_sites_import ST (São Tomé) QID-only entries → faith cleared
4. holy_sites_import ID Hindu temples → faith cleared
5. holy_sites_import BR clearly non-Jewish entries → faith cleared
6. holy_sites_import CN Buddhist temple → Jewish→Buddhist

Uses gw_db.Provenance for auto provenance logging.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gw_db import connect, Provenance

conn = connect()
c = conn.cursor()

fixes = []
record_count = 0

# === FIX 1: osm_import country codes ===
with Provenance(conn, "_fix_jewish_misclassifications.py", source="osm_import", action="updated",
                fields="country", params="fix_country_codes") as prov:
    
    # 1a. SA→IL: entries at Israel coordinates with Hebrew synagogue names
    sa_israel = c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE faith='Jewish' AND country='SA' AND source='osm_import'
        AND latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 37.0
    """).fetchone()[0]
    
    c.execute("""
        UPDATE churches SET country='IL'
        WHERE faith='Jewish' AND country='SA' AND source='osm_import'
        AND latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 37.0
    """)
    fixes.append(('SA->IL (Israel coords)', sa_israel))
    record_count += sa_israel
    
    # 1b. JO→IL: same pattern
    jo_israel = c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE faith='Jewish' AND country='JO' AND source='osm_import'
        AND latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 37.0
    """).fetchone()[0]
    
    c.execute("""
        UPDATE churches SET country='IL'
        WHERE faith='Jewish' AND country='JO' AND source='osm_import'
        AND latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 37.0
    """)
    fixes.append(('JO->IL (Israel coords)', jo_israel))
    record_count += jo_israel
    
    # 1c. SA→IR: Persian synagogues at Iran coordinates (Yazd area)
    sa_iran = c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE faith='Jewish' AND country='SA' AND source='osm_import'
        AND latitude BETWEEN 25.0 AND 40.0 AND longitude BETWEEN 44.0 AND 64.0
        AND NOT (latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 37.0)
    """).fetchone()[0]
    
    c.execute("""
        UPDATE churches SET country='IR'
        WHERE faith='Jewish' AND country='SA' AND source='osm_import'
        AND latitude BETWEEN 25.0 AND 40.0 AND longitude BETWEEN 44.0 AND 64.0
        AND NOT (latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 37.0)
    """)
    fixes.append(('SA->IR (Iran coords)', sa_iran))
    record_count += sa_iran
    
    # 1d. SA→BH: Bahrain Synagogue
    sa_bh = c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE faith='Jewish' AND country='SA' AND source='osm_import'
        AND name LIKE '%Bahrain%'
    """).fetchone()[0]
    
    c.execute("""
        UPDATE churches SET country='BH'
        WHERE faith='Jewish' AND country='SA' AND source='osm_import'
        AND name LIKE '%Bahrain%'
    """)
    fixes.append(('SA->BH (Bahrain Synagogue)', sa_bh))
    record_count += sa_bh
    
    prov.records_attempted = record_count
    prov.records_matched = record_count
    prov.churches_updated = record_count

# === FIX 2: Thai Buddhist temples reclassified from Jewish→Buddhist ===
with Provenance(conn, "_fix_jewish_misclassifications.py", source="holy_sites_import", action="updated",
                fields="faith,faith_tradition,landmark_type",
                params="fix_th_buddhist") as prov:
    
    th_buddhist = c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE faith='Jewish' AND country='TH' AND source='holy_sites_import'
        AND (name LIKE '%วัด%' OR name LIKE '%ศาล%' OR name LIKE '%สำนัก%' 
             OR name LIKE '%สถูป%' OR name LIKE '%กุฏิ%' OR name LIKE '%สวน%')
    """).fetchone()[0]
    
    c.execute("""
        UPDATE churches SET faith='Buddhist', faith_tradition='Theravada', landmark_type='temple'
        WHERE faith='Jewish' AND country='TH' AND source='holy_sites_import'
        AND (name LIKE '%วัด%' OR name LIKE '%ศาล%' OR name LIKE '%สำนัก%' 
             OR name LIKE '%สถูป%' OR name LIKE '%กุฏิ%' OR name LIKE '%สวน%')
    """)
    fixes.append(('TH Buddhist temples reclassified', th_buddhist))
    
    prov.records_attempted = th_buddhist
    prov.records_matched = th_buddhist
    prov.churches_updated = th_buddhist
    record_count += th_buddhist

# === FIX 3: ST (São Tomé) — all 58 are QID-name entries, no Jews in ST ===
with Provenance(conn, "_fix_jewish_misclassifications.py", source="holy_sites_import", action="updated",
                fields="faith,faith_tradition,landmark_type",
                params="fix_st_no_jewish_pop") as prov:
    
    st_all = c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE faith='Jewish' AND country='ST' AND source='holy_sites_import'
    """).fetchone()[0]
    
    c.execute("""
        UPDATE churches SET faith='unclassified', faith_tradition='', landmark_type='unknown'
        WHERE faith='Jewish' AND country='ST' AND source='holy_sites_import'
    """)
    fixes.append(('ST faith cleared (QID-only, no Jewish pop)', st_all))
    
    prov.records_attempted = st_all
    prov.records_matched = st_all
    prov.churches_updated = st_all
    record_count += st_all

# === FIX 4: ID Hindu/Chinese temples misclassified as Jewish ===
with Provenance(conn, "_fix_jewish_misclassifications.py", source="holy_sites_import", action="updated",
                fields="faith,faith_tradition,landmark_type",
                params="fix_id_hindu_chinese_temples") as prov:
    
    id_bad = c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE faith='Jewish' AND country='ID' AND source='holy_sites_import'
        AND (name LIKE '%Pura%' OR name LIKE '%Klenteng%' OR name LIKE '%Makam%' 
             OR name LIKE '%Panti%' OR name LIKE '%Vihara%')
    """).fetchone()[0]
    
    c.execute("""
        UPDATE churches SET faith='unclassified', faith_tradition='', landmark_type='unknown'
        WHERE faith='Jewish' AND country='ID' AND source='holy_sites_import'
        AND (name LIKE '%Pura%' OR name LIKE '%Klenteng%' OR name LIKE '%Makam%' 
             OR name LIKE '%Panti%' OR name LIKE '%Vihara%')
    """)
    fixes.append(('ID Hindu/Chinese temples cleared', id_bad))
    
    prov.records_attempted = id_bad
    prov.records_matched = id_bad
    prov.churches_updated = id_bad
    record_count += id_bad

# === FIX 5: BR clearly non-Jewish entries ===
with Provenance(conn, "_fix_jewish_misclassifications.py", source="holy_sites_import", action="updated",
                fields="faith,faith_tradition,landmark_type",
                params="fix_br_non_jewish") as prov:
    
    br_bad = c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE faith='Jewish' AND country='BR' AND source='holy_sites_import'
        AND (name LIKE '%Igreja%' OR name LIKE '%Matriz%' OR name LIKE '%Djoy%' 
             OR name LIKE '%Tattoo%' OR name LIKE '%Mahikari%' OR name LIKE '%Osun%'
             OR name LIKE '%Assembleia%' OR name LIKE '%Evangelica%')
    """).fetchone()[0]
    
    c.execute("""
        UPDATE churches SET faith='unclassified', faith_tradition='', landmark_type='unknown'
        WHERE faith='Jewish' AND country='BR' AND source='holy_sites_import'
        AND (name LIKE '%Igreja%' OR name LIKE '%Matriz%' OR name LIKE '%Djoy%' 
             OR name LIKE '%Tattoo%' OR name LIKE '%Mahikari%' OR name LIKE '%Osun%'
             OR name LIKE '%Assembleia%' OR name LIKE '%Evangelica%')
    """)
    fixes.append(('BR non-Jewish entries cleared', br_bad))
    
    prov.records_attempted = br_bad
    prov.records_matched = br_bad
    prov.churches_updated = br_bad
    record_count += br_bad

# === FIX 6: CN Buddhist temple ===
with Provenance(conn, "_fix_jewish_misclassifications.py", source="holy_sites_import", action="updated",
                fields="faith,landmark_type",
                params="fix_cn_buddhist_temple") as prov:
    
    cn_bad = c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE faith='Jewish' AND country='CN' AND source='holy_sites_import'
        AND (name LIKE '%寺%' OR name LIKE '%庙%' OR name LIKE '%祠%' OR name LIKE '%庵%')
    """).fetchone()[0]
    
    c.execute("""
        UPDATE churches SET faith='Buddhist', faith_tradition='', landmark_type='temple'
        WHERE faith='Jewish' AND country='CN' AND source='holy_sites_import'
        AND (name LIKE '%寺%' OR name LIKE '%庙%' OR name LIKE '%祠%' OR name LIKE '%庵%')
    """)
    fixes.append(('CN Buddhist temple reclassified', cn_bad))
    
    prov.records_attempted = cn_bad
    prov.records_matched = cn_bad
    prov.churches_updated = cn_bad
    record_count += cn_bad

# === Summary ===
conn.commit()
total = sum(cnt for _, cnt in fixes)
print(f"{'='*60}")
print(f"  JEWISH MISCLASSIFICATION FIX SUMMARY")
print(f"{'='*60}")
print(f"  {'Fix':42s} {'Count':>6s}")
print(f"  {'-'*50}")
for label, cnt in fixes:
    if cnt:
        print(f"  {label:42s} {cnt:>6,}")
print(f"  {'-'*50}")
print(f"  {'TOTAL':42s} {total:>6,}")
print(f"{'='*60}")

# Verify
c2 = conn.cursor()
sa_rem = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='SA'").fetchone()[0]
jo_rem = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='JO'").fetchone()[0]
th_rem = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='TH'").fetchone()[0]
st_rem = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='ST'").fetchone()[0]
id_rem = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='ID'").fetchone()[0]
total_rem = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]
il_added = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='IL'").fetchone()[0]
print(f"\n  Remaining Jewish entries:")
print(f"  SA: {sa_rem:,}  JO: {jo_rem:,}  TH: {th_rem:,}  ST: {st_rem:,}  ID: {id_rem:,}")
print(f"  IL (corrected): {il_added:,}")
print(f"  Total Jewish worldwide: {total_rem:,}")
print(f"  (was 38,185 before fix)")

conn.close()
