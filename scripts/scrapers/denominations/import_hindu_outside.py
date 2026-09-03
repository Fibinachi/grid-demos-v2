"""Import Wikipedia's List of Hindu temples outside India — parses LI elements + table rows."""
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
log("Fetching List_of_Hindu_temples_outside_India...")
params = urllib.parse.urlencode({
    "action": "parse", "page": "List_of_Hindu_temples_outside_India",
    "prop": "text", "format": "json"
})
data = fetch_wiki(f"https://en.wikipedia.org/w/api.php?{params}")
html = data["parse"]["text"]["*"]

# Parse table rows (19 rows — Cambodia section)
rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL)
# Parse list items (148 items — main data)
items = re.findall(r'<li[^>]*>(.*?)</li>', html)

temples = []

# 1a. From table rows (Name, City, Deity)
for row_html in rows:
    cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
    if len(cells) < 2: continue
    name = re.sub(r'<[^>]+>', '', cells[0]).strip()
    if not name or len(name) < 3: continue
    city = re.sub(r'<[^>]+>', '', cells[1]).strip() if len(cells) > 1 else ""
    temples.append({"name": name, "city": city, "country": "KH", "source_type": "table"})

# 1b. From LI items — parse "Temple Name, City, Country" patterns
for li_html in items:
    # Get link text first (more reliable)
    link_match = re.search(r'<a[^>]*>(.*?)</a>', li_html)
    if not link_match: continue
    name = link_match.group(1).strip()
    if not name or len(name) < 3: continue
    
    # Get full text after the link for location
    full_text = re.sub(r'<[^>]+>', '', li_html).strip()
    
    # Location: text after the name, often "in City" or ", City"
    # Pattern: "Temple Name – in City, Country" or "Temple Name, City"
    location = ""
    for sep in [" – in ", " - in ", " in ", " – ", " - ", ", "]:
        idx = full_text.find(sep, len(name))
        if idx > 0:
            location = full_text[idx + len(sep):].strip()
            break
    
    city = location
    country = "ZZ"
    
    # Country from location
    ll = location.lower()
    if "australia" in ll or "sydney" in ll or "melbourne" in ll or "perth" in ll: country = "AU"
    elif "united states" in ll or " usa " in ll or "california" in ll or "texas" in ll or "florida" in ll: country = "US"
    elif "united kingdom" in ll or "england" in ll or "london" in ll: country = "UK"
    elif "canada" in ll or "toronto" in ll: country = "CA"
    elif "singapore" in ll: country = "SG"
    elif "malaysia" in ll or "kuala lumpur" in ll: country = "MY"
    elif "indonesia" in ll or "jakarta" in ll or "bali" in ll: country = "ID"
    elif "south africa" in ll or "durban" in ll: country = "ZA"
    elif "fiji" in ll: country = "FJ"
    elif "mauritius" in ll: country = "MU"
    elif "trinidad" in ll: country = "TT"
    elif "guyana" in ll: country = "GY"
    elif "suriname" in ll: country = "SR"
    elif "sri lanka" in ll or "colombo" in ll: country = "LK"
    elif "nepal" in ll: country = "NP"
    elif "bangladesh" in ll: country = "BD"
    elif "pakistan" in ll: country = "PK"
    elif "germany" in ll: country = "DE"
    elif "france" in ll or "paris" in ll: country = "FR"
    elif "netherlands" in ll: country = "NL"
    elif "italy" in ll or "rome" in ll: country = "IT"
    
    temples.append({"name": name, "city": city, "country": country, "source_type": "li"})

# Dedup
seen = set()
unique = []
for t in temples:
    key = t["name"].lower()
    if key not in seen:
        seen.add(key); unique.append(t)

log(f"Found {len(unique)} unique temples ({sum(1 for t in temples if t['source_type']=='table')} from tables, {sum(1 for t in temples if t['source_type']=='li')} from lists)")
from collections import Counter
country_counts = Counter(t["country"] for t in unique)
for c, n in country_counts.most_common(10):
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

# ── 3. Import ──
log("Importing...")
rows_data = []
for t in unique:
    if "lat" not in t: continue
    rows_data.append({
        "name": t["name"], "city": t["city"], "state": "",
        "country": t["country"],
        "latitude": t["lat"], "longitude": t["lon"],
        "geocode_source": "wikipedia_geodata",
        "source": "wikipedia_hindu_outside",
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

df.to_sql("_wiki_hindu_out_temp", db, if_exists="replace", index=False)
db.execute("CREATE INDEX IF NOT EXISTS idx_who_id ON _wiki_hindu_out_temp(id)")
db.execute("""
    INSERT INTO churches (id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source)
    SELECT id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source
    FROM _wiki_hindu_out_temp
""")
inserted = db.execute("SELECT COUNT(*) FROM _wiki_hindu_out_temp").fetchone()[0]
db.execute("DROP TABLE _wiki_hindu_out_temp")

db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_inserted, fields_populated,
     records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
""", ("wikipedia_hindu_outside", "import_hindu_outside.py", NOW, NOW, inserted,
      "name,city,country,latitude,longitude,denomination,family",
      len(unique), geocoded,
      f"Hindu temples outside India: {inserted}/{len(unique)} imported."))
db.commit()

total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
db.close()

log(f"Inserted: {inserted:,}")
log(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%)")
log("Done")
