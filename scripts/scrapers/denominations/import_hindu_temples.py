"""Import Wikipedia's List of largest Hindu temples with proper column parsing + geocode."""
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
log("Fetching List_of_largest_Hindu_temples...")
params = urllib.parse.urlencode({
    "action": "parse", "page": "List_of_largest_Hindu_temples",
    "prop": "text", "format": "json"
})
data = fetch_wiki(f"https://en.wikipedia.org/w/api.php?{params}")
html = data["parse"]["text"]["*"]

# Table: Name | (empty/alt) | Area | City | Country | Notes
rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL)
temples = []
for row_html in rows:
    cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
    if len(cells) < 4: continue
    
    name = re.sub(r'<[^>]+>', '', cells[0]).strip()
    if not name or len(name) < 3: continue
    
    # Skip "See also" footer rows
    if any(s in name.lower() for s in ['largest mosques', 'largest church', 'list of ']):
        if len(temples) > 10: continue
    
    # City is cells[3], Country is cells[4]
    city = re.sub(r'<[^>]+>', '', cells[3]).strip() if len(cells) > 3 else ""
    country_raw = re.sub(r'<[^>]+>', '', cells[4]).strip() if len(cells) > 4 else ""
    area = re.sub(r'<[^>]+>', '', cells[2]).strip() if len(cells) > 2 else ""
    
    # Clean citations
    city = re.sub(r'&#91;\d+&#93;', '', city).strip()
    country_raw = re.sub(r'&#91;\d+&#93;', '', country_raw).strip()
    
    # Country mapping
    country = "ZZ"
    cl = country_raw.lower()
    if "india" in cl: country = "IN"
    elif "united states" in cl or "usa" in cl: country = "US"
    elif "cambodia" in cl: country = "KH"
    elif "indonesia" in cl: country = "ID"
    elif "nepal" in cl: country = "NP"
    elif "united kingdom" in cl or "england" in cl: country = "UK"
    elif "canada" in cl: country = "CA"
    elif "australia" in cl: country = "AU"
    elif "singapore" in cl: country = "SG"
    elif "malaysia" in cl: country = "MY"
    elif "south africa" in cl: country = "ZA"
    elif "trinidad" in cl: country = "TT"
    elif "fiji" in cl: country = "FJ"
    elif "mauritius" in cl: country = "MU"
    elif "sri lanka" in cl: country = "LK"
    elif "bangladesh" in cl: country = "BD"
    elif "pakistan" in cl: country = "PK"
    
    temples.append({
        "name": name, "city": city, "country": country,
        "country_raw": country_raw, "area": area,
        "denomination": "Hindu", "family": "Hindu",
        "faith_tradition": "Hindu",
    })

# Dedup
seen = set()
unique = []
for t in temples:
    key = t["name"].lower()
    if key not in seen:
        seen.add(key); unique.append(t)

log(f"Found {len(unique)} unique temples")
# Country breakdown
from collections import Counter
country_counts = Counter(t["country"] for t in unique)
for c, n in country_counts.most_common():
    log(f"  {c}: {n}")

# ── 2. Geocode via Wikipedia ──
log("Geocoding via Wikipedia GeoData API...")
geocoded = 0
for i, t in enumerate(unique):
    clean = t["name"].replace("'S", "s")
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
                t["lat"] = coords["lat"]; t["lon"] = coords["lon"]
                t["wiki_title"] = page.get("title", "")
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
                        t["lat"] = coords["lat"]; t["lon"] = coords["lon"]
                        t["wiki_title"] = page.get("title", "")
                        geocoded += 1; break
    except Exception:
        pass
    if (i + 1) % 10 == 0:
        log(f"  {geocoded}/{i+1}")
    time.sleep(0.3)

log(f"Geocoded: {geocoded}/{len(unique)}")

# ── 3. Import via load-memory-write-sql ──
log("Importing...")
rows_data = []
for t in unique:
    if "lat" not in t: continue
    rows_data.append({
        "name": t["name"], "city": t["city"], "state": "",
        "country": t["country"],
        "latitude": t["lat"], "longitude": t["lon"],
        "geocode_source": "wikipedia_geodata",
        "source": "wikipedia_hindu_temples",
        "denomination": "Hindu", "family": "Hindu",
        "faith_tradition": "Hindu",
        "classification_source": "wikipedia_geodata",
    })

if not rows_data:
    log("Nothing to import."); import sys; sys.exit(0)

df = pd.DataFrame(rows_data)
db = sqlite3.connect(DB)
max_id = db.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]
df["id"] = range(max_id + 1, max_id + 1 + len(df))

df.to_sql("_wiki_hindu_temp", db, if_exists="replace", index=False)
db.execute("CREATE INDEX IF NOT EXISTS idx_wht_id ON _wiki_hindu_temp(id)")
db.execute("""
    INSERT INTO churches (id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source)
    SELECT id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source
    FROM _wiki_hindu_temp
""")
inserted = db.execute("SELECT COUNT(*) FROM _wiki_hindu_temp").fetchone()[0]
db.execute("DROP TABLE _wiki_hindu_temp")

db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_inserted, fields_populated,
     records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
""", ("wikipedia_hindu_temples", "import_hindu_temples.py", NOW, NOW, inserted,
      "name,city,country,latitude,longitude,denomination,family,faith_tradition",
      len(unique), geocoded,
      f"Hindu temples: {inserted}/{len(unique)} imported."))
db.commit()

# Add source URLs to church_sources
db.execute("""
    INSERT OR IGNORE INTO church_sources (church_id, source_url)
    SELECT c.id, 'https://en.wikipedia.org/wiki/List_of_largest_Hindu_temples'
    FROM churches c WHERE c.source = 'wikipedia_hindu_temples'
""")
db.commit()

total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
db.close()

log(f"Inserted: {inserted:,}")
log(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%)")
log("Done")
