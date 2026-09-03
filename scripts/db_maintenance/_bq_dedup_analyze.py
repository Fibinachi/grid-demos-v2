"""Analyze duplicates and enrichment recency for BigQuery upload."""
import sqlite3

conn = sqlite3.connect("churches.db")
c = conn.cursor()

# Check churches table columns
c.execute("PRAGMA table_info(churches)")
cols = [(r[1], r[2]) for r in c.fetchall()]
col_names = [r[0] for r in cols]
print(f"churches: {len(cols)} columns")
c.execute("SELECT COUNT(*) FROM churches")
print(f"Total rows: {c.fetchone()[0]:,}")

# ============================================================
# DUPLICATE ANALYSIS
# ============================================================

# Duplicate IDs
c.execute("SELECT COUNT(*) FROM (SELECT id, COUNT(*) as cnt FROM churches GROUP BY id HAVING cnt > 1)")
dup_id_count = c.fetchone()[0]
c.execute("SELECT SUM(cnt) FROM (SELECT id, COUNT(*) as cnt FROM churches GROUP BY id HAVING cnt > 1)")
dup_id_rows = c.fetchone()[0]
print(f"\nDuplicate IDs: {dup_id_count:,} IDs, {dup_id_rows:,} total rows")

# Show sample dup IDs
c.execute("SELECT id, COUNT(*) as cnt FROM churches GROUP BY id HAVING cnt > 1 ORDER BY cnt DESC LIMIT 5")
print("Sample duplicate IDs:")
for row in c.fetchall():
    print(f"  id={row[0]}: {row[1]} rows")

# Look at a specific dup
c.execute("SELECT id, name, source, denomination, latitude, longitude FROM churches WHERE id=545122 LIMIT 3")
print("\nSample id=545122:")
for row in c.fetchall():
    name = (row[1] or "NULL")[:60]
    src = (row[2] or "NULL")[:30]
    print(f"  id={row[0]} | name={name} | src={src} | denom={row[3]} | lat={row[4]} | lon={row[5]}")

# ============================================================
# Name-based duplicates
# ============================================================
c.execute("""
    SELECT COUNT(*) FROM (
        SELECT name, COUNT(DISTINCT source) as src_count
        FROM churches
        WHERE name IS NOT NULL AND name != ''
        GROUP BY name
        HAVING src_count > 1
    )
""")
print(f"\nNames appearing in multiple sources: {c.fetchone()[0]:,}")

# ============================================================
# ENRICHMENT ANALYSIS
# ============================================================
print("\n=== ENRICHMENT DEPTH ===")
c.execute("""
    SELECT 
        CASE 
            WHEN e.church_id IS NOT NULL AND e.last_updated IS NOT NULL THEN 'enriched_with_date'
            WHEN e.church_id IS NOT NULL THEN 'enriched_no_date'
            ELSE 'not_enriched'
        END as enrichment_status,
        COUNT(*) as cnt
    FROM churches c
    LEFT JOIN church_enrichment e ON c.id = e.church_id
    GROUP BY 1
    ORDER BY 2 DESC
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

# Enriched fields count (density)
print("\n=== ENRICHMENT FIELD DENSITY ===")
c.execute("PRAGMA table_info(church_enrichment)")
enrich_cols = [r[1] for r in c.fetchall() if r[1] not in ('church_id', 'last_updated', 'notes')]
c.execute("SELECT COUNT(*) FROM church_enrichment")
total_enrich = c.fetchone()[0]
for col in enrich_cols[:15]:  # first 15
    c.execute(f"SELECT COUNT(*) FROM church_enrichment WHERE {col} IS NOT NULL AND {col} != ''")
    cnt = c.fetchone()[0]
    if cnt > 0:
        print(f"  {col}: {cnt:,} ({cnt/total_enrich*100:.0f}%)")

# Most recently enriched records
print("\n=== RECENT ENRICHMENT TIMELINE ===")
c.execute("""
    SELECT substr(last_updated, 1, 10) as dt, COUNT(*) 
    FROM church_enrichment 
    WHERE last_updated IS NOT NULL 
    GROUP BY dt 
    ORDER BY dt DESC 
    LIMIT 15
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

# ============================================================
# DUPLICATE DEDUP STRATEGY TEST
# ============================================================
print("\n=== DEDUP TEST: Same lat/lon, pick most enriched ===")
c.execute("""
    SELECT c.id, c.name, c.source, c.denomination, c.latitude, c.longitude,
           e.last_updated,
           (CASE WHEN e.diocese IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN e.denomination IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN e.attendance_arda IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN e.jewish_movement IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN e.muslim_affiliation IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN e.jewish_classification_source IS NOT NULL THEN 1 ELSE 0 END
           ) as enrich_score
    FROM churches c
    LEFT JOIN church_enrichment e ON c.id = e.church_id
    WHERE c.latitude = 29.807771660642 AND c.longitude = -95.16702204528
    ORDER BY enrich_score DESC, e.last_updated DESC
    LIMIT 5
""")
print("  Top 5 at a high-duplicate location (sorted by enrichment):")
for row in c.fetchall():
    name = (row[1] or "NULL")[:50]
    src = (row[2] or "NULL")[:20]
    print(f"  id={row[0]:>8} | name={name} | src={src} | enrich_score={row[7]} | last_upd={row[6]}")

conn.close()

