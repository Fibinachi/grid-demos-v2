"""Import Wikipedia lists: evangelical auditoriums, tallest, Orthodox largest, shrines."""
import json, re, sqlite3, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime
import pandas as pd

DB = "E:/grid/churches.db"
NOW = datetime.utcnow().isoformat()
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
t0 = time.time()

DENOM_MAP = {
    'catholic': 'Catholic', 'anglican': 'Anglican', 'orthodox': 'Orthodox',
    'protestant': 'Protestant', 'lutheran': 'Lutheran', 'methodist': 'Methodist',
    'baptist': 'Baptist', 'pentecostal': 'Pentecostal', 'presbyterian': 'Presbyterian',
    'evangelical': 'Protestant', 'calvinist': 'Presbyterian',
}

def fetch_wiki(url, retries=3):
    req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0 (charles@example.com)"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                print(f"  429 — waiting {2**(attempt+1)}s...", flush=True)
                time.sleep(2 ** (attempt + 1))
            else:
                raise

def classify_denom(raw):
    raw = (raw or "").lower().strip()
    raw = re.sub(r'\([^)]*\)', '', raw).strip()
    for key, label in DENOM_MAP.items():
        if key in raw: return label
    return "Other"

def log(msg):
    print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)

# Pages to scrape (page_name, source_tag, default_denom)
PAGES = [
    ("List_of_the_largest_evangelical_church_auditoriums", "wikipedia_evangelical", "Protestant"),
    ("List_of_tallest_church_buildings", "wikipedia_tallest", None),
    ("List_of_largest_Eastern_Orthodox_church_buildings", "wikipedia_orthodox_largest", "Orthodox"),
    ("List_of_Christian_pilgrimage_sites", "wikipedia_shrines", None),
]

all_churches = []

for page_name, source_tag, default_denom in PAGES:
    log(f"Fetching {page_name}...")
    params = urllib.parse.urlencode({
        "action": "parse", "page": page_name,
        "prop": "text", "format": "json"
    })
    data = fetch_wiki(f"https://en.wikipedia.org/w/api.php?{params}")
    html = data["parse"]["text"]["*"]
    
    rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL)
    churches = []
    for row_html in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
        if len(cells) < 2: continue
        name = re.sub(r'<[^>]+>', '', cells[0]).strip()
        if not name or len(name) < 3: continue
        # Extract denomination
        denom_raw = ""
        for cell in reversed(cells):
            text = re.sub(r'<[^>]+>', '', cell).strip()
            if any(k in text.lower() for k in DENOM_MAP):
                denom_raw = text; break
        denom = classify_denom(denom_raw) if denom_raw else (default_denom or "Other")
        # Extract city/country from 2nd-to-last / 3rd-to-last cells
        city = ""; country = ""
        if len(cells) >= 3:
            city = re.sub(r'<[^>]+>', '', cells[-2]).strip()
            country = re.sub(r'<[^>]+>', '', cells[-1]).strip()
        churches.append({"name": name, "denom": denom, "source": source_tag,
                        "city": city, "country": country})
    
    # Dedup
    seen = set()
    unique = []
    for ch in churches:
        key = ch["name"].lower()
        if key not in seen and "|" not in ch["name"]:
            seen.add(key); unique.append(ch)
    
    log(f"  {len(unique)} unique (from {len(churches)} rows)")
    all_churches.extend(unique)

# Dedup across all lists
seen = set()
final = []
for ch in all_churches:
    key = ch["name"].lower()
    if key not in seen:
        seen.add(key); final.append(ch)

log(f"Total unique across all lists: {len(final)}")

# Geocode
log("Geocoding via Wikipedia GeoData API...")
geocoded = 0
for i, ch in enumerate(final):
    clean = ch["name"].replace("'S", "s")
    try:
        # Exact title first
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
        
        if not found:  # Search fallback
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
    if (i + 1) % 10 == 0:
        log(f"  Geocoding: {geocoded}/{i+1}")
    time.sleep(0.3)

log(f"Geocoded: {geocoded}/{len(final)}")

# Import via load-memory-write-sql
log("Importing...")
rows_data = []
for ch in final:
    if "lat" not in ch: continue
    country = "EU"; state = ""
    c = (ch.get("country") or "").lower()
    city = ch.get("city", "")
    if "united states" in c or "usa" in c: country = "US"
    elif "united kingdom" in c or "england" in c: country = "UK"; state = "England"
    elif "canada" in c: country = "CA"
    elif "brazil" in c: country = "BR"
    elif "france" in c: country = "FR"
    elif "italy" in c: country = "IT"
    elif "germany" in c: country = "DE"
    elif "spain" in c: country = "ES"
    elif "poland" in c: country = "PL"
    elif "mexico" in c: country = "MX"
    elif "india" in c: country = "IN"
    elif "australia" in c: country = "AU"
    elif "russia" in c: country = "RU"
    elif "china" in c: country = "CN"
    elif "turkey" in c: country = "TR"
    elif "japan" in c: country = "JP"
    elif "philippines" in c: country = "PH"
    elif "nigeria" in c: country = "NG"
    elif "south africa" in c: country = "ZA"
    elif "south korea" in c or "korea" in c: country = "KR"
    
    denom = ch["denom"]
    if denom == "Catholic": family = "Catholic"; tradition = "Christian"
    elif denom == "Anglican": family = "Anglican"; tradition = "Christian"
    elif denom == "Orthodox": family = "Orthodox"; tradition = "Christian"
    elif denom in ("Lutheran","Methodist","Baptist","Presbyterian","Pentecostal","Protestant"):
        family = "Protestant"; tradition = "Christian"
    else: family = "Other"; tradition = "Christian"
    
    rows_data.append({
        "name": ch["name"], "city": city, "state": state, "country": country,
        "latitude": ch["lat"], "longitude": ch["lon"],
        "geocode_source": "wikipedia_geodata", "source": ch["source"],
        "denomination": denom, "family": family, "faith_tradition": tradition,
        "classification_source": "wikipedia_geodata",
    })

if not rows_data:
    log("No churches to import."); import sys; sys.exit(0)

df = pd.DataFrame(rows_data)
db = sqlite3.connect(DB)
max_id = db.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]
df["id"] = range(max_id + 1, max_id + 1 + len(df))

df.to_sql("_wiki_extra_temp", db, if_exists="replace", index=False)
db.execute("CREATE INDEX IF NOT EXISTS idx_wet_id ON _wiki_extra_temp(id)")
db.execute("""
    INSERT INTO churches (id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source)
    SELECT id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source
    FROM _wiki_extra_temp
""")
inserted = db.execute("SELECT COUNT(*) FROM _wiki_extra_temp").fetchone()[0]
db.execute("DROP TABLE _wiki_extra_temp")

db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_inserted, fields_populated,
     records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
""", ("wikipedia_extra_lists", "import_wiki_extra_lists.py", NOW, NOW, inserted,
      "name,latitude,longitude,denomination,family,faith_tradition",
      len(final), geocoded,
      f"Wikipedia extra lists: {inserted}/{len(final)} imported."))
db.commit()

total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
db.close()

log(f"Inserted: {inserted:,}")
log(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%)")
log("Done")
