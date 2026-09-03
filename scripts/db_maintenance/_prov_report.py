"""Provenance Report — GrantWizard DB (2026-06-18)"""
import sqlite3, os, time

DB = 'churches.db'
size_mb = os.path.getsize(DB) / 1024 / 1024

conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

print("=" * 72)
print("  GRANTWIZARD PROVENANCE REPORT")
print(f"  Generated: 2026-06-18 | DB: {DB} ({size_mb:.0f} MB)")
print("=" * 72)

# ──── 1. OVERVIEW ────
print("\n─── 1. DATABASE OVERVIEW ───")
c.execute("SELECT COUNT(*) FROM churches"); total = c.fetchone()[0]
c.execute("SELECT COUNT(DISTINCT country) FROM churches"); n_countries = c.fetchone()[0]
c.execute("SELECT COUNT(DISTINCT denomination) FROM churches WHERE denomination IS NOT NULL AND denomination != ''"); n_denoms = c.fetchone()[0]

print(f"  Total churches:        {total:>12,}")
print(f"  Countries represented: {n_countries:>12}")
print(f"  Unique denominations:  {n_denoms:>12}")

# ──── 2. CHURCHES BY SOURCE ────
print("\n─── 2. CHURCHES BY SOURCE ───")
for r in c.execute("""
    SELECT COALESCE(source,'UNKNOWN'), COUNT(*) AS n
    FROM churches GROUP BY source ORDER BY n DESC
"""):
    print(f"  {r[0]:35s} {r[1]:>10,}")

# ──── 3. CHURCHES BY COUNTRY ────
print("\n─── 3. CHURCHES BY COUNTRY ───")
for r in c.execute("""
    SELECT COALESCE(country,'UNKNOWN'), COUNT(*) AS n
    FROM churches GROUP BY country ORDER BY n DESC
"""):
    print(f"  {r[0]:10s} {r[1]:>10,}")

# ──── 4. PROVENANCE LOG ────
print("\n─── 4. PROVENANCE LOG (operations tracked) ───")
c.execute("SELECT COUNT(*) FROM provenance_log")
n_logs = c.fetchone()[0]
print(f"  Total logged operations: {n_logs}")

if n_logs > 0:
    for r in c.execute("SELECT * FROM provenance_log ORDER BY id"):
        # (id, source, script_name, started_at, completed_at, churches_updated,
        #  churches_inserted, fields_populated, parameters, records_attempted,
        #  records_matched, status, notes, error)
        rid = r[0]
        src = str(r[1]) if r[1] else '?'
        script = str(r[2]) if r[2] else '?'
        started = str(r[3]) if r[3] else '?'
        upd = r[5] or 0
        ins = r[6] or 0
        att = r[9] or 0
        mat = r[10] or 0
        status = str(r[11]) if r[11] else '?'
        print(f"  [{rid}] {src:25s} {script:55s}")
        print(f"         {started} | upd={upd:>8,} ins={ins:>8,} attempted={att:>8,} matched={mat:>8,} {status}")
else:
    print("  ⚠ provenance_log is EMPTY — no operations have been tracked!")

# ──── 5. ENRICHMENT CHANGE LOG ────
print("\n─── 5. ENRICHMENT CHANGE LOG ───")
c.execute("SELECT COUNT(*), COUNT(DISTINCT church_id), COUNT(DISTINCT change_source), COUNT(DISTINCT field_name) FROM enrichment_change_log")
total_changes, n_churches, n_sources, n_fields = c.fetchone()
print(f"  Total changes: {total_changes:>10,} across {n_churches:,} churches, {n_sources} sources, {n_fields} fields")

print("\n  Top change sources:")
for r in c.execute("""
    SELECT change_source, COUNT(*) AS n FROM enrichment_change_log
    GROUP BY change_source ORDER BY n DESC LIMIT 15
"""):
    print(f"    {r[0]:45s} {r[1]:>8,}")

print("\n  Top changed fields:")
for r in c.execute("""
    SELECT field_name, COUNT(*) AS n FROM enrichment_change_log
    GROUP BY field_name ORDER BY n DESC LIMIT 15
"""):
    print(f"    {r[0]:45s} {r[1]:>8,}")

print("\n  Recent changes (last 10):")
for r in c.execute("""
    SELECT church_id, field_name,
           COALESCE(SUBSTR(old_value,1,40),'NULL'),
           COALESCE(SUBSTR(new_value,1,40),'NULL'),
           change_source, changed_at
    FROM enrichment_change_log ORDER BY changed_at DESC LIMIT 10
"""):
    print(f"    church={r[0]:>7,}  {str(r[1]):30s}  {str(r[2] or 'NULL'):40s} -> {str(r[3] or 'NULL'):40s}  [{r[4]}]  {r[5]}")

# ──── 6. CHURCH SOURCES CROSS-REFERENCE ────
print("\n─── 6. CHURCH_SOURCES LINK TABLE ───")
c.execute("SELECT COUNT(*), COUNT(DISTINCT church_id), COUNT(DISTINCT source_id) FROM church_sources")
cs_total, cs_churches, cs_sids = c.fetchone()
print(f"  Total links: {cs_total:>10,} | Unique churches: {cs_churches:>9,} | Unique source IDs: {cs_sids}")

print("\n  Top source names:")
for r in c.execute("""
    SELECT COALESCE(source_name,'?'), COUNT(*) AS n
    FROM church_sources GROUP BY source_name ORDER BY n DESC LIMIT 15
"""):
    print(f"    {r[0]:45s} {r[1]:>8,}")

# ──── 7. DATA FRESHNESS ────
print("\n─── 7. DATA FRESHNESS ───")
for r in c.execute("""
    SELECT 'enrichment_last', MAX(last_updated) FROM church_enrichment WHERE last_updated IS NOT NULL
    UNION ALL
    SELECT 'contacts_last', MAX(website_last_verified) FROM church_contacts WHERE website_last_verified IS NOT NULL
    UNION ALL
    SELECT 'latest_prov_log', MAX(completed_at) FROM provenance_log WHERE completed_at IS NOT NULL
    UNION ALL
    SELECT 'osm_timestamp_max', MAX(osm_timestamp) FROM churches WHERE osm_timestamp IS NOT NULL
"""):
    print(f"  {r[0]:25s} {r[1] or 'N/A'}")

# ──── 8. GAPS & WARNINGS ────
print("\n─── 8. PROVENANCE GAPS ───")
# Churches with no source
c.execute("SELECT COUNT(*) FROM churches WHERE source IS NULL OR source = ''")
no_source = c.fetchone()[0]
print(f"  Churches with no source:        {no_source:>8,}  ({no_source/total*100:.1f}%)")

# Churches with no church_sources link
c.execute("""
    SELECT COUNT(*) FROM churches c
    WHERE NOT EXISTS (SELECT 1 FROM church_sources cs WHERE cs.church_id = c.id)
""")
no_link = c.fetchone()[0]
print(f"  Churches with no source link:   {no_link:>8,}  ({no_link/total*100:.1f}%)")

# provenance_log size
if n_logs == 0:
    print("  ⚠ CRITICAL: provenance_log is EMPTY!")
    print("    No import/enrichment operations have been recorded.")
    print("    Run provenance logging in scripts that modify churches table.")

conn.close()
print("\n" + "=" * 72)
print("  END OF REPORT")
print("=" * 72)
