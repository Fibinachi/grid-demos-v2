"""Geocode Anglican cathedrals from report via Wikipedia GeoData API."""
import csv, json, sqlite3, time, urllib.request, urllib.parse
from datetime import datetime

DB = "E:/grid/churches.db"
CSV_IN = "E:/grid/reports/ungeocoded_no_city_state_100.csv"
NOW = datetime.utcnow()
TODAY = NOW.strftime("%Y-%m-%d")
t0 = time.time()

# Load names from the report
names = []
with open(CSV_IN, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        name = (row.get("name") or "").strip()
        src = (row.get("source") or "").strip()
        if src == "wikipedia_list" and name and not name.startswith("GPX"):
            names.append(name)

print(f"Loaded {len(names)} names from report", flush=True)

# Geocode via Wikipedia API
results = []
for name in names:
    # Clean name for Wikipedia search
    clean = name.replace("'S", "s").replace("'S", "s")
    params = urllib.parse.urlencode({
        "action": "query",
        "titles": clean,
        "prop": "coordinates|pageprops",
        "format": "json"
    })
    url = f"https://en.wikipedia.org/w/api.php?{params}"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0 (charles@example.com)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        
        pages = data.get("query", {}).get("pages", {})
        found = None
        for pid, page in pages.items():
            if pid == "-1":
                continue  # Not found via exact title
            if "coordinates" in page:
                coords = page["coordinates"][0]
                found = (coords["lat"], coords["lon"], page.get("title", clean))
                break
        
        # Fallback: search if exact title not found
        if found is None:
            search_params = urllib.parse.urlencode({
                "action": "query", "list": "search",
                "srsearch": clean, "srlimit": 1, "format": "json"
            })
            search_url = f"https://en.wikipedia.org/w/api.php?{search_params}"
            with urllib.request.urlopen(
                urllib.request.Request(search_url, headers={"User-Agent": "GrantWizard/1.0 (charles@example.com)"}),
                timeout=10) as resp2:
                sdata = json.loads(resp2.read())
            search_results = sdata.get("query", {}).get("search", [])
            if search_results:
                pageid = search_results[0]["pageid"]
                # Get coordinates for this page
                coord_params = urllib.parse.urlencode({
                    "action": "query", "pageids": pageid,
                    "prop": "coordinates", "format": "json"
                })
                coord_url = f"https://en.wikipedia.org/w/api.php?{coord_params}"
                with urllib.request.urlopen(
                    urllib.request.Request(coord_url, headers={"User-Agent": "GrantWizard/1.0 (charles@example.com)"}),
                    timeout=10) as resp3:
                    cdata = json.loads(resp3.read())
                cpages = cdata.get("query", {}).get("pages", {})
                for cpid, cpage in cpages.items():
                    if "coordinates" in cpage:
                        coords = cpage["coordinates"][0]
                        found = (coords["lat"], coords["lon"], cpage.get("title", clean))
                        break
            
            if found is None:
                print(f"  NOT FOUND: {name[:50]}", flush=True)
                results.append((name, None, None, None))
            else:
                lat, lon, title = found
                print(f"  OK (search): {name[:50]} → {lat:.4f},{lon:.4f}", flush=True)
                results.append((name, lat, lon, title))
        else:
            lat, lon, title = found
            print(f"  OK: {name[:50]} → {lat:.4f},{lon:.4f}", flush=True)
            results.append((name, lat, lon, title))
        
        time.sleep(1.5)  # Wikipedia rate limit: be patient
        
    except Exception as e:
        print(f"  ERROR: {name[:50]} → {e}", flush=True)
        results.append((name, None, None, None))

# Count matches
matches = [r for r in results if r[1] is not None]
print(f"\nGeocoded: {len(matches)}/{len(names)}", flush=True)

# Insert into DB
if matches:
    db = sqlite3.connect(DB)
    db.execute("PRAGMA synchronous=OFF")
    max_id = db.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]
    
    inserted = 0
    for name, lat, lon, title in matches:
        max_id += 1
        # Extract city from Wikipedia title (e.g., "St Paul's Cathedral, London" → "London")
        parts = title.split(",")
        city = parts[-1].strip() if "," in title else ""
        country = "UK"
        state = "England"
        
        db.execute("""
            INSERT INTO churches (id, name, city, state, country, latitude, longitude,
                geocode_source, source, denomination, family, faith_tradition,
                classification_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'wikipedia_geodata', 'wikipedia_list',
                'Anglican', 'Anglican', 'Christian', 'wikipedia_geodata')
        """, (max_id, name, city, state, country, lat, lon))
        inserted += 1
    
    db.commit()
    
    # Log provenance
    db.execute("""
        INSERT INTO provenance_log 
        (source, script_name, started_at, completed_at, churches_updated,
         churches_inserted, fields_populated, records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, 'completed', ?)
    """, ("wikipedia_geodata", "geocode_wikipedia_cathedrals.py", TODAY, TODAY,
          inserted, "name,city,state,country,latitude,longitude",
          len(names), len(matches),
          f"Geocoded {len(matches)}/{len(names)} Anglican cathedrals via Wikipedia GeoData API."))
    
    db.commit()
    
    total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
    geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
    db.close()
    
    print(f"\nInserted: {inserted:,}", flush=True)
    print(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%)", flush=True)

print(f"\nDone in {time.time()-t0:.1f}s", flush=True)
