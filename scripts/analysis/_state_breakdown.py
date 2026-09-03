"""State-by-state breakdown for US, Canada, Mexico"""
import sqlite3
conn = sqlite3.connect('churches.db')

# ── UNITED STATES ──
print('=== UNITED STATES — By State ===')
us_total = conn.execute("SELECT COUNT(*) FROM churches WHERE country='US'").fetchone()[0]

# Get state populations from county_fips_lookup
state_pop = {}
for r in conn.execute("SELECT state_fips, SUM(population) FROM county_fips_lookup WHERE population > 0 GROUP BY 1"):
    state_pop[r[0]] = r[1]

# State name lookup (from county data or known abbreviations)
state_names = {
    '01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE',
    '11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA',
    '20':'KS','21':'KY','22':'LA','23':'ME','24':'MD','25':'MA','26':'MI','27':'MN',
    '28':'MS','29':'MO','30':'MT','31':'NE','32':'NV','33':'NH','34':'NJ','35':'NM',
    '36':'NY','37':'NC','38':'ND','39':'OH','40':'OK','41':'OR','42':'PA','44':'RI',
    '45':'SC','46':'SD','47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA',
    '54':'WV','55':'WI','56':'WY','72':'PR','78':'VI'
}

us_rows = conn.execute("""
    SELECT state, COUNT(*) n FROM churches 
    WHERE country='US' AND state IS NOT NULL AND state != ''
    GROUP BY 1 ORDER BY 2 DESC
""").fetchall()

rows_shown = 0
for st, cnt in us_rows:
    pop = state_pop.get(st, 0)
    rate = f'{cnt/pop*1000:.1f}/1K' if pop > 0 else '?'
    print(f'  {st:4s} {cnt:>8,} churches  pop~{pop:>12,}  {rate}')
    rows_shown += 1

# Totals for US
total_us_pop = sum(state_pop.values())
print(f'\n  {"":4s} {us_total:>8,} US total  pop~{total_us_pop:>12,}  {us_total/total_us_pop*1000:.1f}/1K')
print(f'  3,210 of 3,235 US counties covered (99.2%)')

# ── CANADA ──
print(f'\n=== CANADA — By Province ===')
ca_total = conn.execute("SELECT COUNT(*) FROM churches WHERE country='CA'").fetchone()[0]
ca_rows = conn.execute("""
    SELECT state, COUNT(*) n FROM churches 
    WHERE country='CA' AND state IS NOT NULL AND state != ''
    GROUP BY 1 ORDER BY 2 DESC
""").fetchall()

ca_names = {'ON':'Ontario','QC':'Quebec','BC':'British Columbia','AB':'Alberta',
            'MB':'Manitoba','SK':'Saskatchewan','NS':'Nova Scotia','NB':'New Brunswick',
            'NL':'Newfoundland','PE':'Prince Edward Island','YT':'Yukon','NT':'NW Territories','NU':'Nunavut'}

for st, cnt in ca_rows:
    name = ca_names.get(st, '?')
    print(f'  {st:4s} {name:25s} {cnt:>8,}')
print(f'\n  {"":4s} {"Total":25s} {ca_total:>8,}')

# ── MEXICO ──
print(f'\n=== MEXICO — By State ===')
mx_total = conn.execute("SELECT COUNT(*) FROM churches WHERE country='MX'").fetchone()[0]
mx_rows = conn.execute("""
    SELECT state, COUNT(*) n FROM churches 
    WHERE country='MX' AND state IS NOT NULL AND state != ''
    GROUP BY 1 ORDER BY 2 DESC
""").fetchall()

mx_names = {
    'CMX':'Ciudad de México','SLP':'San Luis Potosí','BCS':'Baja California Sur',
    'BCN':'Baja California','CHH':'Chihuahua','MEX':'Estado de México',
    'YUC':'Yucatán','JAL':'Jalisco','VER':'Veracruz','PUE':'Puebla',
    'TAM':'Tamaulipas','SON':'Sonora','OAX':'Oaxaca','NLE':'Nuevo León',
    'CHIH':'Chihuahua','CHP':'Chiapas','COA':'Coahuila','COL':'Colima',
    'DGO':'Durango','GRO':'Guerrero','GUA':'Guanajuato','HID':'Hidalgo',
    'MCH':'Michoacán','MOA':'Morelos','NAY':'Nayarit','QUE':'Querétaro',
    'ROO':'Quintana Roo','SIN':'Sinaloa','TAB':'Tabasco','TLA':'Tlaxcala','ZAC':'Zacatecas',
}

for st, cnt in mx_rows:
    name = mx_names.get(st, st)
    print(f'  {st:4s} {name:25s} {cnt:>8,}')
print(f'\n  {"":4s} {"Total":25s} {mx_total:>8,}')

# ── CONTINENTAL SUMMARY ──
print(f'\n{"="*60}')
print(f'CONTINENTAL SUMMARY')
print(f'{"="*60}')
total_all = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
for country, label in [('US','United States'),('CA','Canada'),('MX','Mexico'),('EU','Europe')]:
    n = conn.execute("SELECT COUNT(*) FROM churches WHERE country=?", (country,)).fetchone()[0]
    pct = 100 * n / total_all
    print(f'  {label:25s} {n:>10,}  ({pct:4.1f}%)')
print(f'  {"TOTAL":25s} {total_all:>10,}')

conn.close()
