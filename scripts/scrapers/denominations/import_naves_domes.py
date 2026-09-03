"""Import Wikipedia List_of_highest_church_naves + List_of_tallest_domes (filter churches only)."""
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

COUNTRY_MAP = {
    "germany": "DE", "france": "FR", "italy": "IT", "spain": "ES", "poland": "PL",
    "russia": "RU", "belgium": "BE", "czech": "CZ", "austria": "AT", "hungary": "HU",
    "united kingdom": "UK", "england": "UK", "netherlands": "NL", "switzerland": "CH",
    "denmark": "DK", "sweden": "SE", "norway": "NO", "portugal": "PT", "greece": "GR",
    "croatia": "HR", "serbia": "RS", "romania": "RO", "bulgaria": "BG", "ukraine": "UA",
    "united states": "US", "usa": "US", "canada": "CA", "mexico": "MX",
    "brazil": "BR", "argentina": "AR", "chile": "CL", "colombia": "CO", "peru": "PE",
    "philippines": "PH", "india": "IN", "australia": "AU",
    "ivory coast": "CI", "malaysia": "MY", "singapore": "SG", "vatican": "VA",
}
DENOM_MAP = {
    "catholic": "Catholic", "protestant": "Protestant", "lutheran": "Lutheran",
    "orthodox": "Orthodox", "anglican": "Anglican", "methodist": "Methodist",
    "baptist": "Baptist", "pentecostal": "Pentecostal", "presbyterian": "Presbyterian",
}

def classify_denom(raw):
    raw = (raw or "").lower()
    for k, v in DENOM_MAP.items():
        if k in raw: return v
    return "Other"

def map_country(raw):
    raw = (raw or "").lower()
    for k, v in COUNTRY_MAP.items():
        if k in raw: return v
    return "ZZ"

all_churches = []

# ── 1. Highest church naves ──
log("Fetching List_of_highest_church_naves...")
params = urllib.parse.urlencode({
    "action": "parse", "page": "List_of_highest_church_naves", "prop": "text", "format": "json"
})
data = fetch_wiki(f"https://en.wikipedia.org/w/api.php?{params}")
html = data["parse"]["text"]["*"]

# 8 cols: Rank | Name | Height | City | Country | Denomination | Notes | Extra
rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL)
for row in rows:
    cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
    if len(cells) < 4: continue
    name = re.sub(r'<[^>]+>', '', cells[1]).strip()
    if not name or len(name) < 3: continue
    city = re.sub(r'<[^>]+>', '', cells[3]).strip()
    country_raw = re.sub(r'<[^>]+>', '', cells[4]).strip()
    denom_raw = re.sub(r'<[^>]+>', '', cells[5]).strip()
    all_churches.append({
        "name": name, "city": city, "country": map_country(country_raw),
        "denom": classify_denom(denom_raw), "source": "wikipedia_highest_naves",
    })

log(f"  Naves: {len(all_churches)}")

# ── 2. Tallest domes (filter to churches/mosques/temples only) ──
log("Fetching List_of_tallest_domes...")
params2 = urllib.parse.urlencode({
    "action": "parse", "page": "List_of_tallest_domes", "prop": "text", "format": "json"
})
data2 = fetch_wiki(f"https://en.wikipedia.org/w/api.php?{params2}")
html2 = data2["parse"]["text"]["*"]

# Column structure varies: Name | ...measurements... | City | Country
# Look for city/country in last few cells
RELIGIOUS_KEYWORDS = ['church', 'cathedral', 'basilica', 'temple', 'mosque', 'masjid',
                       "st ", "st.", 'saint ', 'our lady', 'san ', 'santa ', 'saint-',
                       'minster', 'abbey', 'chapel', 'shrine', 'oratory', 'vedic',
                       'salvation', 'sultan', 'beth ', 'beth-']

rows2 = re.findall(r'<tr>(.*?)</tr>', html2, re.DOTALL)
dome_count = 0
for row in rows2:
    cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
    if len(cells) < 3: continue
    name = re.sub(r'<[^>]+>', '', cells[0]).strip()
    name_lower = name.lower()
    if not name or len(name) < 3: continue
    
    # Filter: only religious buildings
    if not any(kw in name_lower for kw in RELIGIOUS_KEYWORDS):
        continue
    
    # City and country are typically in last 2-3 columns
    # Parse all cells for city-like and country-like content
    texts = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
    # Skip pure measurement cells
    non_measure = [t for t in texts if not re.match(r'^[~]?\d+[\d.,\s]*m', t) and not re.match(r'^[\d.,]+\s*(ft|m)', t)]
    
    city = ""
    country_raw = ""
    # City/country typically at positions -2 and -1 (or -3 and -2)
    if len(texts) >= 2:
        last2 = texts[-2]
        last1 = texts[-1]
        # Check which is country
        if map_country(last1) != "ZZ":
            country_raw = last1
            city = last2 if map_country(last2) == "ZZ" else ""
        elif map_country(last2) != "ZZ":
            country_raw = last2
            city = texts[-3] if len(texts) >= 3 else ""
    
    if not city:
        # Try position-based
        if len(texts) >= 10:
            city = texts[9]
            country_raw = texts[10] if len(texts) > 10 else ""
    
    dome_count += 1
    all_churches.append({
        "name": name, "city": city, "country": map_country(country_raw),
        "denom": "Other", "source": "wikipedia_tallest_domes",
    })

log(f"  Domes (religious): {dome_count}")

# Dedup
seen = set()
unique = []
for ch in all_churches:
    key = ch["name"].lower()
    if key not in seen:
        seen.add(key); unique.append(ch)

log(f"Total unique: {len(unique)}")

# ── 3. Geocode via Wikipedia ──
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
                ch["lat"] = page["coordinates"][0]["lat"]
                ch["lon"] = page["coordinates"][0]["lon"]
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
                        ch["lat"] = page["coordinates"][0]["lat"]
                        ch["lon"] = page["coordinates"][0]["lon"]
                        geocoded += 1; break
    except Exception:
        pass
    if (i + 1) % 10 == 0:
        log(f"  {geocoded}/{i+1}")
    time.sleep(0.3)

log(f"Geocoded: {geocoded}/{len(unique)}")

# ── 4. Import ──
log("Importing...")
rows_data = []
for ch in unique:
    if "lat" not in ch: continue
    denom = ch["denom"]
    if denom == "Catholic": family = "Catholic"; trad = "Christian"
    elif denom == "Orthodox": family = "Orthodox"; trad = "Christian"
    elif denom == "Anglican": family = "Anglican"; trad = "Christian"
    elif denom in ("Lutheran","Methodist","Baptist","Presbyterian","Pentecostal","Protestant"):
        family = "Protestant"; trad = "Christian"
    elif denom == "Other" and "mosque" in ch["name"].lower(): family = "Islam"; trad = "Islam"
    else: family = "Other"; trad = "Christian"
    
    rows_data.append({
        "name": ch["name"], "city": ch["city"], "state": "",
        "country": ch["country"],
        "latitude": ch["lat"], "longitude": ch["lon"],
        "geocode_source": "wikipedia_geodata", "source": ch["source"],
        "denomination": denom, "family": family,
        "faith_tradition": trad, "classification_source": "wikipedia_geodata",
    })

if not rows_data:
    log("Nothing to import."); import sys; sys.exit(0)

df = pd.DataFrame(rows_data)
db = sqlite3.connect(DB)
max_id = db.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]
df["id"] = range(max_id + 1, max_id + 1 + len(df))

df.to_sql("_naves_domes_temp", db, if_exists="replace", index=False)
db.execute("CREATE INDEX IF NOT EXISTS idx_nd_id ON _naves_domes_temp(id)")
db.execute("""
    INSERT INTO churches (id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source)
    SELECT id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source
    FROM _naves_domes_temp
""")
inserted = db.execute("SELECT COUNT(*) FROM _naves_domes_temp").fetchone()[0]
db.execute("DROP TABLE _naves_domes_temp")

db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_inserted, fields_populated,
     records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
""", ("wikipedia_naves_domes", "import_naves_domes.py", NOW, NOW, inserted,
      "name,city,country,latitude,longitude,denomination",
      len(unique), geocoded, f"Naves+domes: {inserted}/{len(unique)} imported."))
db.commit()

total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
db.close()

log(f"Inserted: {inserted:,}")
log(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%)")
log("Done")
