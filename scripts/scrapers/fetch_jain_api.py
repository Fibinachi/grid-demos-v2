"""
Fetch all Jain temple data from jainmandir.org API.
Endpoints discovered in LoadTempleLefletMap.js:
  /SearchTempleByState/{stateName}/
  /SearchTempleByDistrict/{id}/
  /SearchTempleByCountry/{country}/
  /Temple/Index/{alias}  (individual temple page)
"""
import requests, json, time, re
from pathlib import Path

BASE = "https://www.jainmandir.org"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
     "Accept": "application/json"}
OUT = Path("data/jainmandir")
OUT.mkdir(parents=True, exist_ok=True)

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

COUNTRIES = ["AUSTRALIA","BANGLADESH","BELGIUM","CANADA","CHINA","DUBAI","FIJI",
    "FRANCE","GERMANY","HONG KONG","INDONESIA","IRAN","ISRAEL","ITALY","JAPAN",
    "JORDAN","KENYA","KUWAIT","MALAYSIA","MAURITIUS","MYANMAR","NEPAL","NETHERLANDS",
    "NEW ZEALAND","NORWAY","OMAN","PAKISTAN","PHILIPPINES","QATAR","SAUDI ARABIA",
    "SINGAPORE","SOUTH AFRICA","SOUTH KOREA","SPAIN","SRI LANKA","SWEDEN","SWITZERLAND",
    "SYRIA","TANZANIA","THAILAND","UGANDA","UK","UKRAINE","USA","YEMEN","ZAMBIA","ZIMBABWE"]

all_temples = {}  # alias -> temple data
failed = []

# Fetch by state
print("=== Fetching by State ===")
for state_id, state_name in STATES:
    url = f"{BASE}/SearchTempleByState/{state_name}/"
    try:
        r = requests.get(url, headers=H, timeout=30)
        if r.status_code == 200 and len(r.text) > 10:
            data = r.json()
            if isinstance(data, list):
                for d in data:
                    alias = d.get("alias", "")
                    if alias:
                        all_temples[alias] = d
                print(f"  {state_name:30s} {len(data):5d} temples")
            else:
                print(f"  {state_name:30s} NOT A LIST: {str(data)[:100]}")
        else:
            failed.append(state_name)
            print(f"  {state_name:30s} FAILED ({r.status_code})")
    except Exception as e:
        failed.append(state_name)
        print(f"  {state_name:30s} ERROR: {str(e)[:60]}")
    time.sleep(0.5)  # Be polite

# Fetch outside India
print("\n=== Fetching Outside India ===")
for country in COUNTRIES:
    url = f"{BASE}/SearchTempleByCountry/{country}/"
    try:
        r = requests.get(url, headers=H, timeout=30)
        if r.status_code == 200 and len(r.text) > 10:
            data = r.json()
            if isinstance(data, list):
                for d in data:
                    alias = d.get("alias", "")
                    if alias:
                        all_temples[alias] = d
                print(f"  {country:20s} {len(data):5d} temples")
            else:
                print(f"  {country:20s} bad data")
        else:
            print(f"  {country:20s} FAILED ({r.status_code})")
    except Exception as e:
        print(f"  {country:20s} ERROR: {str(e)[:60]}")
    time.sleep(0.5)

# Save
temples_list = list(all_temples.values())
json.dump(temples_list, open(OUT / "temples.json", "w", encoding="utf-8"), indent=2)
print(f"\n{'='*60}")
print(f"Total unique temples: {len(temples_list)}")
print(f"Failed states: {len(failed)}")
if failed:
    print(f"  Failed: {failed}")
print(f"Saved to {OUT}/temples.json")

# Also try to fetch individual pages for more detail
if len(temples_list) > 0:
    print(f"\n=== Fetching individual temple pages (sample) ===")
    sample_aliases = list(all_temples.keys())[:5]
    for alias in sample_aliases:
        url = f"{BASE}/Temple/Index/{alias}"
        try:
            r = requests.get(url, headers=H, timeout=15)
            print(f"  /Temple/Index/{alias}: {r.status_code} ({len(r.text)} bytes)")
            if r.status_code == 200:
                # Save sample
                with open(OUT / f"temple_{alias}.html", "w", encoding="utf-8") as f:
                    f.write(r.text)
        except Exception as e:
            print(f"  /Temple/Index/{alias}: {e}")
