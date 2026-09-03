"""Scrape additional Wikipedia church lists: evangelical auditoriums, tallest churches, largest orthodox."""
import csv, json, sqlite3, re, time, urllib.request, urllib.parse
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
    'church of norway': 'Lutheran', 'church of ireland': 'Anglican',
    'church of england': 'Anglican', 'episcopal': 'Anglican',
    'coptic': 'Orthodox', 'armenian': 'Orthodox', 'georgian': 'Orthodox',
    'serbian': 'Orthodox', 'russian': 'Orthodox', 'greek': 'Orthodox',
    'eastern orthodox': 'Orthodox', 'oriental orthodox': 'Orthodox',
    'bulgarian': 'Orthodox', 'romanian': 'Orthodox',
    'non-denominational': 'Non-Denominational / Independent',
    'nondenominational': 'Non-Denominational / Independent',
}

def classify(raw):
    raw = (raw or "").lower().strip()
    raw = re.sub(r'\([^)]*\)', '', raw).strip()
    for key, label in DENOM_MAP.items():
        if key in raw: return label
    return "Other"

def log(msg):
    print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)

def geocode_wiki(name):
    sp = urllib.parse.urlencode({"action":"query","list":"search","srsearch":name,"srlimit":1,"format":"json"})
    try:
        req = urllib.request.Request(f"https://en.wikipedia.org/w/api.php?{sp}",
            headers={"User-Agent":"GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            sdata = json.loads(r.read())
        results = sdata.get("query",{}).get("search",[])
        if results:
            pageid = results[0]["pageid"]
            cp = urllib.parse.urlencode({"action":"query","pageids":pageid,"prop":"coordinates","format":"json"})
            req2 = urllib.request.Request(f"https://en.wikipedia.org/w/api.php?{cp}",
                headers={"User-Agent":"GrantWizard/1.0"})
            with urllib.request.urlopen(req2, timeout=10) as r2:
                cdata = json.loads(r2.read())
            for pid, page in cdata.get("query",{}).get("pages",{}).items():
                if "coordinates" in page:
                    return (page["coordinates"][0]["lat"], page["coordinates"][0]["lon"], page.get("title",""))
    except: pass
    return None

# Wiki pages to scrape
PAGES = [
    "List_of_the_largest_evangelical_church_auditoriums",
    "List_of_tallest_church_buildings",
    "List_of_largest_Eastern_Orthodox_church_buildings",
    "List_of_Christian_pilgrimage_sites",  # Includes major shrines
]

SHRINES = {"shrine", "basilica", "sanctuary", "grotto", "calvary", "lourdes", "fatima", "guadalupe"}

all_churches = []
for page_name in PAGES:
    log(f"Fetching {page_name}...")
    params = urllib.parse.urlencode({"action":"parse","page":page_name,"prop":"text","section":"0","format":"json"})
    url = f"https://en.wikipedia.org/w/api.php?{params}"
    req = urllib.request.Request(url, headers={"User-Agent":"GrantWizard/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    html = data["parse"]["text"]["*"]
    
    # Extract table rows
    rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL)
    page_churches = []
    for row_html in rows:
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row_html, re.DOTALL)
        if len(cells) < 2: continue
        name = re.sub(r'<[^>]+>', '', cells[0]).strip()
        if not name or len(name) < 3 or '!' in name or '|' in name: continue
        if name.lower() in ('church','building','name','cathedral'): continue
        
        denom_raw = ""
        for cell in reversed(cells):
            text = re.sub(r'<[^>]+>', '', cell).strip()
            if any(k in text.lower() for k in DENOM_MAP): denom_raw = text; break
        if not denom_raw and len(cells) > 2:
            denom_raw = re.sub(r'<[^>]+>', '', cells[-1]).strip()
        
        denom = classify(denom_raw)
        # Detect shrines
        is_shrine = any(s in name.lower() or s in denom_raw.lower() for s in SHRINES)
        if is_shrine:
            denom = f"{denom} Shrine" if denom != "Other" else "Shrine"
        page_churches.append({"name": name, "denom": denom, "source": page_name, "shrine": is_shrine})
    
    # Dedup
    seen_names = set(ch["name"].lower() for ch in all_churches)
    for ch in page_churches:
        if ch["name"].lower() not in seen_names:
            seen_names.add(ch["name"].lower())
            all_churches.append(ch)
    log(f"  Added {len(page_churches)} ({len(all_churches)} total unique)")

log(f"\nTotal unique churches across all lists: {len(all_churches)}")
for d in sorted(set(ch["denom"] for ch in all_churches)):
    n = sum(1 for ch in all_churches if ch["denom"] == d)
    log(f"  {d}: {n}")

# Geocode
log("\nGeocoding...")
geocoded = 0
for ch in all_churches:
    if "lat" not in ch:
        result = geocode_wiki(ch["name"])
        if result:
            ch["lat"], ch["lon"], ch["wiki_title"] = result
            geocoded += 1
    else:
        geocoded += 1
    time.sleep(1.5)

log(f"Geocoded: {geocoded}/{len(all_churches)}")

# Import
log("Importing...")
db = sqlite3.connect(DB)
db.execute("PRAGMA synchronous=OFF")
max_id = db.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]

inserted = 0
for ch in all_churches:
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
          "Shrine" if ch.get("shrine") else None))
    inserted += 1

db.commit()

db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated,
     churches_inserted, fields_populated, records_attempted, records_matched, status, notes)
    VALUES (?,?,?,?,0,?,?,?,?,'completed',?)
""", ("wikipedia_lists", "import_wiki_lists.py", TODAY, TODAY, inserted,
      "name,latitude,longitude,denomination,family", len(all_churches), geocoded,
      f"Wikipedia lists: evangelical auditoriums, tallest, largest Orthodox. {inserted} imported."))

total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
db.commit()
db.close()

log(f"\nInserted: {inserted:,}")
log(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%)")
log(f"Done in {time.time()-t0:.1f}s")
