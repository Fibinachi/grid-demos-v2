#!/usr/bin/env python3
"""
Scrape Salvation Army locations via Google Places API called through the page context.
Uses Playwright to load salvationarmyusa.org (where the API key is authorized),
then calls Places API from within the page's JS context.
"""
import sys, time, json, mysql.connector
from playwright.sync_api import sync_playwright

RDS_HOST = "grantwizard.csjiu2wagplc.us-east-1.rds.amazonaws.com"
RDS_USER = "grantwizard"
RDS_PASS = "F3y6bBoQZeYPMJir"
TARGET_DB = "grantwizard_unified"

DENOM = "The Salvation Army"
FAITH = "christian"
SOURCE = "salvation_army_scraper"

# Major US cities to search (every state covered)
SEARCH_CITIES = [
    ("Columbia", "SC"), ("Charleston", "SC"), ("Greenville", "SC"),
    ("Atlanta", "GA"), ("Charlotte", "NC"), ("Raleigh", "NC"),
    ("Nashville", "TN"), ("Memphis", "TN"), ("Birmingham", "AL"),
    ("Jackson", "MS"), ("Miami", "FL"), ("Orlando", "FL"),
    ("Jacksonville", "FL"), ("Tampa", "FL"), ("Richmond", "VA"),
    ("Norfolk", "VA"), ("Washington", "DC"), ("Baltimore", "MD"),
    ("Wilmington", "DE"), ("Philadelphia", "PA"), ("Pittsburgh", "PA"),
    ("New York", "NY"), ("Buffalo", "NY"), ("Boston", "MA"),
    ("Hartford", "CT"), ("Providence", "RI"), ("Manchester", "NH"),
    ("Portland", "ME"), ("Burlington", "VT"), ("Newark", "NJ"),
    ("Cleveland", "OH"), ("Columbus", "OH"), ("Cincinnati", "OH"),
    ("Indianapolis", "IN"), ("Chicago", "IL"), ("Detroit", "MI"),
    ("Milwaukee", "WI"), ("Minneapolis", "MN"), ("Des Moines", "IA"),
    ("St Louis", "MO"), ("Kansas City", "MO"), ("Omaha", "NE"),
    ("Wichita", "KS"), ("Fargo", "ND"), ("Sioux Falls", "SD"),
    ("Dallas", "TX"), ("Houston", "TX"), ("San Antonio", "TX"),
    ("Austin", "TX"), ("Oklahoma City", "OK"), ("Little Rock", "AR"),
    ("New Orleans", "LA"), ("Louisville", "KY"), ("Denver", "CO"),
    ("Salt Lake City", "UT"), ("Phoenix", "AZ"), ("Albuquerque", "NM"),
    ("Las Vegas", "NV"), ("Los Angeles", "CA"), ("San Diego", "CA"),
    ("San Francisco", "CA"), ("Portland", "OR"), ("Seattle", "WA"),
    ("Boise", "ID"), ("Billings", "MT"), ("Cheyenne", "WY"),
    ("Anchorage", "AK"), ("Honolulu", "HI"),
]

LIMIT = None


def parse_args():
    global LIMIT
    for i, a in enumerate(sys.argv[1:], 1):
        if a == "--limit" and i < len(sys.argv):
            LIMIT = int(sys.argv[i + 1])

import os
GOOGLE_PLACES_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
if not GOOGLE_PLACES_KEY:
    raise ValueError("GOOGLE_PLACES_API_KEY environment variable is required")


def search_from_page(page, city, state):
    """Call Google Places Text Search from within the page context."""
    global GOOGLE_PLACES_KEY
    query = f"Salvation Army {city} {state}"
    result = page.evaluate(f"""async () => {{
        const url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            + "?query={query.replace(' ','+')}+Salvation+Army"
            + "&key=" + window.GOOGLE_PLACES_KEY;
        try {{
            const resp = await fetch(url);
            const data = await resp.json();
            return JSON.stringify(data);
        }} catch(e) {{
            return JSON.stringify({{error: e.message}});
        }}
    }}""")
    return json.loads(result)


def main():
    parse_args()
    print(f"Starting Salvation Army Places scraper", flush=True)
    print(f"Cities: {len(SEARCH_CITIES)}", flush=True)
    
    t0 = time.time()
    all_locations = []
    seen = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Load the Salvation Army site to authorize the API key
        print("Loading Salvation Army site to authorize API key...", flush=True)
        page.goto("https://www.salvationarmyusa.org/location-finder/", 
                   wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(3000)
        print(f"Page loaded", flush=True)
        
        cities_to_search = SEARCH_CITIES[:LIMIT] if LIMIT else SEARCH_CITIES
        
        for city, state in cities_to_search:
            if LIMIT and len(all_locations) >= LIMIT * 3:
                break
                
            print(f"  Searching {city}, {state}...", flush=True)
            try:
                data = search_from_page(page, city, state)
                if data.get("status") == "OK":
                    for r in data.get("results", []):
                        name = r.get("name", "").strip()
                        addr = r.get("formatted_address", "") or r.get("vicinity", "")
                        place_id = r.get("place_id", "")
                        
                        if place_id in seen:
                            continue
                        seen.add(place_id)
                        
                        # Parse address components
                        city_out = state_out = ""
                        for comp in r.get("address_components", []):
                            if "locality" in comp["types"]:
                                city_out = comp["long_name"]
                            elif "administrative_area_level_1" in comp["types"]:
                                state_out = comp["short_name"]
                        
                        if not city_out and not state_out:
                            # Parse from formatted address
                            parts = addr.split(",")
                            if len(parts) >= 2:
                                state_zip = parts[-1].strip().split()
                                if state_zip:
                                    state_out = state_zip[0]
                                if len(parts) >= 3:
                                    city_out = parts[-3].strip()
                        
                        all_locations.append({
                            "name": name,
                            "address": addr,
                            "city": city_out or city,
                            "state": state_out or state,
                            "place_id": place_id,
                        })
                    
                    print(f"    Found {len(data.get('results',[]))} locations ({len(all_locations)} total)", flush=True)
                else:
                    print(f"    API status: {data.get('status')}", flush=True)
            except Exception as e:
                print(f"    Error: {e}", flush=True)
            
            time.sleep(1)  # Rate limit
        
        browser.close()
    
    print(f"\nTotal unique locations: {len(all_locations)} ({time.time()-t0:.1f}s)", flush=True)
    
    # Write to RDS
    if all_locations:
        print("Connecting to RDS...", flush=True)
        conn = mysql.connector.connect(
            host=RDS_HOST, user=RDS_USER, password=RDS_PASS,
            database=TARGET_DB, connect_timeout=10
        )
        cur = conn.cursor()
        
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM core_names")
        max_id = cur.fetchone()[0]
        for t in ["core_contact", "core_address", "geo_coords", "denom_basic"]:
            cur.execute(f"SELECT COALESCE(MAX(id), 0) FROM {t}")
            max_id = max(max_id, cur.fetchone()[0])
        
        inserted = matched = 0
        for loc in all_locations:
            name = loc["name"]
            addr = loc["address"]
            city = loc["city"]
            state = loc["state"]
            
            cur.execute(
                "SELECT cn.id FROM core_names cn "
                "JOIN core_address ca ON ca.id = cn.id "
                "WHERE UPPER(cn.name) = UPPER(%s) AND ca.state = %s LIMIT 1",
                (name, state)
            )
            existing = cur.fetchone()
            
            if existing:
                cid = existing[0]
                if addr:
                    cur.execute("UPDATE core_address SET address=%s WHERE id=%s AND (address IS NULL OR address='')",
                               (addr, cid))
                cur.execute("UPDATE denom_basic SET denomination=%s WHERE id=%s AND (denomination IS NULL OR denomination='')",
                           (DENOM, cid))
                cur.execute("UPDATE denom_basic SET faith_tradition=%s WHERE id=%s AND (faith_tradition IS NULL OR faith_tradition='')",
                           (FAITH, cid))
                cur.execute("SELECT source FROM core_names WHERE id=%s", (cid,))
                row = cur.fetchone()
                src = row[0] if row else ""
                if SOURCE not in str(src):
                    new_src = (src + f",{SOURCE}") if src else SOURCE
                    cur.execute("UPDATE core_names SET source=%s WHERE id=%s", (new_src, cid))
                matched += 1
            else:
                max_id += 1
                new_id = max_id
                try:
                    cur.execute("INSERT INTO core_names (id, name, source) VALUES (%s, %s, %s)",
                               (new_id, name, SOURCE))
                    cur.execute("INSERT INTO core_contact (id) VALUES (%s)", (new_id,))
                    cur.execute("INSERT INTO core_address (id, address, city, state) VALUES (%s, %s, %s, %s)",
                               (new_id, addr, city, state))
                    cur.execute("INSERT INTO denom_basic (id, denomination, faith_tradition) VALUES (%s, %s, %s)",
                               (new_id, DENOM, FAITH))
                    inserted += 1
                except Exception as e:
                    print(f"  Error inserting {name}: {e}", flush=True)
            
            if (inserted + matched) % 50 == 0:
                conn.commit()
        
        conn.commit()
        conn.close()
        print(f"RDS: {inserted} inserted, {matched} matched ({time.time()-t0:.1f}s)", flush=True)
    
    print(f"Done!", flush=True)


if __name__ == "__main__":
    main()
