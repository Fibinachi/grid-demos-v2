"""Analyze what provenance can be reconstructed from source field + timestamps."""
import sqlite3, os, time
from collections import defaultdict

conn = sqlite3.connect('churches.db', timeout=60)
c = conn.cursor()

# ── 1. What timestamp columns exist? ──
print("=== Timestamp columns with data ===")
c.execute('PRAGMA table_info(churches)')
for r in c.fetchall():
    name = r[1]
    if any(k in name.lower() for k in ['time', 'date', 'at', 'created']):
        c.execute(f'SELECT COUNT(*) FROM churches WHERE {name} IS NOT NULL')
        n = c.fetchone()[0]
        print(f"  churches.{name:30s} {n:>12,} non-null")

c.execute('PRAGMA table_info(church_enrichment)')
for r in c.fetchall():
    name = r[1]
    if any(k in name.lower() for k in ['time', 'date', 'at', 'created', 'updated']):
        c.execute(f'SELECT COUNT(*) FROM church_enrichment WHERE {name} IS NOT NULL')
        n = c.fetchone()[0]
        print(f"  church_enrichment.{name:30s} {n:>12,} non-null")

# ── 2. Check osm_timestamp by source ──
print("\n=== Top sources: osm_timestamp coverage ===")
for r in c.execute("""
    SELECT source, COUNT(*) n,
           COUNT(CASE WHEN osm_timestamp IS NOT NULL THEN 1 END) has_ts,
           MIN(osm_timestamp), MAX(osm_timestamp)
    FROM churches
    GROUP BY source
    ORDER BY n DESC
    LIMIT 25
"""):
    print(f"  {str(r[0] or 'NULL'):50s} {r[1]:>10,}  osm={r[2]:>10,}  [{r[3]}, {r[4]}]")

# ── 3. Source composition: single vs composite ──
print("\n=== Source type breakdown ===")
c.execute("""
    SELECT
        CASE WHEN source LIKE '%+%' THEN 'composite'
             ELSE 'single'
        END as src_type,
        COUNT(*) n
    FROM churches
    GROUP BY src_type
""")
for r in c.fetchall():
    print(f"  {r[0]:15s} {r[1]:>12,}")

# ── 4. What unique base sources exist? ──
print("\n=== Base sources (before first +) ===")
base_counts = defaultdict(int)
for r in c.execute("SELECT source, COUNT(*) FROM churches GROUP BY source"):
    src, n = r
    if src:
        base = src.split('+')[0].split(',')[0].strip()
        base_counts[base] += n

for base, n in sorted(base_counts.items(), key=lambda x: -x[1])[:20]:
    print(f"  {base:45s} {n:>10,}")

# ── 5. Check enrichment last_updated by source ──
print("\n=== Enrichment timestamps by top sources ===")
for r in c.execute("""
    SELECT c.source, COUNT(*) n,
           MIN(e.last_updated), MAX(e.last_updated)
    FROM churches c
    JOIN church_enrichment e ON c.id = e.church_id
    WHERE e.last_updated IS NOT NULL
    GROUP BY c.source
    ORDER BY n DESC
    LIMIT 15
"""):
    print(f"  {str(r[0] or 'NULL'):50s} {r[1]:>8,}  [{r[2]}, {r[3]}]")

# ── 6. How many have NO timestamp at all? ──
print("\n=== Gaps ===")
c.execute("""
    SELECT COUNT(*) FROM churches c
    LEFT JOIN church_enrichment e ON c.id = e.church_id
    WHERE c.osm_timestamp IS NULL
      AND (e.last_updated IS NULL)
""")
no_ts = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches")
total = c.fetchone()[0]
print(f"  Churches with NO timestamp anchor: {no_ts:,} / {total:,} ({no_ts/total*100:.1f}%)")

# ── 7. Filesystem timestamps of import scripts ──
print("\n=== Script file modification times ===")
script_dir = os.path.dirname(__file__)
for fname in sorted(os.listdir(script_dir)):
    if fname.startswith('_import_') or fname.startswith('import_'):
        fpath = os.path.join(script_dir, fname)
        mtime = os.path.getmtime(fpath)
        mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
        size_kb = os.path.getsize(fpath) / 1024
        print(f"  {mtime_str}  {fname:40s}  {size_kb:6.0f} KB")

conn.close()
