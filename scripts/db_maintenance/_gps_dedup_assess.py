"""Quick assessment of GPS dedup scope."""
import sqlite3

conn = sqlite3.connect(r'E:\grid\churches.db')
total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
with_gps = conn.execute('SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL').fetchone()[0]

# Exact GPS duplicates (6 decimal places ~0.1m)
exact_dup_groups = conn.execute('''
    SELECT COUNT(*) FROM (
        SELECT latitude, longitude, COUNT(*) as cnt
        FROM churches
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY ROUND(latitude, 6), ROUND(longitude, 6)
        HAVING cnt > 1
    )
''').fetchone()[0]

total_dup_records = conn.execute('''
    SELECT COALESCE(SUM(cnt), 0) FROM (
        SELECT COUNT(*) as cnt
        FROM churches
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY ROUND(latitude, 6), ROUND(longitude, 6)
        HAVING cnt > 1
    )
''').fetchone()[0]

print(f'Total records: {total:,}')
print(f'With GPS: {with_gps:,}')
print(f'Exact GPS dupe groups (6dp ~0.1m): {exact_dup_groups:,}')
print(f'Total records in exact GPS dupe groups: {total_dup_records:,}')

print()
print('Top 30 GPS dupe clusters:')
rows = conn.execute('''
    SELECT ROUND(latitude,6) as lat, ROUND(longitude,6) as lon, COUNT(*) as cnt,
           GROUP_CONCAT(DISTINCT source) as sources,
           GROUP_CONCAT(DISTINCT faith) as faiths,
           GROUP_CONCAT(DISTINCT COALESCE(denomination,'?')) as denoms,
           GROUP_CONCAT(DISTINCT COALESCE(landmark_type,'?')) as lm_types
    FROM churches
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    GROUP BY ROUND(latitude,6), ROUND(longitude,6)
    HAVING cnt > 1
    ORDER BY cnt DESC
    LIMIT 30
''').fetchall()
for r in rows:
    print(f'  ({r[0]:.6f}, {r[1]:.6f}) cnt={r[2]} src=[{r[3]}] faith=[{r[4]}] denom=[{r[5]}] lm=[{r[6]}]')

# Child tables that reference churches
child_tables = [
    'church_contacts', 'church_enrichment', 'provenance_log',
    'church_sources', 'church_fcc', 'church_gnis', 'church_nrhp',
    'church_broadband', 'church_postal_admin',
    'church_classification_meta', 'church_metro_area',
]
print()
print('Child tables referencing churches.id:')
for t in child_tables:
    try:
        refs = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        # Check if there's a churches.id reference
        col_info = conn.execute(f'PRAGMA table_info({t})').fetchall()
        has_church_id = any(c[1] in ('church_id', 'churches_id') for c in col_info)
        print(f'  {t}: {refs:,} rows, has_church_id={has_church_id}')
    except Exception as e:
        print(f'  {t}: ERROR {e}')

# Also check enrichment_change_log
try:
    ecl = conn.execute('SELECT COUNT(*) FROM enrichment_change_log').fetchone()[0]
    print(f'  enrichment_change_log: {ecl:,} rows')
except Exception as e:
    print(f'  enrichment_change_log: ERROR {e}')

conn.close()
