"""Import Wikipedia's List of tallest crosses — coordinates are embedded in table cells!"""
import json, re, sqlite3, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime
import pandas as pd

DB = "E:/grid/churches.db"
NOW = datetime.utcnow().isoformat()
t0 = time.time()

def log(msg):
    print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)

# ── 1. Fetch & parse ──
log("Fetching List_of_tallest_crosses_in_the_world...")
params = urllib.parse.urlencode({
    "action": "parse", "page": "List_of_tallest_crosses_in_the_world",
    "prop": "text", "format": "json"
})
url = f"https://en.wikipedia.org/w/api.php?{params}"
req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0 (charles@example.com)"})
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read())

html = data["parse"]["text"]["*"]

# Table columns: Name | Country | City | Coordinates (lat lon) | Height | Year | (extra) | (extra)
rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL)
crosses = []
for row in rows:
    cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
    if len(cells) < 4: continue
    
    name = re.sub(r'<[^>]+>', '', cells[0]).strip()
    if not name or len(name) < 3: continue
    # Clean parenthetical from name
    name = re.split(r'\s*\(', name)[0].strip()
    
    country_raw = re.sub(r'<[^>]+>', '', cells[1]).strip()
    city = re.sub(r'<[^>]+>', '', cells[2]).strip()
    
    # Coordinates: "lat lon" or "lat, lon"
    coord_text = re.sub(r'<[^>]+>', '', cells[3]).strip()
    coords_match = re.match(r'(-?[\d.]+)\s+(-?[\d.]+)', coord_text)
    if not coords_match:
        coords_match = re.match(r'(-?[\d.]+)\s*,\s*(-?[\d.]+)', coord_text)
    
    if not coords_match:
        continue  # Skip if no coordinates
    
    lat, lon = float(coords_match.group(1)), float(coords_match.group(2))
    
    height = re.sub(r'<[^>]+>', '', cells[4]).strip() if len(cells) > 4 else ""
    year = re.sub(r'<[^>]+>', '', cells[5]).strip() if len(cells) > 5 else ""
    
    # Country mapping
    country = "ZZ"
    cl = country_raw.lower()
    if "spain" in cl: country = "ES"
    elif "philippines" in cl: country = "PH"
    elif "chile" in cl: country = "CL"
    elif "brazil" in cl: country = "BR"
    elif "italy" in cl: country = "IT"
    elif "lebanon" in cl: country = "LB"
    elif "mexico" in cl: country = "MX"
    elif "united states" in cl or "usa" in cl: country = "US"
    elif "poland" in cl: country = "PL"
    elif "france" in cl: country = "FR"
    elif "germany" in cl: country = "DE"
    elif "lithuania" in cl: country = "LT"
    elif "portugal" in cl: country = "PT"
    elif "croatia" in cl: country = "HR"
    elif "slovakia" in cl: country = "SK"
    elif "hungary" in cl: country = "HU"
    elif "canada" in cl: country = "CA"
    elif "australia" in cl: country = "AU"
    elif "venezuela" in cl: country = "VE"
    elif "colombia" in cl: country = "CO"
    elif "argentina" in cl: country = "AR"
    elif "peru" in cl: country = "PE"
    elif "ecuador" in cl: country = "EC"
    elif "india" in cl: country = "IN"
    elif "timor" in cl: country = "TL"
    elif "vietnam" in cl: country = "VN"
    elif "haiti" in cl: country = "HT"
    elif "pakistan" in cl: country = "PK"
    elif "slovenia" in cl: country = "SI"
    elif "austria" in cl: country = "AT"
    
    crosses.append({
        "name": name, "city": city, "country": country,
        "latitude": lat, "longitude": lon,
        "height": height, "year": year,
    })

# Dedup
seen = set()
unique = []
for c in crosses:
    key = c["name"].lower()
    if key not in seen:
        seen.add(key); unique.append(c)

log(f"Found {len(unique)} crosses with coordinates")

# ── 2. Import ──
log("Importing...")
rows_data = []
for c in unique:
    rows_data.append({
        "name": c["name"], "city": c["city"], "state": "",
        "country": c["country"],
        "latitude": c["latitude"], "longitude": c["longitude"],
        "geocode_source": "wikipedia_embedded",
        "source": "wikipedia_tallest_crosses",
        "denomination": "Christian", "family": "Christian",
        "faith_tradition": "Christian",
        "classification_source": "wikipedia_embedded",
    })

df = pd.DataFrame(rows_data)
db = sqlite3.connect(DB)
max_id = db.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]
df["id"] = range(max_id + 1, max_id + 1 + len(df))

df.to_sql("_crosses_temp", db, if_exists="replace", index=False)
db.execute("CREATE INDEX IF NOT EXISTS idx_cr_id ON _crosses_temp(id)")
db.execute("""
    INSERT INTO churches (id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source)
    SELECT id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source
    FROM _crosses_temp
""")
inserted = db.execute("SELECT COUNT(*) FROM _crosses_temp").fetchone()[0]
db.execute("DROP TABLE _crosses_temp")

db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_inserted, fields_populated,
     records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
""", ("wikipedia_tallest_crosses", "import_tallest_crosses.py", NOW, NOW, inserted,
      "name,city,country,latitude,longitude,denomination",
      len(unique), len(unique),
      f"Tallest crosses: {inserted} imported with embedded coords."))
db.commit()

total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
db.close()

log(f"Inserted: {inserted:,}")
log(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%)")
log("Done")
