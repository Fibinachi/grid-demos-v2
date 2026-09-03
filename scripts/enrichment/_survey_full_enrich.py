"""Survey all domain tables and church_enrichment for full migration plan."""
import sqlite3

db = sqlite3.connect(r'E:\grid\churches.db')
c = db.cursor()

# All tables
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
print('=== ALL TABLES ===')
for t in tables:
    cnt = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    print(f'  {t:35s} {cnt:>8,} rows')

# church_enrichment: count non-null per column to find what's worth moving
print('\n=== church_enrichment: columns with actual data ===')
ce_cols = c.execute('PRAGMA table_info(church_enrichment)').fetchall()
total = c.execute('SELECT COUNT(*) FROM church_enrichment').fetchone()[0]
for col in ce_cols:
    name = col[1]
    if name == 'church_id':
        continue
    # Try count
    try:
        cnt = c.execute(f'SELECT COUNT(*) FROM church_enrichment WHERE "{name}" IS NOT NULL AND "{name}" != "" AND "{name}" != 0').fetchone()[0]
        if cnt > 0:
            pct = 100.0 * cnt / total
            print(f'  {name:40s} {cnt:>8,} ({pct:5.1f}%)')
    except:
        pass

# Check domain tables
print('\n=== EXISTING DOMAIN TABLES ===')
domains = ['church_census_us', 'church_arda', 'church_food_desert', 'fbi_ucr_crime', 
           'broadcast_coverage', 'broadcast_ministries', 'broadcast_transmitters',
           'church_contacts', 'church_staff', 'church_operations', 'church_sources',
           'church_broadcast', 'church_vacancies', 'church_food_desert',
           'election_results', 'arda_counts', 'arda_county_data',
           'census_zip_data', 'county_fips_lookup', 'tract_lookup_us',
           'church_sources', 'church_contacts', 'church_staff']

for t in domains:
    try:
        cnt = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        cols = [r[1] for r in c.execute(f'PRAGMA table_info("{t}")').fetchall()]
        print(f'\n  {t:30s} ({cnt:,} rows):')
        print(f'    Columns: {", ".join(cols[:8])}{"..." if len(cols)>8 else ""}')
    except Exception as e:
        pass

db.close()
