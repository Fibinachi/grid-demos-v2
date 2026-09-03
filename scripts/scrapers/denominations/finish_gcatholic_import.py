"""Finish GCatholic import: add church_contacts and verify."""
import sqlite3, csv
from datetime import datetime, timezone

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
    print("Nothing to do — run import_gcatholic_global.py first")
    conn.close()
    exit()

# ── Read CSV for websites ──
rows = list(csv.DictReader(open('E:/grid/data/gcatholic_global.csv', 'r', encoding='utf-8')))
csv_websites = {}
for r in rows:
    w = (r.get('website') or '').strip()
    if w and w.startswith('http'):
        csv_websites[r['gcatholic_id']] = w
print(f"CSV rows with real websites: {len(csv_websites):,}")

# ── Get site_id mapping ──
c.execute("SELECT osm_id, site_id FROM holy_sites WHERE source_primary=?", (SOURCE,))
gc_to_site = {r[0]: r[1] for r in c.fetchall()}

# ── Bulk insert contacts ──
contact_rows = []
for gc_id, website in csv_websites.items():
    site_id = gc_to_site.get(gc_id)
    if not site_id:
        continue
    c.execute("SELECT id FROM churches WHERE holy_site_id=? AND source=? LIMIT 1", (site_id, SOURCE))
    ch = c.fetchone()
    if ch:
        contact_rows.append((ch[0], website, SOURCE))

print(f"Website contacts to insert: {len(contact_rows):,}")

if contact_rows:
    c.executemany("""
        INSERT OR IGNORE INTO church_contacts 
        (church_id, website, website_source, has_website, website_scrape_status)
        VALUES (?,?,?,1,'found')
    """, contact_rows)
    conn.commit()
    print(f"  Inserted {c.rowcount:,}")

# ── Also add gcatholic URLs as a secondary website source ──
gc_urls = {}
for r in rows:
    u = (r.get('url') or '').strip()
    if u and u.startswith('http'):
        gc_urls[r['gcatholic_id']] = u

url_rows = []
for gc_id, url in gc_urls.items():
    site_id = gc_to_site.get(gc_id)
    if not site_id:
        continue
    c.execute("SELECT id FROM churches WHERE holy_site_id=? AND source=? LIMIT 1", (site_id, SOURCE))
    ch = c.fetchone()
    if ch:
        url_rows.append((ch[0], url, 'gcatholic_url'))

if url_rows:
    c.executemany("""
        INSERT OR IGNORE INTO church_contacts 
        (church_id, website, website_source, has_website, website_scrape_status)
        VALUES (?,?,?,1,'found')
    """, url_rows)
    conn.commit()
    print(f"  Gcatholic URLs added: {len(url_rows):,}")

# ── Verify ──
c.execute("""
    SELECT COUNT(*) FROM church_contacts cc
    INNER JOIN churches c ON cc.church_id = c.id
    WHERE c.source=?
""", (SOURCE,))
print(f"\nFinal: {ch_count:,} churches, {c.fetchone()[0]:,} with contacts")

# Country breakdown
c.execute("SELECT country, COUNT(*) FROM churches WHERE source=? GROUP BY country ORDER BY 2 DESC", (SOURCE,))
print("\nBy country:")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]:,}")

conn.close()
print("\nDone.")
