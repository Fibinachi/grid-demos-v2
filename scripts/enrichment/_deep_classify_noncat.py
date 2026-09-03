"""Deep classification of non-Catholic GoodLands diocese records"""
import sqlite3
conn = sqlite3.connect('churches.db')
c = conn.cursor()

# Get ALL non-Catholic records with GoodLands-format diocese, with full detail
c.execute("""
SELECT ch.id, ch.name, ch.faith, ch.faith_tradition, ch.denomination,
       ch.country, ch.latitude, ch.longitude,
       ce.diocese, ce.diocese_detail, ce.archdiocese, ce.province, ce.rite
FROM churches ch
JOIN church_enrichment ce ON ch.id = ce.church_id
WHERE ch.faith_tradition != 'Catholic'
  AND ce.diocese IS NOT NULL AND ce.diocese != ''
  AND (ce.diocese LIKE 'Diocese of%' OR ce.diocese LIKE 'Archdiocese of%')
ORDER BY ch.name
""")

rows = c.fetchall()
print(f"Total records to classify: {len(rows)}")
print()

# Keywords suggesting this is REALLY a Catholic institution
catholic_indicators = [
    'basilica', 'basilique', 'cathedral', 'cathédrale', 'cathedrale',
    'oratory', 'oratoire', 'oratorio',
    'archdiocese', 'archdiocèse', 'archévêché', 'archevêché',
    'diocese of', 'diocèse',
    'monsignor', 'monseigneur',
    'saint patrick', 'st patrick',
    'our lady of', 'notre dame',
    'saint joseph', 'st joseph', 'san giuseppe',
    'santa maria', 'holy name',
    'mary, queen', 'queen of the world',
    'uspenski', # Orthodox but uses diocese structure legitimately
]

for r in rows:
    rid, name, faith, faith_trad, denom, country, lat, lon, dio, dio_detail, arch, prov, rite = r
    name_lower = (name or '').lower()
    
    is_likely_catholic = any(ind in name_lower for ind in catholic_indicators)
    is_anglican = faith_trad == 'Anglican' or (denom or '').lower() in ['anglican', 'episcopal']
    is_orthodox = faith_trad == 'Orthodox' or 'orthodox' in name_lower
    
    label = 'LIKELY_CATHOLIC' if is_likely_catholic else ('ANGLICAN' if is_anglican else ('ORTHODOX' if is_orthodox else 'TRULY_NON_CATH'))
    
    # Check if lat/lon matches country or is bad
    # US is roughly -125 to -65, 25 to 50
    in_us = lat and lon and -125 < lon < -65 and 25 < lat < 50
    country_bad = in_us and country not in ('US', 'USA', 'United States')
    
    print(f"{label:20s} | id={rid:>8} | {str(name):55s} | faith={str(faith):20s} denom={str(denom):20s} | country={country:5s} lat={lat or 0:.4f} lon={lon or 0:.4f} | {dio}")

conn.close()
