"""Check lat distribution of osm_import MX records to understand the scope"""
import sqlite3

db = sqlite3.connect(r"E:\grid\churches.db")
c = db.cursor()

# Lat distribution of osm_import MX records
c.execute("""
    SELECT 
        CASE 
            WHEN latitude >= 45 THEN '45+ (Canada border)'
            WHEN latitude >= 40 THEN '40-45 (Midwest/North)'
            WHEN latitude >= 35 THEN '35-40 (OK/CO/KS)'
            WHEN latitude >= 33 THEN '33-35 (Southwest/TX panhandle)'
            WHEN latitude >= 32 THEN '32-33 (South TX/AZ border)'
            WHEN latitude >= 31 THEN '31-32 (Border zone)'
            WHEN latitude >= 30 THEN '30-31 (Border zone)'
            WHEN latitude >= 29 THEN '29-30 (Border zone)'
            WHEN latitude >= 28 THEN '28-29 (South TX)'
            WHEN latitude >= 27 THEN '27-28 (South TX)'
            WHEN latitude >= 26 THEN '26-27 (Rio Grande)'
            WHEN latitude >= 25 THEN '25-26 (N Mexico/S TX)'
            WHEN latitude IS NULL THEN 'NULL'
            ELSE '< 25 (Mexico proper)'
        END as lat_band,
        COUNT(*) as cnt,
        ROUND(AVG(longitude),2) as avg_lon
    FROM churches 
    WHERE country='MX' AND source='osm_import'
    GROUP BY lat_band
    ORDER BY MIN(latitude) NULLS LAST
""")
print("=== osm_import MX — latitude bands ===")
south_of_border = 0
border_zone = 0
clearly_us = 0
for r in c.fetchall():
    print(f"  {str(r[0]):35s}  {r[1]:>7,}  (avg lon: {r[2]})")
    band = r[0]
    if band in ('26-27 (Rio Grande)', '25-26 (N Mexico/S TX)', '< 25 (Mexico proper)'):
        south_of_border += r[1]
    elif band in ('31-32 (Border zone)', '30-31 (Border zone)', '29-30 (Border zone)', '28-29 (South TX)', '27-28 (South TX)'):
        border_zone += r[1]
    else:
        clearly_us += r[1]

print(f"\n  South of border (< 28°N, really MX): {south_of_border:,}")
print(f"  Border zone (28-32°N, could be either): {border_zone:,}")
print(f"  Clearly US (> 32°N or < -114°W): {clearly_us:,}")

# Now for the border zone (28-32°N) — check city names
c.execute("""
    SELECT 
        CASE 
            WHEN city IS NULL OR city = '' OR city = 'None' THEN 'NULL/empty'
            WHEN city IN ('Ciudad de México','Naucalpan de Juárez','Guadalajara',
                'Monterrey','Puebla','Tijuana','Mexicali','Ciudad Juárez',
                'León','Zapopan','Chihuahua','Hermosillo','Saltillo',
                'Culiacán','Torreón','Morelia','Reynosa','San Luis Potosí',
                'Mérida','Aguascalientes','Querétaro','Cancún','Durango',
                'Veracruz','Tuxtla Gutiérrez','Irapuato','Villahermosa',
                'Acapulco','Tampico','Celaya','Ensenada','Nogales',
                'Piedras Negras','Nuevo Laredo','Matamoros','Campeche',
                'Oaxaca','Cuernavaca','Toluca','Pachuca','Xalapa',
                'Zacatecas','Tlaxcala','La Paz','Navojoa','Guaymas',
                'Los Mochis','Mazatlán','Tepic','Uruapan','Zamora',
                'Guanajuato','San Miguel','Puerto Vallarta',
                'Naucalpan','Ecatepec','Chimalhuacán','Tlalnepantla',
                'Cárdenas','Comalcalco','Macuspana')
            THEN 'Mexican city'
            ELSE 'Non-MX city'
        END as city_type,
        COUNT(*) as cnt
    FROM churches 
    WHERE country='MX' AND source='osm_import'
    AND latitude BETWEEN 28 AND 32
    AND longitude BETWEEN -125 AND -65
    GROUP BY city_type
""")
print("\n=== Border zone (28-32°N) city analysis ===")
for r in c.fetchall():
    print(f"  {str(r[0]):20s}  {r[1]:>7,}")

# For border zone with Non-MX cities, sample them
c.execute("""
    SELECT city, COUNT(*) as cnt FROM churches 
    WHERE country='MX' AND source='osm_import'
    AND latitude BETWEEN 28 AND 32
    AND longitude BETWEEN -125 AND -65
    AND city NOT IN ('Ciudad de México','Naucalpan de Juárez','Guadalajara',
        'Monterrey','Puebla','Tijuana','Mexicali','Ciudad Juárez',
        'León','Zapopan','Chihuahua','Hermosillo','Saltillo',
        'Culiacán','Torreón','Morelia','Reynosa','San Luis Potosí',
        'Mérida','Aguascalientes','Querétaro','Cancún','Durango',
        'Veracruz','Tuxtla Gutiérrez','Irapuato','Villahermosa',
        'Acapulco','Tampico','Celaya','Ensenada','Nogales',
        'Piedras Negras','Nuevo Laredo','Matamoros','Campeche',
        'Oaxaca','Cuernavaca','Toluca','Pachuca','Xalapa',
        'Zacatecas','Tlaxcala','La Paz','Navojoa','Guaymas',
        'Los Mochis','Mazatlán','Tepic','Uruapan','Zamora',
        'Guanajuato','San Miguel','Puerto Vallarta',
        'Naucalpan','Ecatepec','Chimalhuacán','Tlalnepantla',
        'Cárdenas','Comalcalco','Macuspana')
    AND city IS NOT NULL AND city != '' AND city != 'None'
    GROUP BY city ORDER BY cnt DESC LIMIT 25
""")
print("\n=== Border zone — non-MX city names (top 25) ===")
for r in c.fetchall():
    print(f"  {str(r[0])[:30]:30s}  {r[1]:>6,}")

# SAFE estimate: osm_import MX records north of 32°N OR with known US city names
# North of 32°N = definitely US (border is 31.8°N max near El Paso)
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' AND source='osm_import'
    AND latitude >= 32
    AND longitude BETWEEN -125 AND -65
""")
north_of_32 = c.fetchone()[0]
print(f"\nosm_import MX north of 32°N (clearly US): {north_of_32:,}")

# PLUS: records in border zone (28-32°N) with known US city names
us_border_cities = ['Houston','San Antonio','Austin','Shreveport','Pensacola','Hattiesburg',
    'Georgetown','Longview','Waco','New Orleans','Baton Rouge','Abilene',
    'Mobile','Midland','Richmond','Dallas','Cleveland','Columbus',
    'Jacksonville','Portland','Philadelphia','Phoenix']
ph = ','.join('?' * len(us_border_cities))
c.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' AND source='osm_import'
    AND latitude BETWEEN 28 AND 32
    AND longitude BETWEEN -125 AND -65
    AND city IN ({ph})
""", us_border_cities)
border_us_cities = c.fetchone()[0]

# PLUS: records with US state code (already counted if they have lat>=28)
# But many have no city, so let's count conservatively
print(f"Border zone with US city names: {border_us_cities:,}")
print(f"TOTAL clearly US (north of 32 + border US cities): {north_of_32 + border_us_cities:,}")

# What about holy_sites_import?
c.execute("""
    SELECT 
        CASE 
            WHEN latitude >= 32 THEN 'Clearly US'
            WHEN latitude BETWEEN 28 AND 32 THEN 'Border zone'
            ELSE 'Mexico proper'
        END as zone,
        COUNT(*)
    FROM churches 
    WHERE country='MX' AND source='holy_sites_import'
    GROUP BY zone
""")
print("\n=== holy_sites_import MX by zone ===")
total_holy_clear = 0
for r in c.fetchall():
    print(f"  {str(r[0]):20s}  {r[1]:>8,}")
    if r[0] != 'Mexico proper':
        total_holy_clear += r[1]

# Check holy_sites_import border zone city names
c.execute("""
    SELECT city, COUNT(*) FROM churches 
    WHERE country='MX' AND source='holy_sites_import'
    AND latitude BETWEEN 28 AND 32
    AND city IS NOT NULL AND city != '' AND city != 'None'
    GROUP BY city ORDER BY COUNT(*) DESC LIMIT 10
""")
print("\n=== holy_sites_import border zone cities ===")
for r in c.fetchall():
    print(f"  {str(r[0]):30s}  {r[1]:>6,}")

db.close()
