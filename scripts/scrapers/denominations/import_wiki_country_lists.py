"""Scrape Wikipedia country-specific church lists from Lists_of_church_buildings."""
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
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
            else: raise

def log(msg):
    print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)

COUNTRY_MAP = {
    "albania": "AL", "belize": "BZ", "cape verde": "CV", "estonia": "EE",
    "malta": "MT", "nigeria": "NG", "north macedonia": "MK", "pakistan": "PK",
    "palestine": "PS", "portugal": "PT", "sweden": "SE", "zimbabwe": "ZW",
    "indonesia": "ID", "scotland": "UK", "england": "UK",
}

# Get all country list pages
log("Fetching Lists_of_church_buildings...")
data = fetch_wiki("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
    "action": "parse", "page": "Lists_of_church_buildings", "prop": "text", "format": "json"
}))
html = data["parse"]["text"]["*"]
links = re.findall(r'href="/wiki/(List_of_churches_in_\w+)"', html)
links += re.findall(r'href="/wiki/(List_of_oldest_church_buildings)"', html)
links += re.findall(r'href="/wiki/(List_of_longest_church_buildings)"', html)
links += re.findall(r'href="/wiki/(List_of_church_buildings_in_\w+)"', html)
links = list(set(links))

log(f"Found {len(links)} pages to scrape")

all_churches = []

for page_slug in links:
    try:
        data = fetch_wiki("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "parse", "page": page_slug, "prop": "text", "format": "json"
        }))
        page_html = data["parse"]["text"]["*"]
        rows = re.findall(r'<tr>(.*?)</tr>', page_html, re.DOTALL)
        
        # Determine country from page name
        country = "ZZ"
        for cname, ccode in COUNTRY_MAP.items():
            if cname in page_slug.lower(): country = ccode; break
        
        page_churches = 0
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) < 2: continue
            name = re.sub(r'<[^>]+>', '', cells[0]).strip()
            if not name or len(name) < 3: continue
            
            # City from later columns
            texts = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            city = texts[1] if len(texts) > 1 and len(texts[1]) < 50 else ""
            
            page_churches += 1
            all_churches.append({
                "name": name, "city": city, "country": country,
                "source": "wikipedia_country_lists",
            })
        
        log(f"  {page_slug}: {page_churches}")
        time.sleep(0.3)
    except Exception as e:
        pass

log(f"Total: {len(all_churches)} churches")

# Dedup
seen = set()
unique = []
for ch in all_churches:
    key = ch["name"].lower()
    if key not in seen:
        seen.add(key); unique.append(ch)

log(f"Unique: {len(unique)}")

# Geocode
log("Geocoding...")
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
            for r in sdata.get("query", {}).get("search", []):
                cp = urllib.parse.urlencode({
                    "action": "query", "pageids": r["pageid"],
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

# Import
log("Importing...")
rows = []
for ch in unique:
    if "lat" not in ch: continue
    rows.append({
        "name": ch["name"], "city": ch["city"], "state": "", "country": ch["country"],
        "latitude": ch["lat"], "longitude": ch["lon"],
        "geocode_source": "wikipedia_geodata", "source": ch["source"],
        "denomination": "Christian", "family": "Christian", "faith_tradition": "Christian",
        "classification_source": "wikipedia_geodata",
    })

if not rows:
    log("Nothing to import."); import sys; sys.exit(0)

df = pd.DataFrame(rows)
db = sqlite3.connect(DB)
max_id = db.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]
df["id"] = range(max_id + 1, max_id + 1 + len(df))
df.to_sql("_wiki_country_temp", db, if_exists="replace", index=False)
db.execute("CREATE INDEX IF NOT EXISTS idx_wct_id ON _wiki_country_temp(id)")
db.execute("""
    INSERT INTO churches (id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source)
    SELECT id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source
    FROM _wiki_country_temp
""")
inserted = db.execute("SELECT COUNT(*) FROM _wiki_country_temp").fetchone()[0]
db.execute("DROP TABLE _wiki_country_temp")

db.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at, 
    churches_inserted, fields_populated, records_attempted, records_matched, status, notes)
    VALUES (?,?,?,?,?,?,?,?,'completed',?)
""", ("wikipedia_country_lists", "import_wiki_country_lists.py", NOW, NOW, inserted,
      "name,city,country,latitude,longitude", len(unique), geocoded,
      f"Country lists: {inserted}/{len(unique)} imported."))
db.commit()

total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
db.close()

log(f"Inserted: {inserted:,}")
log(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%)")
log("Done")
