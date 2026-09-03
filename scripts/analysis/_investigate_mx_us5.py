"""Confirm osm_import MX records with US cities have US coordinates"""
import sqlite3

db = sqlite3.connect(r"E:\grid\churches.db")
c = db.cursor()

# Check coords of osm_import MX records with known US city names
us_cities = [
    'Houston', 'San Antonio', 'Austin', 'Shreveport', 'Pensacola',
    'Hattiesburg', 'Georgetown', 'Longview', 'Waco', 'El Paso',
    'New Orleans', 'Tucson', 'Baton Rouge', 'Abilene', 'San Diego',
    'Mobile', 'Midland', 'Dallas', 'Phoenix', 'Los Angeles',
    'Chicago', 'Atlanta', 'Denver', 'Oklahoma City', 'Tulsa',
    'Little Rock', 'Memphis', 'Nashville', 'Charlotte', 'Jacksonville',
    'Orlando', 'Tampa', 'Miami', 'Albuquerque', 'Las Vegas',
    'Portland', 'Seattle', 'Kansas City', 'St Louis', 'Indianapolis',
    'Columbus', 'Cincinnati', 'Cleveland', 'Detroit', 'Minneapolis',
    'Milwaukee', 'Louisville', 'Richmond', 'Baltimore', 'Philadelphia'
]

ph = ','.join('?' * len(us_cities))

c.execute(f"""
    SELECT city, COUNT(*), 
           ROUND(AVG(latitude),2) as avg_lat, ROUND(AVG(longitude),2) as avg_lon,
           ROUND(MIN(latitude),2) as min_lat, ROUND(MAX(latitude),2) as max_lat
    FROM churches 
    WHERE country='MX' AND source='osm_import' 
    AND city IN ({ph})
    GROUP BY city ORDER BY COUNT(*) DESC
""", us_cities)

print("=== osm_import MX records with US city names — coordinates ===")
total = 0
for r in c.fetchall():
    if r[5] and r[5] > 25:  # max_lat > 25 means firmly in US/North America
        location = "US" if r[3] and r[3] < -80 else "Check"
    else:
        location = "MEXICO?"
    print(f"  {str(r[0])[:20]:20s}  cnt={r[1]:>5,}  lat={r[2]:>7.2f}  lon={r[3]:>8.2f}  range={r[4]:.1f}-{r[5]:.1f}  → {location}")
    total += r[1]

print(f"\n  Subtotal above: {total:,}")

# Now check ALL osm_import MX records that have latitude in US range
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' AND source='osm_import'
    AND latitude BETWEEN 25 AND 50
    AND longitude BETWEEN -125 AND -65
""")
osm_us_coords = c.fetchone()[0]
print(f"\nTotal osm_import MX with US coordinates: {osm_us_coords:,}")

# How many osm_import MX records have lat < 25 (really in Mexico)?
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' AND source='osm_import'
    AND (latitude < 25 OR latitude IS NULL)
""")
osm_mx_coords = c.fetchone()[0]
print(f"Total osm_import MX with MX/unknown coordinates: {osm_mx_coords:,}")

# Of those with US coordinates, how many have NULL/empty city vs. Mexican city?
c.execute("""
    SELECT 
        SUM(CASE WHEN city IS NULL OR city='' OR city='None' THEN 1 ELSE 0 END) as no_city,
        SUM(CASE WHEN city IN ('Ciudad de México','Naucalpan de Juárez','Guadalajara',
                    'Monterrey','Puebla','Tijuana','Mexicali','Ciudad Juárez',
                    'León','Zapopan','Nezahualcóyotl','Ecatepec','Chihuahua',
                    'Hermosillo','Saltillo','Culiacán','Torreón','Morelia',
                    'Reynosa','San Luis Potosí','Mérida','Aguascalientes',
                    'Querétaro','Cancún','Durango','Veracruz','Tuxtla Gutiérrez',
                    'Irapuato','Villahermosa','Acapulco','Tampico','Celaya',
                    'Ensenada','Los Cabos','Nogales','Piedras Negras','Nuevo Laredo',
                    'Matamoros','Reynosa','Campeche','Colima','Chetumal',
                    'Oaxaca','Cuernavaca','Toluca','Pachuca','Xalapa',
                    'Cuautla','Córdoba','Orizaba','Poza Rica','Coatzacoalcos',
                    'Minatitlán','Tapachula','San Cristóbal','Pátzcuaro',
                    'Zacatecas','Tlaxcala','La Paz','Navojoa','Guaymas',
                    'Obregón','Los Mochis','Mazatlán','Tepic','Manzanillo',
                    'Uruapan','Zamora','Salamanca','Guanajuato','San Miguel',
                    'Querétaro','Tehuacán','Jalapa','Puerto Vallarta',
                    'Naucalpan','Ecatepec','Nezahualcóyotl','Chimalhuacán',
                    'Iztapalapa','Tlalnepantla','Atizapán','San Nicolás',
                    'Guadalupe','Apodaca','Santa Catarina','Escobedo',
                    'Juárez','Cárdenas','Comalcalco','Macuspana',
                    'Tenosique','Teapa','Jalpa','Jalpan')
        THEN 1 ELSE 0 END) as mx_city
    FROM churches 
    WHERE country='MX' AND source='osm_import'
    AND latitude BETWEEN 25 AND 50
    AND longitude BETWEEN -125 AND -65
""")
r = c.fetchone()
print(f"osc_import MX with US coords & no city: {r[0]:,}")
print(f"osc_import MX with US coords & MX city name: {r[1]:,}")

# Also check: how many osm_import MX records have US coords AND a non-MX city?
# We'll check city names that don't match the known MX cities
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' AND source='osm_import'
    AND latitude BETWEEN 25 AND 50
    AND longitude BETWEEN -125 AND -65
    AND (city IS NULL OR city = '' OR city = 'None'
         OR city NOT IN ('Ciudad de México','Naucalpan de Juárez','Guadalajara',
                    'Monterrey','Puebla','Tijuana','Mexicali','Ciudad Juárez',
                    'León','Zapopan','Nezahualcóyotl','Ecatepec','Chihuahua',
                    'Hermosillo','Saltillo','Culiacán','Morelia',
                    'Reynosa','San Luis Potosí','Mérida','Aguascalientes',
                    'Querétaro','Cancún','Durango','Veracruz','Tuxtla Gutiérrez',
                    'Irapuato','Villahermosa','Acapulco','Tampico','Celaya',
                    'Ensenada','Nogales','Piedras Negras','Nuevo Laredo',
                    'Matamoros','Campeche','Colima','Chetumal',
                    'Oaxaca','Cuernavaca','Toluca','Pachuca','Xalapa',
                    'Cuautla','Córdoba','Orizaba','Poza Rica','Coatzacoalcos',
                    'Tapachula','Zacatecas','Tlaxcala','La Paz','Navojoa',
                    'Guaymas','Los Mochis','Mazatlán','Tepic','Manzanillo',
                    'Uruapan','Zamora','Salamanca','Guanajuato','San Miguel',
                    'Tehuacán','Puerto Vallarta',
                    'Naucalpan','Ecatepec','Chimalhuacán',
                    'Tlalnepantla','San Nicolás',
                    'Guadalupe','Apodaca','Santa Catarina','Escobedo',
                    'Cárdenas','Comalcalco','Macuspana',
                    'Tenosique','Teapa','Jalpan'))
""")
r = c.fetchone()
print(f"osmc_import MX with US coords & non-MX city: {r[0]:,}")

db.close()
