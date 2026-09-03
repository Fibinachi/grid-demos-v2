"""Try Overpass query by city+state for SBC church addresses."""
import sqlite3
import urllib.request
import urllib.parse
import json
import time
import re

OVERSPASS_URL = "https://overpass-api.de/api/interpreter"

def normalize(name):
    n = name.upper().strip()
    n = re.sub(r'[^A-Z0-9\s]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    for w in ['BAPTIST', 'FIRST', 'SECOND', 'THIRD', 'MISSIONARY',
              'OF', 'THE', 'AND', 'AT', 'INC', 'MISSION', 'MINISTRIES',
              'MINISTRY', 'FELLOWSHIP', 'TEMPLE', 'CHAPEL', 'CATHEDRAL',
              'CHURCH']:
        n = re.sub(r'\b' + w + r'\b', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def names_match(osm_name, church_name):
    if not osm_name:
        return False
    o = normalize(osm_name)
    c = normalize(church_name)
    if not o or not c:
        return False
    if o == c:
        return True
    if len(o) >= 4 and (o in c or c in o):
        return True
    o_words = set(o.split())
    c_words = set(c.split())
    if len(o_words) >= 2 and len(c_words) >= 2:
        common = o_words & c_words
        if len(common) >= min(len(o_words), len(c_words)) * 0.6:
            return True
    return False

def has_addr(elem):
    tags = elem.get("tags", {})
    return bool(tags.get("addr:housenumber") and tags.get("addr:street"))

def extract_addr(elem):
    tags = elem.get("tags", {})
    parts = []
    if tags.get("addr:housenumber"):
        parts.append(tags["addr:housenumber"])
    if tags.get("addr:street"):
        parts.append(tags["addr:street"])
    return " ".join(parts) if parts else ""

def search_church(church_name, city, state):
    """Search for a specific church by name in a city."""
    safe_name = church_name[:60].replace('"', '').replace("'", "").replace("\\", "")
    safe_city = city.replace('"', '').replace("'", "").replace("\\", "")
    
    # Strategy: get all places of worship in city, then match locally
    query = f"""
    [out:json][timeout:15];
    area["name"="{safe_city}"]["admin_level"="8"]->.a;
    (
      node(area.a)[amenity=place_of_worship];
      way(area.a)[amenity=place_of_worship];
    );
    out center;
    """
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(OVERSPASS_URL, data=data)
    req.add_header("User-Agent", "GrantWizard/1.0 (research project)")
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        result = json.loads(resp.read())
        return result.get("elements", [])
    except Exception as e:
        return []

def main():
    conn = sqlite3.connect('churches.db')
    c = conn.cursor()
    
    # Test on first 50 SBC churches
    c.execute("""
        SELECT id, name, city, state, zip
        FROM churches
        WHERE classification_source IN ('sbc_directory', 'sbc_scrape')
          AND NULLIF(address, '') IS NULL
          AND NULLIF(zip, '') IS NOT NULL
        LIMIT 50
    """)
    churches = c.fetchall()
    
    print("Testing Overpass city search on 50 SBC churches...\n")
    matched = 0
    with_addr = 0
    city_cache = {}
    
    for i, ch in enumerate(churches):
        ch_id, ch_name, ch_city, ch_state, ch_zip = ch
        cache_key = f"{ch_city}|{ch_state}"
        
        print(f"[{i+1}/50] {ch_name[:40]:40s} | {ch_city}, {ch_state} {ch_zip}")
        
        if cache_key not in city_cache:
            elements = search_church(ch_name, ch_city, ch_state)
            city_cache[cache_key] = elements
            time.sleep(1.2)
        else:
            elements = city_cache[cache_key]
        
        if not elements:
            print(f"  No OSM results for this city")
            continue
        
        # Find best match
        best = None
        best_score = 0
        for elem in elements:
            tags = elem.get("tags", {})
            osm_name = tags.get("name", "")
            if names_match(osm_name, ch_name):
                score = 100 if normalize(osm_name) == normalize(ch_name) else 80
                if score > best_score:
                    best_score = score
                    best = elem
        
        if best:
            matched += 1
            if has_addr(best):
                addr = extract_addr(best)
                osm_name = best.get("tags", {}).get("name", "")
                print(f"  ✅ {addr:40s} (OSM: {osm_name[:30]})")
                with_addr += 1
            else:
                osm_name = best.get("tags", {}).get("name", "")
                tags = best.get("tags", {})
                # Check what address fields exist
                addr_fields = {k: v for k, v in tags.items() if k.startswith("addr:")}
                print(f"  ⚠ No street address. OSM: {osm_name[:30]} | addr tags: {addr_fields}")
        else:
            print(f"  No name match in OSM")
    
    print(f"\n=== Results: {matched}/50 matched name, {with_addr}/50 with addresses ===")
    conn.close()

if __name__ == "__main__":
    main()
