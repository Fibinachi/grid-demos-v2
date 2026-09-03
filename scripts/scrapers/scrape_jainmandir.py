"""
Scrape jainmandir.org — intercept SearchTempleByState JSON responses.
Uses Playwright to trigger each state's TempleDialog and capture the API response.
"""
import json, time, os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("data/jainmandir")
OUT.mkdir(parents=True, exist_ok=True)
JSON_OUT = OUT / "temples_raw.json"

STATES = [
    ("35","ANDAMAN AND NICOBAR ISLANDS"),("28","ANDHRA PRADESH"),("12","ARUNACHAL PRADESH"),
    ("18","ASSAM"),("10","BIHAR"),("34","CHANDIGARH"),("22","CHHATTISGARH"),
    ("26","DADRA AND NAGAR HAVELI"),("25","DAMAN AND DIU"),("30","GOA"),("13","GUJARAT"),
    ("6","HARYANA"),("7","HIMACHAL PRADESH"),("31","JAMMU AND KASHMIR"),("20","JHARKHAND"),
    ("15","KARNATAKA"),("32","KERALA"),("37","Ladakh"),("33","LAKSHADWEEP"),("5","MADHYA PRADESH"),
    ("1","MAHARASHTRA"),("27","MANIPUR"),("17","MEGHALAYA"),("36","MIZORAM"),("19","NAGALAND"),
    ("29","NCT OF DELHI"),("21","ODISHA"),("23","PUDUCHERRY"),("8","PUNJAB"),("4","RAJASTHAN"),
    ("11","SIKKIM"),("14","TAMIL NADU"),("24","TELANGANA"),("16","TRIPURA"),
    ("9","UTTAR PRADESH"),("2","UTTARAKHAND"),("3","WEST BENGAL"),
]

def run():
    all_temples = {}  # alias -> data
    api_responses = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        
        # Intercept SearchTempleByState API responses
        def handle_response(response):
            url = response.url
            if "/SearchTempleByState/" in url or "/SearchTempleByDistrict/" in url or "/SearchTempleByCountry/" in url:
                try:
                    data = response.json()
                    if isinstance(data, list):
                        for d in data:
                            alias = d.get("alias", "")
                            if alias:
                                all_temples[alias] = d
                        state_name = url.split("/SearchTempleByState/")[-1].rstrip("/") if "/SearchTempleByState/" in url else "district"
                        print(f"  Got {len(data)} temples from {state_name}")
                except:
                    pass
        
        page.on("response", handle_response)
        
        print("Navigating to page...")
        page.goto("https://www.jainmandir.org/MainPage/MandirListMenu.html",
                   wait_until="networkidle", timeout=30000)
        print(f"Loaded: {page.title()}")
        
        # Process each state
        state_select = page.locator("#statedata")
        view_btn = page.locator("button:has-text('View')").first
        
        for state_id, state_name in STATES:
            print(f"\n  {state_name}...", end="", flush=True)
            try:
                state_select.select_option(state_id)
                time.sleep(1)
                view_btn.click()
                time.sleep(2)  # Wait for API response + map render
                
                # Escape any modal that might appear
                page.keyboard.press("Escape")
                time.sleep(0.5)
                
            except Exception as e:
                print(f" ERR: {e}")
        
        # Also try outside India
        print(f"\n\nOutside India...")
        country_select = page.locator("#country_out")
        view_btn2 = page.locator("input[value='View']").last  # Outside India button
        if country_select.count() > 0:
            countries = ["USA", "UK", "CANADA", "AUSTRALIA", "UAE", "SINGAPORE", "KENYA",
                         "NEPAL", "THAILAND", "MALAYSIA", "BANGLADESH", "PAKISTAN", "SRI LANKA"]
            for country in countries:
                print(f"  {country}...", end="", flush=True)
                try:
                    country_select.select_option(country)
                    time.sleep(1)
                    if view_btn2.count() > 0:
                        view_btn2.click()
                        time.sleep(2)
                        page.keyboard.press("Escape")
                        time.sleep(0.5)
                except:
                    print(" skip", end="")
        
        browser.close()
    
    # Save results
    temples_list = list(all_temples.values())
    print(f"\n\n{'='*60}")
    print(f"Total unique temples: {len(temples_list)}")
    
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(temples_list, f, indent=2)
    print(f"Saved to {JSON_OUT}")
    
    # Import into churches.db
    print("\n=== Importing into churches.db ===")
    import sqlite3
    db = sqlite3.connect("churches.db")
    imported = 0
    for t in temples_list:
        name = t.get("name", "")
        location = t.get("location", "")
        alias = t.get("alias", "")
        city = t.get("cityAlias", "") or ""
        
        if not name or not location:
            continue
        
        lat, lon = None, None
        if location and "," in location:
            parts = location.split(",")
            try:
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
            except:
                pass
        
        if not lat or not lon:
            continue
        
        # Check if already exists
        exists = db.execute("SELECT id FROM churches WHERE source='jainmandir' AND source_id=?", (alias,)).fetchone()
        if not exists:
            db.execute("""INSERT INTO churches 
                (name, faith, latitude, longitude, country, city, source, source_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name[:500], "Jain", lat, lon, "IN" if not city else None, city, 
                 "jainmandir", alias, "active"))
            imported += 1
    
    db.commit()
    db.close()
    print(f"Imported {imported} new Jain temples (total in dataset: {len(temples_list)})")

if __name__ == "__main__":
    run()
