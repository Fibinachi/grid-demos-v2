"""Scrape Wikipedia's 'List of largest church buildings', geocode via GeoData, import with denomination tags."""
import csv, json, sqlite3, re, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime

DB = "E:/grid/churches.db"
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
NOW = datetime.utcnow().isoformat()
t0 = time.time()

def fetch_wiki(url, retries=3):
    """Fetch Wikipedia URL with exponential backoff on 429."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "GrantWizard/1.0 (charles@example.com)"
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = 2 ** (attempt + 1)  # 2, 4, 8
                print(f"  429 — waiting {wait}s...", flush=True)
                time.sleep(wait)
            else:
                raise

DENOM_MAP = {
    'catholic': 'Catholic',
    'anglican': 'Anglican',
    'orthodox': 'Orthodox',
    'protestant': 'Protestant',
    'lutheran': 'Lutheran',
    'methodist': 'Methodist',
    'baptist': 'Baptist',
    'pentecostal': 'Pentecostal',
    'calvinist': 'Presbyterian',
    'presbyterian': 'Presbyterian',
    'church of sweden': 'Lutheran',
    'church of denmark': 'Lutheran',
    'church of norway': 'Lutheran',
    'church of ireland': 'Anglican',
    'church in wales': 'Anglican',
    'church of south india': 'Protestant',
    'church of england': 'Anglican',
    'episcopal': 'Anglican',
    'syro-malabar': 'Catholic',
    'coptic': 'Orthodox',
    'armenian': 'Orthodox',
    'georgian': 'Orthodox',
    'serbian': 'Orthodox',
    'russian': 'Orthodox',
    'greek': 'Orthodox',
    'eastern orthodox': 'Orthodox',
    'oriental orthodox': 'Orthodox',
    'bulgarian': 'Orthodox',
    'romanian': 'Orthodox',
}

def classify_denom(raw):
    """Map Wikipedia denomination text to our classification."""
    raw = (raw or "").lower().strip()
    # Remove parentheticals
    raw = re.sub(r'\([^)]*\)', '', raw).strip()
    for key, label in DENOM_MAP.items():
        if key in raw:
            return label
    return "Other"

def log(msg):
    print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)

# ── 1. Scrape Wikipedia table ──
log("Fetching Wikipedia page...")
# Use the raw wiki markup for the table
params = urllib.parse.urlencode({
    "action": "parse", "page": "List_of_largest_church_buildings",
    "prop": "text", "section": "2",  # The "List" section
    "format": "json"
})
url = f"https://en.wikipedia.org/w/api.php?{params}"
data = fetch_wiki(url)

html = data["parse"]["text"]["*"]

# Parse table rows — extract church names and denominations
# Wikipedia table rows look like: <tr><td>Church Name</td><td>area</td>...<td>City</td><td>Country</td><td>Denomination</td></tr>
rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL)
churches = []
for row_html in rows:
    cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
    if len(cells) < 6:
        continue
    name = re.sub(r'<[^>]+>', '', cells[0]).strip()
    if not name or name in ('Church', 'Building') or len(name) < 3:
        continue
    # Extract denomination from last relevant cell
    denom_raw = ""
    for cell in reversed(cells):
        text = re.sub(r'<[^>]+>', '', cell).strip()
        if any(k in text.lower() for k in DENOM_MAP):
            denom_raw = text
            break
    if not denom_raw and len(cells) >= 8:
        denom_raw = re.sub(r'<[^>]+>', '', cells[-1] if len(cells) > 6 else cells[5]).strip()
    
    # Extract city and country from cells
    city_raw = re.sub(r'<[^>]+>', '', cells[-4]).strip() if len(cells) >= 7 else ""
    country_raw = re.sub(r'<[^>]+>', '', cells[-3]).strip() if len(cells) >= 7 else ""
    
    denom = classify_denom(denom_raw)
    churches.append({"name": name, "denom": denom, "denom_raw": denom_raw,
                     "city": city_raw, "country": country_raw})

# Dedup by name
seen = set()
unique = []
for ch in churches:
    key = ch["name"].lower()
    if key not in seen and "|" not in ch["name"]:
        seen.add(key)
        unique.append(ch)

log(f"Found {len(unique):,} unique churches")
for d in sorted(set(ch["denom"] for ch in unique)):
    n = sum(1 for ch in unique if ch["denom"] == d)
    log(f"  {d}: {n}")

# ── 2. Geocode via Wikipedia ──
log("Geocoding via Wikipedia GeoData API...")
geocoded = 0
for i, ch in enumerate(unique):
    clean = ch["name"].replace("'S", "s").replace("'S", "s")
    try:
        # First try exact title match (less rate-limited)
        tp = urllib.parse.urlencode({
            "action": "query", "titles": clean,
            "prop": "coordinates", "format": "json"
        })
        cdata = fetch_wiki(f"https://en.wikipedia.org/w/api.php?{tp}")
        pages = cdata.get("query", {}).get("pages", {})
        found = False
        for pid, page in pages.items():
            if pid == "-1": continue
            if "coordinates" in page:
                coords = page["coordinates"][0]
                ch["lat"] = coords["lat"]
                ch["lon"] = coords["lon"]
                ch["wiki_title"] = page.get("title", "")
                geocoded += 1
                found = True
                break

        # Fallback: search if exact title not found
        if not found:
            sp = urllib.parse.urlencode({
                "action": "query", "list": "search", "srsearch": clean,
                "srlimit": 1, "format": "json"
            })
            sdata = fetch_wiki(f"https://en.wikipedia.org/w/api.php?{sp}")
            results = sdata.get("query", {}).get("search", [])
            if results:
                pageid = results[0]["pageid"]
                cp = urllib.parse.urlencode({
                    "action": "query", "pageids": pageid,
                    "prop": "coordinates", "format": "json"
                })
                cdata2 = fetch_wiki(f"https://en.wikipedia.org/w/api.php?{cp}")
                pages2 = cdata2.get("query", {}).get("pages", {})
                for pid, page in pages2.items():
                    if "coordinates" in page:
                        coords = page["coordinates"][0]
                        ch["lat"] = coords["lat"]
                        ch["lon"] = coords["lon"]
                        ch["wiki_title"] = page.get("title", "")
                        geocoded += 1
                        break
    except Exception:
        pass
    if (i + 1) % 10 == 0:
        log(f"  Geocoding: {geocoded}/{i+1}")
    time.sleep(0.3)  # Gentle on the API

log(f"Geocoded: {geocoded}/{len(unique)}")

# ── 3. Import into DB (load-memory-write-sql pattern) ──
log("Importing into DB...")
import pandas as pd

rows = []
for ch in unique:
    if "lat" not in ch:
        continue
    country = "EU"
    state = ""
    city = ch.get("city", "")
    if ch.get("country"):
        c = ch["country"].lower()
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

    denom = ch["denom"]
    if denom == "Catholic": family = "Catholic"; tradition = "Christian"
    elif denom == "Anglican": family = "Anglican"; tradition = "Christian"
    elif denom == "Orthodox": family = "Orthodox"; tradition = "Christian"
    elif denom in ("Lutheran", "Methodist", "Baptist", "Presbyterian", "Pentecostal", "Protestant"):
        family = "Protestant"; tradition = "Christian"
    else: family = "Other"; tradition = "Christian"

    rows.append({
        "name": ch["name"], "city": city, "state": state, "country": country,
        "latitude": ch["lat"], "longitude": ch["lon"],
        "geocode_source": "wikipedia_geodata", "source": "wikipedia_largest",
        "denomination": denom, "family": family, "faith_tradition": tradition,
        "classification_source": "wikipedia_geodata",
    })

if not rows:
    log("No geocoded churches to import.")
    import sys; sys.exit(0)

df = pd.DataFrame(rows)

db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
max_id = db.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]
df["id"] = range(max_id + 1, max_id + 1 + len(df))

# Write to temp table
df.to_sql("_wiki_largest_temp", db, if_exists="replace", index=False)
db.execute("CREATE INDEX IF NOT EXISTS idx_wlt_id ON _wiki_largest_temp(id)")

# Copy into churches
db.execute("""
    INSERT INTO churches (id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source)
    SELECT id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source
    FROM _wiki_largest_temp
""")
inserted = db.execute("SELECT COUNT(*) FROM _wiki_largest_temp").fetchone()[0]
db.execute("DROP TABLE _wiki_largest_temp")

# Provenance
now_iso = datetime.utcnow().isoformat()
db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated,
     churches_inserted, fields_populated, records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, 'completed', ?)
""", ("wikipedia_largest", "import_largest_churches.py", now_iso, now_iso,
      inserted,
      "name,city,country,latitude,longitude,denomination,family,faith_tradition",
      len(unique), geocoded,
      f"Wikipedia 'List of largest church buildings': {inserted}/{len(unique)} imported with geocodes."))
db.commit()

total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
db.close()

log(f"Inserted: {inserted:,}")
log(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%)")
log(f"Done")
