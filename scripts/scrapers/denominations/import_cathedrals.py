"""Scrape ALL Wikipedia cathedral lists with diocese info — 126 country pages."""
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

COUNTRY_FROM_TITLE = {
    "algeria": "DZ", "angola": "AO", "benin": "BJ", "botswana": "BW",
    "burkina faso": "BF", "burundi": "BI", "cameroon": "CM", "cape verde": "CV",
    "central african": "CF", "chad": "TD", "democratic republic of the congo": "CD",
    "republic of the congo": "CG", "egypt": "EG", "ghana": "GH", "ivory coast": "CI",
    "liberia": "LR", "madagascar": "MG", "malawi": "MW", "morocco": "MA",
    "mozambique": "MZ", "nigeria": "NG", "rwanda": "RW", "senegal": "SN",
    "south africa": "ZA", "tanzania": "TZ", "tunisia": "TN", "uganda": "UG",
    "zambia": "ZM", "zimbabwe": "ZW", "kenya": "KE", "ethiopia": "ET",
    "france": "FR", "germany": "DE", "italy": "IT", "spain": "ES", "poland": "PL",
    "united kingdom": "UK", "england": "UK", "ireland": "IE", "belgium": "BE",
    "netherlands": "NL", "austria": "AT", "switzerland": "CH", "portugal": "PT",
    "croatia": "HR", "czech": "CZ", "hungary": "HU", "romania": "RO", "russia": "RU",
    "greece": "GR", "sweden": "SE", "denmark": "DK", "norway": "NO", "finland": "FI",
    "united states": "US", "usa": "US", "canada": "CA", "mexico": "MX",
    "brazil": "BR", "argentina": "AR", "chile": "CL", "colombia": "CO", "peru": "PE",
    "philippines": "PH", "india": "IN", "australia": "AU", "new zealand": "NZ",
    "indonesia": "ID", "pakistan": "PK", "bangladesh": "BD", "sri lanka": "LK",
    "japan": "JP", "south korea": "KR", "china": "CN", "vietnam": "VN",
    "thailand": "TH", "myanmar": "MM", "malaysia": "MY", "singapore": "SG",
}

DENOM_MAP = {
    "catholic": "Catholic", "roman catholic": "Catholic", "latin": "Catholic",
    "maronite": "Catholic", "syro-malabar": "Catholic", "syro-malankara": "Catholic",
    "chaldean": "Catholic", "armenian catholic": "Catholic", "greek catholic": "Catholic",
    "orthodox": "Orthodox", "eastern orthodox": "Orthodox", "oriental orthodox": "Orthodox",
    "russian orthodox": "Orthodox", "greek orthodox": "Orthodox", "coptic": "Orthodox",
    "anglican": "Anglican", "church of england": "Anglican", "episcopal": "Anglican",
    "lutheran": "Lutheran", "methodist": "Methodist", "baptist": "Baptist",
    "presbyterian": "Presbyterian", "pentecostal": "Pentecostal",
}

# ── 1. Get all cathedral list pages ──
log("Fetching Lists_of_cathedrals...")
data = fetch_wiki("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
    "action": "parse", "page": "Lists_of_cathedrals", "prop": "text", "format": "json"
}))
html = data["parse"]["text"]["*"]

# Find all cathedral list links
links = re.findall(r'href="/wiki/([^"]+)"', html)
cathedral_pages = []
for slug in links:
    if 'list_of_cathedrals' in slug.lower():
        # Convert slug to readable title
        title = slug.replace("_", " ")
        if slug not in [c[0] for c in cathedral_pages]:
            cathedral_pages.append((slug, title))

log(f"Found {len(cathedral_pages)} cathedral list pages")

# ── 2. Process each page ──
all_cathedrals = []

for page_idx, (page_slug, page_title) in enumerate(cathedral_pages):
    # Determine country from page title
    page_title_lower = page_title.lower()
    country = "ZZ"
    for cname, ccode in COUNTRY_FROM_TITLE.items():
        if cname in page_title_lower:
            country = ccode; break
    
    try:
        data = fetch_wiki("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "parse", "page": page_slug, "prop": "text", "format": "json"
        }))
        page_html = data["parse"]["text"]["*"]
        rows = re.findall(r'<tr>(.*?)</tr>', page_html, re.DOTALL)
        
        page_cathedrals = 0
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) < 2: continue
            
            # Get all cell text
            texts = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            
            # Try to identify columns: name, city, diocese, denomination
            name = ""
            city = ""
            diocese = ""
            denom = ""
            
            # Strategy: find the cell most likely to be the name (has links, first meaningful cell)
            # For most cathedral lists: col[0]=name, then city/diocese in different orders
            if len(texts) >= 2:
                name = texts[0]
                if len(name) < 3 or name.startswith("[") or name.startswith("Cathedral"):
                    continue  # Skip header/empty rows
                
                # Find city — typically a short proper noun, often in col[2] or col[3]
                for i in range(1, min(len(texts), 5)):
                    t = texts[i]
                    # Clean: remove references like [1], citations
                    t = re.sub(r'\[.*?\]', '', t).strip()
                    if t and len(t) > 1 and not t.startswith("http"):
                        if not city and not any(k in t.lower() for k in ['catholic','orthodox','anglican','lutheran','methodist','baptist','presbyterian','pentecostal','church of','cathedral','diocese','archdiocese','former','ruins']):
                            city = t
                
                # Find diocese — typically contains "Diocese" or "Archdiocese"
                for t in texts:
                    if 'diocese' in t.lower() or 'archdiocese' in t.lower() or 'eparchy' in t.lower():
                        diocese = re.sub(r'\[.*?\]', '', t).strip()
                        break
                
                # Find denomination
                for t in texts:
                    tl = t.lower()
                    if any(k in tl for k in DENOM_MAP):
                        denom_raw = t
                        for k, v in DENOM_MAP.items():
                            if k in tl:
                                denom = v; break
                        break
                
                # If no explicit diocese but 2nd meaningful cell is a location, use as diocese hint
                if not diocese and len(texts) >= 3:
                    # Some lists have: name | diocese_city | city | notes
                    # The 2nd cell is often the diocese seat
                    maybe_diocese = re.sub(r'\[.*?\]', '', texts[1]).strip()
                    if maybe_diocese and len(maybe_diocese) > 2 and maybe_diocese != city:
                        if not any(k in maybe_diocese.lower() for k in DENOM_MAP):
                            diocese = maybe_diocese
            
            if not name or len(name) < 3:
                continue
            
            page_cathedrals += 1
            all_cathedrals.append({
                "name": name, "city": city, "country": country,
                "diocese": diocese, "denom": denom or "Catholic",  # Default Catholic for cathedrals
                "page": page_title,
            })
        
        if page_cathedrals > 0:
            log(f"  {page_title}: {page_cathedrals} cathedrals")
    
    except Exception as e:
        pass  # Skip failed pages
    
    time.sleep(0.3)

log(f"Total cathedrals: {len(all_cathedrals)}")

# Dedup by name+city
seen = set()
unique = []
for c in all_cathedrals:
    key = (c["name"].lower(), c["city"].lower())
    if key not in seen:
        seen.add(key); unique.append(c)

log(f"Unique: {len(unique)}")

# ── 3. Geocode ──
log("Geocoding...")
geocoded = 0
for i, c in enumerate(unique):
    clean = c["name"].replace("'S", "s")
    # Add city for disambiguation
    if c["city"]:
        clean += " " + c["city"]
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
                c["lat"] = page["coordinates"][0]["lat"]
                c["lon"] = page["coordinates"][0]["lon"]
                geocoded += 1; found = True; break
        if not found:
            sp = urllib.parse.urlencode({
                "action": "query", "list": "search", "srsearch": c["name"],
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
                        c["lat"] = page["coordinates"][0]["lat"]
                        c["lon"] = page["coordinates"][0]["lon"]
                        geocoded += 1; break
    except Exception:
        pass
    if (i + 1) % 50 == 0:
        log(f"  {geocoded}/{i+1}")
    time.sleep(0.3)

log(f"Geocoded: {geocoded}/{len(unique)}")

# ── 4. Import ──
log("Importing...")
rows_data = []
for c in unique:
    if "lat" not in c: continue
    denom = c["denom"]
    if denom == "Catholic": family = "Catholic"; trad = "Christian"
    elif denom == "Orthodox": family = "Orthodox"; trad = "Christian"
    elif denom == "Anglican": family = "Anglican"; trad = "Christian"
    elif denom in ("Lutheran","Methodist","Baptist","Presbyterian","Pentecostal"):
        family = "Protestant"; trad = "Christian"
    else: family = "Other"; trad = "Christian"
    
    rows_data.append({
        "name": c["name"], "city": c["city"], "state": "",
        "country": c["country"],
        "latitude": c["lat"], "longitude": c["lon"],
        "geocode_source": "wikipedia_geodata",
        "source": "wikipedia_cathedrals",
        "denomination": denom, "family": family,
        "faith_tradition": trad,
        "classification_source": "wikipedia_geodata",
        "denomination_affiliation": c.get("diocese", ""),
    })

if not rows_data:
    log("Nothing to import."); import sys; sys.exit(0)

df = pd.DataFrame(rows_data)
db = sqlite3.connect(DB)
max_id = db.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]
df["id"] = range(max_id + 1, max_id + 1 + len(df))

df.to_sql("_cathedrals_temp", db, if_exists="replace", index=False)
db.execute("CREATE INDEX IF NOT EXISTS idx_cat_id ON _cathedrals_temp(id)")
db.execute("""
    INSERT INTO churches (id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source, denomination_affiliation)
    SELECT id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source, denomination_affiliation
    FROM _cathedrals_temp
""")
inserted = db.execute("SELECT COUNT(*) FROM _cathedrals_temp").fetchone()[0]
db.execute("DROP TABLE _cathedrals_temp")

db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_inserted, fields_populated,
     records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
""", ("wikipedia_cathedrals", "import_cathedrals.py", NOW, NOW, inserted,
      "name,city,country,latitude,longitude,denomination,denomination_affiliation",
      len(unique), geocoded,
      f"Cathedrals from {len(cathedral_pages)} country pages: {inserted}/{len(unique)} imported."))
db.commit()

total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
db.close()

log(f"Inserted: {inserted:,}")
log(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%)")
log("Done")
