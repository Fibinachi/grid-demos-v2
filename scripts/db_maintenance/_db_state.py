"""Comprehensive state-of-the-database report."""
import sqlite3
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM churches")
total = c.fetchone()[0]
print(f"TOTAL RECORDS: {total:,}\n")

# ── Faith ───────────────────────────────────────────────────────────────────
print("=" * 60)
print("FAITH CLASSIFICATION")
print("=" * 60)
c.execute("SELECT faith, COUNT(*) FROM churches GROUP BY faith ORDER BY COUNT(*) DESC")
for faith, cnt in c.fetchall():
    pct = cnt/total*100
    bar = "█" * int(pct/2)
    print(f"  {str(faith or 'NULL'):<20} {cnt:>10,}  ({pct:5.1f}%) {bar}")

null_faith = c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''").fetchone()[0]
print(f"\n  NULL faith: {null_faith:,} ({(total-null_faith)/total*100:.1f}% classified)")

# ── Denomination (Christian only) ───────────────────────────────────────────
print("\n" + "=" * 60)
print("DENOMINATION (Christian records)")
print("=" * 60)
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian'")
christian_total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian' AND (denomination IS NULL OR denomination='')")
christian_null = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian' AND denomination IS NOT NULL AND denomination != ''")
christian_tagged = c.fetchone()[0]

print(f"  Total Christian: {christian_total:,}")
print(f"  With denomination: {christian_tagged:,} ({christian_tagged/christian_total*100:.1f}%)")
print(f"  NULL denomination: {christian_null:,} ({christian_null/christian_total*100:.1f}%)")

# Top denominations
print("\n  Top denominations:")
c.execute("""SELECT denomination, COUNT(*) FROM churches 
WHERE faith='Christian' AND denomination IS NOT NULL AND denomination != ''
GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 12""")
for denom, cnt in c.fetchall():
    print(f"    {denom:<35} {cnt:>10,}")

# ── canonical_status ────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("CANONICAL STATUS (all records)")
print("=" * 60)
c.execute("SELECT canonical_status, COUNT(*) FROM churches WHERE canonical_status IS NOT NULL GROUP BY canonical_status ORDER BY COUNT(*) DESC")
for status, cnt in c.fetchall():
    print(f"  {status:<25} {cnt:>10,}")
c.execute("SELECT COUNT(*) FROM churches WHERE canonical_status IS NULL")
print(f"  {'NULL':<25} {c.fetchone()[0]:>10,}")

# ── Country ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("COUNTRY GEOCODING")
print("=" * 60)
c.execute("SELECT COUNT(*) FROM churches WHERE country='ZZ'")
zz = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE country IS NULL OR country=''")
null_country = c.fetchone()[0]
print(f"  ZZ (unknown): {zz:,}")
print(f"  NULL/empty: {null_country:,}")

# ── Source gaps ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("TOP SOURCES WITH NULL FAITH")
print("=" * 60)
c.execute("""SELECT source, COUNT(*) FROM churches 
WHERE (faith IS NULL OR faith='')
GROUP BY source ORDER BY COUNT(*) DESC LIMIT 10""")
for src, cnt in c.fetchall():
    print(f"  {str(src or 'NULL')[:50]:<50} {cnt:>10,}")

# ── Key stats ───────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("KEY METRICS")
print("=" * 60)
c.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL")
with_coords = c.fetchone()[0]
print(f"  With coordinates: {with_coords:,} ({with_coords/total*100:.1f}%)")
print(f"  Faith classified: {total-null_faith:,} ({(total-null_faith)/total*100:.1f}%)")
print(f"  Denom classified (Christian): {christian_tagged:,} ({christian_tagged/christian_total*100:.1f}%)")

conn.close()
