"""
show_stats.py — Display current GRID database statistics
"""
import sqlite3, os

CHURCHES_DB = r"E:\grid\churches.db"
conn = sqlite3.connect(CHURCHES_DB)
c = conn.cursor()

total = c.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
gps = c.execute("""
    SELECT COUNT(*) FROM churches
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
      AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180
""").fetchone()[0]

print("=" * 60)
print("  GRID DATABASE STATISTICS")
print("=" * 60)

print(f"\n  File:     {os.path.getsize(CHURCHES_DB) / 1_000_000:.0f} MB")
tables = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
print(f"  Tables:   {tables}")
print(f"  Records:  {total:,}")
print(f"  GPS:      {gps:,} ({gps/total*100:.1f}%)")
countries = c.execute("SELECT COUNT(DISTINCT COALESCE(country, 'NULL')) FROM churches").fetchone()[0]
print(f"  Country:  {countries}")
state = c.execute("SELECT COUNT(*) FROM churches WHERE state IS NOT NULL AND state != ''").fetchone()[0]
print(f"  State:    {state:,} ({state/total*100:.1f}%)")
denoms = c.execute("SELECT COUNT(DISTINCT COALESCE(denomination, 'NULL')) FROM churches").fetchone()[0]
print(f"  Denoms:   {denoms}")

print(f"\n{'─' * 60}")
print("  Faith")
for r in c.execute("SELECT COALESCE(NULLIF(faith, ''), 'NULL'), COUNT(*) FROM churches GROUP BY 1 ORDER BY 2 DESC"):
    print(f"    {str(r[0]):15s}: {r[1]:>8,} ({r[1]/total*100:.1f}%)")
null_faith = c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith = ''").fetchone()[0]
print(f"    {'NULL faith':15s}: {null_faith} ✅")

print(f"\n{'─' * 60}")
print("  nearest_city_km (confidence tiers)")
tiers = [("< 1 km", 0, 1), ("1-5 km", 1, 5), ("5-10 km", 5, 10),
         ("10-25 km", 10, 25), ("25-50 km", 25, 50), ("50-100 km", 50, 100)]
for label, lo, hi in tiers:
    cnt = c.execute("SELECT COUNT(*) FROM churches WHERE nearest_city_km >= ? AND nearest_city_km < ?", (lo, hi)).fetchone()[0]
    print(f"    {label:15s}: {cnt:>8,}")
cnt100 = c.execute("SELECT COUNT(*) FROM churches WHERE nearest_city_km >= 100").fetchone()[0]
print(f"    {'>= 100 km':15s}: {cnt100:>8,}")
nocnt = c.execute("SELECT COUNT(*) FROM churches WHERE nearest_city_km IS NULL AND latitude IS NOT NULL").fetchone()[0]
print(f"    {'No distance':15s}: {nocnt:>8,}")

print(f"\n{'─' * 60}")
print("  Sources (source_primary)")
for r in c.execute("SELECT COALESCE(source_primary, 'NULL'), COUNT(*) FROM churches GROUP BY 1 ORDER BY 2 DESC LIMIT 12"):
    print(f"    {str(r[0]):30s}: {r[1]:>8,} ({r[1]/total*100:.1f}%)")

print(f"\n{'─' * 60}")
print("  Enrichment Tables")
for tbl in ["provenance_log", "church_enrichment", "church_contact_values",
            "church_addresses", "address_components"]:
    cnt = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"    {tbl:25s}: {cnt:>8,}")

print(f"\n{'─' * 60}")
print("  Hierarchy Tables")
for tbl in ["lds_hierarchy", "lutheran_hierarchy", "jw_hierarchy", "sa_hierarchy",
            "chabad_hierarchy", "moravian_hierarchy", "ahmadiyya_hierarchy"]:
    cnt = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"    {tbl:25s}: {cnt:>8,}")

conn.close()
print(f"\n{'=' * 60}")
