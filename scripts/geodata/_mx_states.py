"""Check what Mexican state codes exist and how many are unmatched"""
import sqlite3
conn = sqlite3.connect('churches.db')

# What states do MX churches have?
print('=== ALL MX CHURCHES BY STATE ===')
for r in conn.execute("""
    SELECT state, COUNT(*) n FROM churches WHERE country='MX' GROUP BY 1 ORDER BY 2 DESC
"""):
    print(f'  {r[0] or "NULL":30s} {r[1]:>8,}')

# How many MX states have both abbreviated AND full names?
print('\n=== DUPLICATE STATE FORMATS (both code + name) ===')
for r in conn.execute("""
    SELECT state, COUNT(*) n FROM churches WHERE country='MX' 
    AND state IN (SELECT state FROM churches WHERE country='MX' GROUP BY 1 HAVING COUNT(DISTINCT LENGTH(state)) > 1)
    GROUP BY 1 ORDER BY 2 DESC LIMIT 20
"""):
    print(f'  {r[0]:25s} {r[1]:>5}')

# Total with abbreviated codes vs full names
abbrev = conn.execute("SELECT COUNT(*) FROM churches WHERE country='MX' AND LENGTH(state) <= 5").fetchone()[0]
full = conn.execute("SELECT COUNT(*) FROM churches WHERE country='MX' AND LENGTH(state) > 5").fetchone()[0]
print(f'\n  Abbreviated codes (≤5 chars): {abbrev:,}')
print(f'  Full names (>5 chars): {full:,}')

# What about churches NOT in MX that have Mexican-looking state names?
print('\n=== NON-MX CHURCHES WITH MEXICAN STATE NAMES ===')
mexican_full = ['Baja California','Sonora','Chihuahua','Yucatan','Yucatán','Jalisco',
                'Guanajuato','Puebla','Tlaxcala','Tamaulipas','Tabasco','Sinaloa',
                'Morelos','Michoacan','Michoacán','Guerrero','Chiapas','Campeche',
                'Queretaro','Querétaro','Veracruz','Oaxaca','Coahuila','Nuevo Leon',
                'Nuevo León','Durango','Zacatecas','Aguascalientes','Colima',
                'Hidalgo','Nayarit','Quintana Roo','San Luis Potosi']
for state in mexican_full:
    n = conn.execute("SELECT COUNT(*) FROM churches WHERE state=? AND country!='MX'", (state,)).fetchone()[0]
    if n > 0:
        print(f'  {state:30s} country!=MX: {n:,}')

# The key question: how many churches with Mexican state codes are NOT country='MX'?
print('\n=== STATE CODES THAT SHOULD BE MX BUT AREN\'T ===')
# Check the specific abbreviated codes
mx_codes = ['CMX','SLP','BCS','BCN','CHH','CHP','COA','COL','DIF','DGO',
            'GRO','GUA','HID','JAL','MCH','MEX','MOA','NAY','NLE','OAX',
            'PUE','QUE','ROO','SIN','SON','TAB','TAM','TLA','VER','YUC','ZAC']
for code in mx_codes:
    n = conn.execute("SELECT COUNT(*) FROM churches WHERE state=? AND country!='MX'", (code,)).fetchone()[0]
    if n > 0:
        print(f'  {code}: {n:,} churches with wrong country')

conn.close()
