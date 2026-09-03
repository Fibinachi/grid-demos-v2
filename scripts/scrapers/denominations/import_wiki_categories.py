"""Discover ALL Wikipedia church list pages via category search, then scrape + geocode + import."""
import csv, json, re, sqlite3, time, urllib.request, urllib.parse
from datetime import datetime

DB = "E:/grid/churches.db"
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
t0 = time.time()

DENOM_MAP = {
    'catholic': 'Catholic', 'anglican': 'Anglican', 'orthodox': 'Orthodox',
    'protestant': 'Protestant', 'lutheran': 'Lutheran', 'methodist': 'Methodist',
    'baptist': 'Baptist', 'pentecostal': 'Pentecostal', 'calvinist': 'Presbyterian',
    'presbyterian': 'Presbyterian', 'evangelical': 'Protestant',
    'church of sweden': 'Lutheran', 'church of denmark': 'Lutheran',
    'church of england': 'Anglican', 'episcopal': 'Anglican',
    'coptic': 'Orthodox', 'armenian': 'Orthodox', 'russian': 'Orthodox',
    'eastern orthodox': 'Orthodox', 'oriental orthodox': 'Orthodox',
    'non-denominational': 'Non-Denominational / Independent',
}
SHRINES = {"shrine", "basilica", "sanctuary", "grotto", "calvary", "lourdes", "fatima", "guadalupe"}

def log(msg):
    print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)

def wiki_api(params, retries=3):
    """Call Wikipedia API with retry on 429."""
    for attempt in range(retries):
        try:
            url = f"https://en.wikipedia.org/w/api.php?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except Exception as e:
            if "429" in str(e) or "Too Many" in str(e):
                wait = (attempt + 1) * 3
                time.sleep(wait)
            elif attempt < retries - 1:
                time.sleep(1)
            else:
                raise
    return None

def classify(raw):
    raw = (raw or "").lower().strip()
    raw = re.sub(r'\([^)]*\)', '', raw).strip()
    for key, label in DENOM_MAP.items():
        if key in raw: return label
    return "Other"

# ── 1. Discover Wikipedia church list pages via title search ──
log("Discovering Wikipedia church list pages via search...")
all_lists = set()

# Search for "List of" + church/cathedral/basilica etc.
searches = [
    "List of church", "List of cathedral", "List of basilica",
    "List of monastery", "List of chapel", "List of abbey",
    "List of largest church", "List of tallest church",
    "List of longest church", "List of oldest church",
]

for query in searches:
    data = wiki_api({"action": "query", "list": "search", "srsearch": f"\"{query}\"",
                     "srlimit": 50, "srwhat": "title", "format": "json"})
    if data:
        for page in data.get("query", {}).get("search", []):
            title = page["title"]
            if "list of" in title.lower() and "disambiguation" not in title.lower():
                # Filter out denomination member lists, keep building lists
                if "denomination" not in title.lower() and "members" not in title.lower():
                    all_lists.add(title)

log(f"Found {len(all_lists)} church list pages")
for t in sorted(all_lists):
    log(f"  {t}")

# ── 2. Scrape each list page for church names ──
log("\nScraping church names from lists...")
all_churches = {}  # name_lower -> {name, denom, source_url, shrine}

for page_title in all_lists:
    source_url = f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
    data = wiki_api({"action": "parse", "page": page_title, "prop": "text", "format": "json"})
    if not data: continue
    html = data.get("parse", {}).get("text", {}).get("*", "")
    
    # Extract table rows
    rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL)
    page_count = 0
    for row_html in rows:
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row_html, re.DOTALL)
        if len(cells) < 2: continue
        name = re.sub(r'<[^>]+>', '', cells[0]).strip()
        if not name or len(name) < 5: continue
        if name.lower() in ('church','building','name','cathedral','place','city','location'): continue
        if '!' in name or '|' in name: continue
        
        # Get all cell text for denomination detection
        all_text = " ".join(re.sub(r'<[^>]+>', '', c).strip() for c in cells).lower()
        denom = classify(all_text)
        
        # Check for shrine
        is_shrine = any(s in name.lower() or s in all_text for s in SHRINES)
        
        key = name.lower()
        if key not in all_churches:
            all_churches[key] = {
                "name": name, "denom": denom, 
                "shrine": is_shrine,
                "source_url": source_url,
                "source_page": page_title
            }
            page_count += 1
    
    if page_count > 0:
        log(f"  {page_title}: +{page_count}")

log(f"\nTotal unique churches: {len(all_churches)}")
for d in sorted(set(ch["denom"] for ch in all_churches.values())):
    n = sum(1 for ch in all_churches.values() if ch["denom"] == d)
    log(f"  {d}: {n}")
shrines = sum(1 for ch in all_churches.values() if ch["shrine"])
log(f"  Shrines: {shrines}")

# ── 3. Geocode via Wikipedia search ──
log("\nGeocoding...")
geocoded = 0
churches_list = list(all_churches.values())
for i, ch in enumerate(churches_list):
    if "lat" in ch: 
        geocoded += 1
        continue
    
    # Search for the article
    data = wiki_api({"action": "query", "list": "search", "srsearch": ch["name"], "srlimit": 1, "format": "json"})
    if not data: continue
    
    results = data.get("query", {}).get("search", [])
    if not results: continue
    
    pageid = results[0]["pageid"]
    cdata = wiki_api({"action": "query", "pageids": pageid, "prop": "coordinates", "format": "json"})
    if not cdata: continue
    
    for pid, page in cdata.get("query", {}).get("pages", {}).items():
        if "coordinates" in page:
            ch["lat"] = page["coordinates"][0]["lat"]
            ch["lon"] = page["coordinates"][0]["lon"]
            geocoded += 1
    
    time.sleep(1.5)
    if (i + 1) % 25 == 0:
        log(f"  {i+1}/{len(churches_list)} ({geocoded} geocoded)")

log(f"Geocoded: {geocoded}/{len(churches_list)}")

# ── 4. Import ──
log("Importing...")
db = sqlite3.connect(DB)
db.execute("PRAGMA synchronous=OFF")
max_id = db.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]

inserted = 0
for ch in churches_list:
    if "lat" not in ch: continue
    max_id += 1
    denom = ch["denom"]
    if denom in ("Catholic","Anglican","Orthodox"): family = denom
    elif denom in ("Lutheran","Methodist","Baptist","Presbyterian","Pentecostal","Protestant"): family = "Protestant"
    else: family = "Other"
    
    db.execute("""
        INSERT INTO churches (id, name, latitude, longitude, geocode_source, source,
            denomination, family, faith_tradition, classification_source, country, historical_status)
        VALUES (?,?,?,?,'wikipedia_geodata','wikipedia_lists',?,?,'Christian','wikipedia_geodata','EU',?)
    """, (max_id, ch["name"], ch["lat"], ch["lon"], denom, family,
          "Shrine" if ch["shrine"] else None))
    
    # Also store source link in church_sources
    db.execute("""
        INSERT OR IGNORE INTO church_sources (church_id, source_name, source_url, notes)
        VALUES (?, 'wikipedia_list', ?, ?)
    """, (max_id, ch["source_url"], f"From Wikipedia page: {ch['source_page']}"))
    
    inserted += 1

db.commit()

db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated,
     churches_inserted, fields_populated, records_attempted, records_matched, status, notes)
    VALUES (?,?,?,?,0,?,?,?,?,'completed',?)
""", ("wikipedia_categories", "import_wiki_categories.py", TODAY, TODAY,
      inserted, "name,latitude,longitude,denomination,family,historical_status",
      len(churches_list), geocoded,
      f"Discovered {len(all_lists)} Wikipedia church lists via categories. {inserted} churches imported."))

total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
db.commit()
db.close()

log(f"\nInserted: {inserted:,}")
log(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%)")
log(f"Done in {time.time()-t0:.1f}s")
