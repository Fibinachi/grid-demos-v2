"""Finish GCatholic import: add church_contacts via bulk SQL join."""
import sqlite3, csv

SOURCE = 'gcatholic_global'
DB = 'E:/grid/churches.db'

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=60000")
c = conn.cursor()

# ── Check current state ──
c.execute("SELECT COUNT(*) FROM churches WHERE source=?", (SOURCE,))
ch_count = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM holy_sites WHERE source_primary=?", (SOURCE,))
hs_count = c.fetchone()[0]
print(f"Already imported: {ch_count:,} churches, {hs_count:,} holy_sites")

if ch_count == 0:
    print("Nothing to do.")
    conn.close()
    exit()

# ── Load CSV into temp table with gcatholic_id → website mapping ──
print("Building temp table...")
c.execute("CREATE TEMP TABLE _gc_websites (gc_id TEXT, website TEXT, gc_url TEXT)")

rows = list(csv.DictReader(open('E:/grid/data/gcatholic_global.csv', 'r', encoding='utf-8')))
batch = []
for r in rows:
    w = (r.get('website') or '').strip()
    u = (r.get('url') or '').strip()
    if w.startswith('http') or u.startswith('http'):
        batch.append((r['gcatholic_id'], w if w.startswith('http') else '', u if u.startswith('http') else ''))

c.executemany("INSERT INTO _gc_websites VALUES (?,?,?)", batch)
c.execute("CREATE INDEX _gc_ws_idx ON _gc_websites(gc_id)")
print(f"  {len(batch):,} rows with URLs")

# ── Bulk INSERT into church_contacts via join chain ──
# Join: _gc_websites → holy_sites (osm_id = gc_id) → churches (holy_site_id = site_id)
print("Inserting real websites...")
c.execute("""
    INSERT INTO church_contacts 
    (church_id, website, website_source, has_website, website_scrape_status)
    SELECT c.id, g.website, ?, 1, 'found'
    FROM _gc_websites g
    INNER JOIN holy_sites hs ON hs.osm_id = g.gc_id AND hs.source_primary = ?
    INNER JOIN churches c ON c.holy_site_id = hs.site_id AND c.source = ?
    WHERE g.website != ''
""", (SOURCE, SOURCE, SOURCE))
print(f"  Real websites: {c.rowcount:,}")

print("Inserting gcatholic URLs...")
c.execute("""
    INSERT INTO church_contacts 
    (church_id, website, website_source, has_website, website_scrape_status)
    SELECT c.id, g.gc_url, 'gcatholic_url', 1, 'found'
    FROM _gc_websites g
    INNER JOIN holy_sites hs ON hs.osm_id = g.gc_id AND hs.source_primary = ?
    INNER JOIN churches c ON c.holy_site_id = hs.site_id AND c.source = ?
    WHERE g.gc_url != ''
""", (SOURCE, SOURCE))
print(f"  Gcatholic URLs: {c.rowcount:,}")

conn.commit()

# ── Verify ──
c.execute("""
    SELECT COUNT(DISTINCT cc.church_id)
    FROM church_contacts cc
    INNER JOIN churches c ON cc.church_id = c.id
    WHERE c.source=?
""", (SOURCE,))
print(f"\nFinal: {ch_count:,} churches, {c.fetchone()[0]:,} with contacts")

# Country breakdown
c.execute("SELECT country, COUNT(*) FROM churches WHERE source=? GROUP BY country ORDER BY 2 DESC", (SOURCE,))
print("\nBy country:")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]:,}")

# Clean up failed provenance entries
c.execute("DELETE FROM provenance_log WHERE source=? AND records_matched=0", (SOURCE,))

conn.commit()
conn.close()
print("\nDone.")
