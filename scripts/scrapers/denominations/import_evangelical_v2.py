"""Re-import Wikipedia evangelical auditoriums with proper column parsing + location fallback geocode."""
import json, re, sqlite3, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime
import pandas as pd

DB = "E:/grid/churches.db"
NOW = datetime.utcnow().isoformat()
t0 = time.time()

def fetch_wiki(url, retries=3):
    req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0 (charles@example.com)"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
            else: raise

def log(msg):
    print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)

# ── 1. Fetch & parse ──
log("Fetching List_of_the_largest_evangelical_church_auditoriums...")
params = urllib.parse.urlencode({
    "action": "parse", "page": "List_of_the_largest_evangelical_church_auditoriums",
    "prop": "text", "format": "json"
})
data = fetch_wiki(f"https://en.wikipedia.org/w/api.php?{params}")
html = data["parse"]["text"]["*"]

# Parse: 5-column table = Church | Ministry | Year | Capacity | Location
rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL)
churches = []
for row_html in rows:
    cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
    if len(cells) < 4: continue
    name = re.sub(r'<[^>]+>', '', cells[0]).strip()
    # Extract just the first church name before comma
    name_clean = name.split(",")[0].strip()
    if not name_clean or len(name_clean) < 3: continue
    # Skip "See also" rows at bottom
    if any(skip in name.lower() for skip in 
           ["tallest", "eastern orthodox", "hindu", "mosque", "churches\n"]):
        continue
    
    location = re.sub(r'<[^>]+>', '', cells[-1]).strip()
    # Clean citations like &#91;9&#93;
    location = re.sub(r'&#91;\d+&#93;', '', location)
    location = re.sub(r'\[\d+\]', '', location)
    
    ministries = re.sub(r'<[^>]+>', '', cells[1]).strip() if len(cells) > 1 else ""
    
    # Parse location into city/state/country
    parts = [p.strip() for p in location.split(",")]
    country_raw = parts[-1] if parts else ""
    state = parts[-2] if len(parts) >= 3 else ""
    city = parts[0] if parts else location
    
    # Country mapping
    country = "ZZ"
    cl = country_raw.lower()
    if "nigeria" in cl: country = "NG"
    elif "united states" in cl or "usa" in cl: country = "US"
    elif "brazil" in cl: country = "BR"
    elif "india" in cl: country = "IN"
    elif "indonesia" in cl: country = "ID"
    elif "zimbabwe" in cl: country = "ZW"
    elif "uganda" in cl: country = "UG"
    elif "ghana" in cl: country = "GH"
    elif "guatemala" in cl: country = "GT"
    elif "burkina faso" in cl: country = "BF"
    elif "kenya" in cl: country = "KE"
    elif "south korea" in cl or "korea" in cl: country = "KR"
    elif "philippines" in cl: country = "PH"
    elif "argentina" in cl: country = "AR"
    elif "paraguay" in cl: country = "PY"
    elif "united kingdom" in cl or "england" in cl: country = "UK"
    elif "australia" in cl: country = "AU"
    elif "canada" in cl: country = "CA"
    
    churches.append({
        "name": name_clean, "city": city, "state": state,
        "country": country, "country_raw": country_raw,
        "denomination": "Pentecostal", "family": "Protestant",
        "faith_tradition": "Christian", "ministries": ministries,
        "location": location,
    })

# Dedup
seen = set()
unique = []
for ch in churches:
    key = ch["name"].lower()
    if key not in seen:
        seen.add(key); unique.append(ch)

log(f"Found {len(unique)} unique churches")
for uc in unique:
    log(f"  {uc['name'][:50]:<50} | {uc['country']} | {uc['location'][:50]}")

# ── 2. Geocode ──
log("Geocoding via Wikipedia GeoData API...")
geocoded = 0
for i, ch in enumerate(unique):
    clean = ch["name"].replace("'S", "s")
    try:
        tp = urllib.parse.urlencode({
            "action": "query", "titles": clean, "prop": "coordinates", "format": "json"
        })
        cdata = fetch_wiki(f"https://en.wikipedia.org/w/api.php?{tp}")
        pages = cdata.get("query", {}).get("pages", {})
        found = False
        for pid, page in pages.items():
            if pid == "-1": continue
            if "coordinates" in page:
                coords = page["coordinates"][0]
                ch["lat"] = coords["lat"]; ch["lon"] = coords["lon"]
                ch["wiki_title"] = page.get("title", "")
                geocoded += 1; found = True; break
        if not found:
            sp = urllib.parse.urlencode({
                "action": "query", "list": "search", "srsearch": clean,
                "srlimit": 1, "format": "json"
            })
            sdata = fetch_wiki(f"https://en.wikipedia.org/w/api.php?{sp}")
            results = sdata.get("query", {}).get("search", [])
            if results:
                cp = urllib.parse.urlencode({
                    "action": "query", "pageids": results[0]["pageid"],
                    "prop": "coordinates", "format": "json"
                })
                cdata2 = fetch_wiki(f"https://en.wikipedia.org/w/api.php?{cp}")
                for pid, page in cdata2.get("query", {}).get("pages", {}).items():
                    if "coordinates" in page:
                        coords = page["coordinates"][0]
                        ch["lat"] = coords["lat"]; ch["lon"] = coords["lon"]
                        ch["wiki_title"] = page.get("title", "")
                        geocoded += 1; break
    except Exception:
        pass
    if (i + 1) % 5 == 0:
        log(f"  {geocoded}/{i+1}")
    time.sleep(0.3)

log(f"Wikipedia geocoded: {geocoded}/{len(unique)}")

# ── 3. Import ──
log("Importing...")
rows_data = []
for ch in unique:
    if "lat" not in ch: continue
    rows_data.append({
        "name": ch["name"], "city": ch["city"], "state": ch.get("state", ""),
        "country": ch["country"],
        "latitude": ch["lat"], "longitude": ch["lon"],
        "geocode_source": ch.get("geocode_source", "wikipedia_geodata"),
        "source": "wikipedia_evangelical",
        "denomination": "Pentecostal", "family": "Protestant",
        "faith_tradition": "Christian",
        "classification_source": "wikipedia_geodata",
    })

if not rows_data:
    log("Nothing to import."); import sys; sys.exit(0)

df = pd.DataFrame(rows_data)
db = sqlite3.connect(DB)
max_id = db.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]
df["id"] = range(max_id + 1, max_id + 1 + len(df))

df.to_sql("_wiki_evan_temp", db, if_exists="replace", index=False)
db.execute("CREATE INDEX IF NOT EXISTS idx_wet2_id ON _wiki_evan_temp(id)")
db.execute("""
    INSERT OR IGNORE INTO churches (id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source)
    SELECT id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source
    FROM _wiki_evan_temp
""")
inserted = db.execute("SELECT COUNT(*) FROM _wiki_evan_temp").fetchone()[0]
db.execute("DROP TABLE _wiki_evan_temp")

db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_inserted, fields_populated,
     records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
""", ("wikipedia_evangelical", "import_evangelical_v2.py", NOW, NOW, inserted,
      "name,city,country,latitude,longitude,denomination,description",
      len(unique), geocoded, f"Evangelical auditoriums v2: {inserted}/{len(unique)} imported."))
db.commit()

total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
db.close()

log(f"Inserted: {inserted:,}")
log(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%)")
log("Done")
