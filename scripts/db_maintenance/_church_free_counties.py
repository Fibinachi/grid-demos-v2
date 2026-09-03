import sqlite3
conn = sqlite3.connect('churches.db')

# Create temp table of counties that HAVE churches
conn.execute('''
    CREATE TEMP TABLE church_fips AS
    SELECT DISTINCT county_fips AS fips FROM churches 
    WHERE county_fips IS NOT NULL AND TRIM(county_fips) != ''
    UNION
    SELECT DISTINCT SUBSTR('0' || fips, -5, 5) FROM churches 
    WHERE fips IS NOT NULL AND TRIM(fips) != ''
''')

# Find church-free counties with demographics
rows = conn.execute('''
    SELECT l.county_fips, l.county_name, l.state_fips, l.population, 
           l.total_adherents, l.adherence_rate,
           (SELECT COUNT(*) FROM tract_lookup_us t WHERE t.county_fips = l.county_fips) AS tract_count,
           (SELECT ROUND(AVG(t.total_pop)) FROM tract_lookup_us t WHERE t.county_fips = l.county_fips) AS avg_tract_pop,
           (SELECT ROUND(AVG(t.median_income)) FROM tract_lookup_us t WHERE t.county_fips = l.county_fips) AS avg_tract_income,
           (SELECT ROUND(AVG(CAST(t.households AS FLOAT)),0) FROM tract_lookup_us t WHERE t.county_fips = l.county_fips) AS avg_households
    FROM county_fips_lookup l
    LEFT JOIN church_fips cf ON l.county_fips = cf.fips
    WHERE cf.fips IS NULL
    ORDER BY l.population DESC
''').fetchall()

print(f'=== {len(rows)} CHURCH-FREE COUNTIES ({len(rows)/32.35:.1f}% of US counties) ===')
print()

# Overall stats
total_pop = sum(r[3] or 0 for r in rows)
total_adh = sum(r[4] or 0 for r in rows)
has_pop = [r for r in rows if r[3] and r[3] > 0]
zero_pop = [r for r in rows if not r[3] or r[3] == 0]

print(f'Total population in church-free counties: {total_pop:,}')
print(f'Counties with population > 0: {len(has_pop)}')
print(f'Counties with population = 0: {len(zero_pop)} (uninhabited or data gaps)')
if has_pop:
    print(f'Median population: {has_pop[len(has_pop)//2][3]:,}')
    print(f'Smallest populated: {has_pop[-1][1]} ({has_pop[-1][0]}) — pop {has_pop[-1][3]:,}')
    print(f'Largest: {has_pop[0][1]} ({has_pop[0][0]}) — pop {has_pop[0][3]:,}')
print()

# ── Top 20 by population ──
print('=== TOP 20 CHURCH-FREE COUNTIES BY POPULATION ===')
print(f'{"FIPS":6s} {"County":28s} {"ST":3s} {"Population":>12s} {"Adherents":>12s} {"Rate":>7s} {"Tracts":>7s} {"AvgTractPop":>12s} {"AvgIncome":>10s}')
print('-' * 110)
for r in rows[:20]:
    fips, name, st, pop, adh, rate, tracts, avg_tp, avg_inc, avg_hh = r
    name = (name or '?')[:28]
    print(f'{fips:6s} {name:28s} {st or "?":3s} {pop or 0:>12,} {adh or 0:>12,} {rate or 0:>6.1f}% {tracts or 0:>7} {avg_tp or 0:>12,} {avg_inc or 0:>10,}')

# ── By state ──
print(f'\n=== BY STATE (church-free count / total counties) ===')
from collections import Counter
state_counts = Counter(r[2] for r in rows)
state_total = {}
for r in conn.execute('SELECT state_fips, COUNT(*) FROM county_fips_lookup GROUP BY 1').fetchall():
    state_total[r[0]] = r[1]

for st, cnt in state_counts.most_common(20):
    total_co = state_total.get(st, 0)
    # Get total pop in church-free counties for this state
    st_pop = sum(r[3] or 0 for r in rows if r[2] == st)
    print(f'  State FIPS {st}: {cnt:3d} church-free out of {total_co:3d} counties ({100*cnt/total_co:.0f}%) — pop {st_pop:,}')

# ── Smallest counties ──
print(f'\n=== 20 SMALLEST CHURCH-FREE COUNTIES (by population) ===')
print(f'{"FIPS":6s} {"County":28s} {"ST":3s} {"Population":>12s}')
print('-' * 60)
for r in sorted(rows, key=lambda x: x[3] or 0)[:20]:
    fips, name, st, pop = r[0], r[1], r[2], r[3]
    print(f'{fips:6s} {(name or "?")[:28]:28s} {st or "?":3s} {pop or 0:>12,}')

# ── Demographic summary ──
print(f'\n=== DEMOGRAPHIC PROFILE (populated counties only) ===')
with_tracts = [r for r in has_pop if r[6] and r[6] > 0]
if with_tracts:
    avg_tp = sum(r[7] or 0 for r in with_tracts) / len(with_tracts)
    avg_inc = sum(r[8] or 0 for r in with_tracts) / len(with_tracts)
    avg_hh = sum(r[9] or 0 for r in with_tracts) / len(with_tracts)
    print(f'  Counties with tract data: {len(with_tracts)} of {len(has_pop)}')
    print(f'  Average tract population: {avg_tp:,.0f}')
    print(f'  Average tract median income: ${avg_inc:,.0f}')
    print(f'  Average tract households: {avg_hh:,.0f}')

# ── Comparison: church-having counties ──
has_churches = conn.execute('''
    SELECT COUNT(DISTINCT l.county_fips) 
    FROM county_fips_lookup l 
    WHERE EXISTS (SELECT 1 FROM church_fips cf WHERE cf.fips = l.county_fips)
''').fetchone()[0]
print(f'\n=== COMPARISON ===')
print(f'  Counties WITH churches:    {has_churches:,}')
print(f'  Counties WITHOUT churches:  {len(rows):,}')
print(f'  Total counties in lookup:   {has_churches + len(rows):,}')

# Avg pop comparison
avg_pop_with = conn.execute('''
    SELECT ROUND(AVG(l.population)) FROM county_fips_lookup l
    WHERE EXISTS (SELECT 1 FROM church_fips cf WHERE cf.fips = l.county_fips)
    AND l.population > 0
''').fetchone()[0]
print(f'  Avg population (with churches):    {avg_pop_with:,.0f}')
print(f'  Avg population (without churches): {total_pop / len(has_pop):,.0f}' if has_pop else '  N/A')

conn.close()
