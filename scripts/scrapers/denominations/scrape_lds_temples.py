"""Scrape churchofjesuschristtemples.org — all LDS temples with coordinates."""
import re, sqlite3, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime
import pandas as pd

DB = "E:/grid/churches.db"
NOW = datetime.utcnow().isoformat()
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
t0 = time.time()
BASE = "https://churchofjesuschristtemples.org"

def fetch(url, retries=2):
    req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0 (charles@example.com)"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
            else: raise
    return ""

def log(msg):
    print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)

# ── 1. Get all temple links from main page ──
log("Fetching temple list...")
html = fetch(f"{BASE}/temples/")

# Extract all temple links: <a href="/temple-name/">Temple Name</a>
# The page structure: links in alphabetical sections
links = re.findall(r'<a href="/([a-z][a-z-]+-temple)/">([^<]+)</a>', html)
# Also catch ones without "-temple" suffix that still end in temple name
links2 = re.findall(r'<a href="/([a-z][a-z-]+)/">([^<]+Temple)</a>', html)

# Dedup by slug
seen = set()
temples = []
for slug, name in links + links2:
    if slug in seen or slug in ("temples", "news", "status", "maps", "library", "statistics"):
        continue
    seen.add(slug)
    temples.append({"slug": slug, "name": name.strip()})

log(f"Found {len(temples)} temple links")

# ── 2. Scrape each temple page for details ──
for i, t in enumerate(temples):
    url = f"{BASE}/{t['slug']}/"
    try:
        page = fetch(url)
        
        # Coordinates from Google Maps link: @lat,lon,zoom
        coords = re.search(r'/maps/[^@]*@([\d.-]+),([\d.-]+),\d+z', page)
        if coords:
            t["lat"] = float(coords.group(1))
            t["lon"] = float(coords.group(2))
        
        # Address: text after "Address" heading, before next heading or "Telephone"
        # Pattern: "Address" heading, then text lines, then "Telephone"
        addr_match = re.search(r'heading "Address"[^>]*>.*?</h[45]>(.*?)(?:heading "Tel|text: "Tel)', page, re.DOTALL)
        if addr_match:
            addr_text = addr_match.group(1)
            # Extract text content
            lines = re.findall(r'text: "?([^"]*)"?', addr_text)
            if not lines:
                # Try alternate format
                lines = [t.strip() for t in re.sub(r'<[^>]+>', '\n', addr_text).split('\n') if t.strip()]
            
            # Parse: street, city/state, country
            addr_parts = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith("Tel") and not line.startswith("("):
                    addr_parts.append(line)
            
            if len(addr_parts) >= 1:
                t["address"] = addr_parts[0]
            if len(addr_parts) >= 2:
                t["city_state"] = addr_parts[1]
            if len(addr_parts) >= 3:
                t["country_raw"] = addr_parts[2]
        
        # Dedication date
        ded_match = re.search(r'heading "Dedication:"[^>]*>.*?</h[45]>(.*?)(?:heading|$)', page, re.DOTALL)
        if ded_match:
            ded_text = re.sub(r'<[^>]+>', ' ', ded_match.group(1)).strip()
            date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', ded_text)
            if date_match:
                t["dedication_date"] = date_match.group(1)
        
        # Status: "dedicated", "under construction", "announced"
        if "under construction" in page.lower():
            t["status"] = "under_construction"
        elif "announced" in page.lower() and "dedicated" not in page.lower():
            t["status"] = "announced"
        else:
            t["status"] = "dedicated"
        
    except Exception as e:
        log(f"  Error on {t['name']}: {e}")
    
    if (i + 1) % 20 == 0:
        gc = sum(1 for x in temples[:i+1] if "lat" in x)
        log(f"  {gc}/{i+1} geocoded")
    time.sleep(0.2)

geocoded = sum(1 for t in temples if "lat" in t)
log(f"Geocoded: {geocoded}/{len(temples)}")

# ── 3. Parse country/city/state ──
COUNTRY_MAP = {
    "nigeria": "NG", "ghana": "GH", "south africa": "ZA", "kenya": "KE",
    "ivory coast": "CI", "mozambique": "MZ", "madagascar": "MG", "zimbabwe": "ZW",
    "united states": "US", "usa": "US", "canada": "CA", "mexico": "MX",
    "brazil": "BR", "argentina": "AR", "chile": "CL", "peru": "PE",
    "colombia": "CO", "ecuador": "EC", "uruguay": "UY", "paraguay": "PY",
    "bolivia": "BO", "guatemala": "GT", "honduras": "HN", "el salvador": "SV",
    "nicaragua": "NI", "costa rica": "CR", "panama": "PA", "dominican republic": "DO",
    "haiti": "HT", "venezuela": "VE",
    "united kingdom": "UK", "england": "UK", "france": "FR", "germany": "DE",
    "italy": "IT", "spain": "ES", "portugal": "PT", "netherlands": "NL",
    "belgium": "BE", "switzerland": "CH", "austria": "AT", "sweden": "SE",
    "denmark": "DK", "norway": "NO", "finland": "FI", "hungary": "HU",
    "ukraine": "UA", "russia": "RU",
    "philippines": "PH", "india": "IN", "thailand": "TH", "indonesia": "ID",
    "singapore": "SG", "cambodia": "KH", "hong kong": "HK", "china": "CN",
    "south korea": "KR", "japan": "JP", "taiwan": "TW", "fiji": "FJ",
    "samoa": "WS", "tonga": "TO", "tahiti": "PF", "new zealand": "NZ",
    "australia": "AU", "papua new guinea": "PG", "vanuatu": "VU",
}

for t in temples:
    cr = (t.get("country_raw") or "").lower()
    country = "ZZ"
    for key, code in COUNTRY_MAP.items():
        if key in cr:
            country = code; break
    
    cs = (t.get("city_state") or "")
    # Split city/state
    parts = [p.strip() for p in cs.split(",")]
    city = parts[0] if parts else ""
    state = parts[1] if len(parts) > 1 else ""
    
    # US states from city_state
    US_STATES = {
        "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
        "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
        "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
        "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
        "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
        "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
        "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
        "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
        "new mexico": "NM", "new york": "NY", "north carolina": "NC",
        "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
        "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
        "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
        "vermont": "VT", "virginia": "VA", "washington": "WA",
        "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
        "district of columbia": "DC",
    }
    if country == "US" and state:
        state_l = state.lower().strip()
        for sname, sabbr in US_STATES.items():
            if sname in state_l or sabbr.lower() == state_l:
                state = sabbr; break
    
    # Canada provinces
    CA_PROVINCES = {
        "alberta": "AB", "british columbia": "BC", "manitoba": "MB",
        "new brunswick": "NB", "newfoundland": "NL", "nova scotia": "NS",
        "ontario": "ON", "quebec": "QC", "saskatchewan": "SK",
    }
    if country == "CA" and state:
        state_l = state.lower().strip()
        for pname, pabbr in CA_PROVINCES.items():
            if pname in state_l:
                state = pabbr; break
    
    t["country"] = country
    t["city"] = city
    t["state"] = state

# ── 4. Import ──
log("Importing...")
rows = []
for t in temples:
    if "lat" not in t: continue
    rows.append({
        "name": t["name"], "city": t.get("city", ""), "state": t.get("state", ""),
        "country": t.get("country", "ZZ"),
        "latitude": t["lat"], "longitude": t["lon"],
        "geocode_source": "lds_temples_org",
        "source": "lds_temples",
        "denomination": "Latter-day Saints", "family": "Latter-day Saints",
        "faith_tradition": "Christian",
        "classification_source": "lds_temples_org",
    })

if not rows:
    log("Nothing to import."); import sys; sys.exit(0)

df = pd.DataFrame(rows)
db = sqlite3.connect(DB)
max_id = db.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]
df["id"] = range(max_id + 1, max_id + 1 + len(df))

df.to_sql("_lds_temp", db, if_exists="replace", index=False)
db.execute("CREATE INDEX IF NOT EXISTS idx_lds_id ON _lds_temp(id)")
db.execute("""
    INSERT INTO churches (id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source)
    SELECT id, name, city, state, country, latitude, longitude,
        geocode_source, source, denomination, family, faith_tradition, classification_source
    FROM _lds_temp
""")
inserted = db.execute("SELECT COUNT(*) FROM _lds_temp").fetchone()[0]
db.execute("DROP TABLE _lds_temp")

db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_inserted, fields_populated,
     records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
""", ("lds_temples", "scrape_lds_temples.py", NOW, NOW, inserted,
      "name,city,state,country,latitude,longitude,denomination",
      len(temples), geocoded,
      f"LDS temples: {inserted}/{len(temples)} scraped from churchofjesuschristtemples.org"))
db.commit()

total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
db.close()

log(f"Inserted: {inserted:,}")
log(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%)")
log("Done")
