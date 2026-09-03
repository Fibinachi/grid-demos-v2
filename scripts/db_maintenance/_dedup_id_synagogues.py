"""Dedup Indonesia synagogues - keep best, remove duplicates."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gw_db import connect, Provenance

conn = connect()
c = conn.cursor()

# Get all 5 entries with full details
rows = c.execute("""
    SELECT rowid, id, name, source, latitude, longitude, 
           landmark_type, faith_tradition, denomination, city, state
    FROM churches WHERE faith='Jewish' AND country='ID'
    ORDER BY source, name
""").fetchall()

print("Before dedup:")
for r in rows:
    print(f"  rowid={r[0]:>8}  id={str(r[1] or ''):>8}  source={r[3]:25s}  {r[2][:60]:60s}")
    if r[1]:
        enr = c.execute("SELECT COUNT(*) FROM church_enrichment WHERE church_id=?", (r[1],)).fetchone()[0]
        src = c.execute("SELECT COUNT(*) FROM church_sources WHERE church_id=?", (r[1],)).fetchone()[0]
        print(f"    enrichment={enr}  sources={src}")
print()

# Strategy: Keep the osm_import entry (most precise coords)
# Merge enrichment/sources to it if needed, delete the other 4
# OSM entry is row with source='osm_import' - rowid=?, name='Sinagog Shaar Hashamayim'

c.execute("SELECT rowid, id FROM churches WHERE faith='Jewish' AND country='ID' AND source='osm_import'")
keep_rowid, keep_id = c.fetchone()
print(f"Keeping: rowid={keep_rowid}, church_id={keep_id}")

# Get the holy_sites_import entries
holy_rows = c.execute("""
    SELECT rowid, id, name FROM churches 
    WHERE faith='Jewish' AND country='ID' AND source='holy_sites_import'
""").fetchall()

with Provenance(conn, "_dedup_id_synagogues.py", source="manual_dedup",
                action="updated", fields="church_sources,deleted",
                params="merge_5_shaar_hashamayim_copies") as prov:
    
    for rowid, church_id, name in holy_rows:
        # If the duplicate has a church_id (enrichment/sources), merge to keep
        if church_id and keep_id:
            # Move church_sources
            c.execute("UPDATE church_sources SET church_id=? WHERE church_id=?", (keep_id, church_id))
            # Move church_enrichment
            c.execute("UPDATE church_enrichment SET church_id=? WHERE church_id=?", (keep_id, church_id))
            # Remove old provenance entries referencing this church_id
            c.execute("DELETE FROM provenance_log WHERE church_id=?", (church_id,))
        
        # Delete the duplicate church record
        c.execute("DELETE FROM churches WHERE rowid=?", (rowid,))
        num = c.execute("SELECT changes()").fetchone()[0]
        if num:
            print(f"  Deleted rowid={rowid} ({name[:60]})")
    
    total = len(holy_rows)
    prov.churches_updated = total
    prov.records_attempted = total
    prov.records_matched = total

conn.commit()

# Verify
c2 = conn.cursor()
remaining = c2.execute("SELECT rowid, id, name, source FROM churches WHERE faith='Jewish' AND country='ID'").fetchall()
print(f"\nRemaining ({len(remaining)}):")
for r in remaining:
    print(f"  rowid={r[0]:>8}  id={str(r[1] or ''):>8}  {r[2][:60]:60s}  source={r[3]}")
    if r[1]:
        enr = c2.execute("SELECT COUNT(*) FROM church_enrichment WHERE church_id=?", (r[1],)).fetchone()[0]
        src = c2.execute("SELECT COUNT(*) FROM church_sources WHERE church_id=?", (r[1],)).fetchone()[0]
        print(f"    enrichment={enr}  sources={src}")

conn.close()
