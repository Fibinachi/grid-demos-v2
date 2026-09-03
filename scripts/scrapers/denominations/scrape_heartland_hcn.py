#!/usr/bin/env python3
"""
Scrape Heartland Church Network (HCN) directory
Serves: Nebraska / western Iowa — Southern Baptist association
URL: https://www.heartlandchurchnetwork.org/directory.html
"""
import json, csv, re, sys
from datetime import datetime

DATA_FILE = r"c:\Users\charlesp\AppData\Roaming\Code\User\workspaceStorage\c4d48b54999cabb13478f02027b13da3\GitHub.copilot-chat\chat-session-resources\0a49250f-e20e-4c02-8125-c76e20c57972\call_00_RUm2kye74kej97orKkDA4314__vscode-1781317451581\content.txt"

# The JSON data starts after "Result: "
with open(DATA_FILE, encoding='utf-8') as f:
    content = f.read()

# Find JSON array in the content
match = re.search(r'\[.*\]', content, re.DOTALL)
if match:
    raw_data = json.loads(match.group())
else:
    print("ERROR: Could not find JSON data")
    sys.exit(1)

print(f"Found {len(raw_data)} church entries")

# Name mapping from imgSrc filename slugs to clean church names
NAME_MAP = {
    "boh": "Beacon of Hope Church SBC",
    "bethel": "Bethel Baptist Church (Lincoln, NE)",
    "calvary": "Calvary Baptist Church (Glenwood, IA)",
    "calvary-community": "Calvary Community Church (Madison, NE)",
    "cff": "Christ Foundation Fellowship",
    "citylight-mosaic": "Citylight Mosaic Church",
    "country-bible": "Country Bible Church",
    "crossroads-community": "Crossroads Community Church (Red Oak, IA)",
    "emmaus-bible": "Emmaus Bible Church",
    "faithful-hearts": "Faithful Hearts Ministry",
    "fbc-bellevue": "First Baptist Church (Bellevue, NE)",
    "fbc-columbus": "First Baptist Church (Columbus, NE)",
    "fbc-tekamah": "First Baptist Church (Tekamah, NE)",
    "god-s-missionary": "God's Missionary Church",
    "grace": "Grace Fellowship (Omaha, NE)",
    "harrison-st": "Harrison Street Baptist Church (Seward, NE)",
    "heartland-baptist": "Home Church (Norfolk, NE)",
    "heartland-community": "Hope Church (Beatrice, NE)",
    "homestead": "Homestead (Beatrice, NE)",
    "house-on-the-rock": "House on the Rock (Omaha, NE)",
    "iglesia-discipulos": "Iglesia de Discipulos",
    "international-church-christ-built": "International Church Christ BUILT",
    "lifespring": "LifeSpring Church",
    "lincoln-revival": "Lincoln Revival Church",
    "lincoln-vision": "Lincoln Vision Church",
    "living-water": "Living Water Church",
    "lwc": "Living Word Church (Plattsmouth, NE)",
    "mt-moriah": "Mt. Moriah (Omaha, NE)",
    "new-beginning": "New Beginning Community Baptist Church",
    "new-covenant": "New Covenant Church",
    "new-hope": "New Hope / Quest Church",
    "north-metro": "North Metro Bible Church",
    "northern-heights": "Northern Heights Baptist Church",
    "northridge-falls-city": "Northridge Church (Falls City, NE)",
    "northridge-humboldt": "Northridge Church (Humboldt, NE)",
    "northridge-peru": "Northridge Church (Peru, NE)",
    "northside": "Northside Church (Omaha, NE)",
    "pib": "PIB South Sioux",
    "prince-of-peace": "Prince of Peace Baptist Church (Omaha, NE)",
    "quimby": "Quimby Baptist Church",
    "redemption-hill": "Redemption Hill Bible Church",
    "renewed-hope": "Renewed Hope Church",
    "restore": "Restore Church",
    "second-baptist": "Second Baptist Church (Omaha, NE)",
    "shiloh": "Shiloh Missionary Baptist Church (Omaha, NE)",
    "southern-hills": "Southern Hills Baptist Church",
    "southview": "Southview Baptist Church",
    "sower": "Sower Church",
    "spring-baptist": "Spring Baptist Church (NE)",
    "st-mark": "St. Mark Baptist Church",
    "iccb": "International Church Christ BUILT",
    "lincoln-karen-christian": "Lincoln Revival Church",
    "lincoln-vision-community": "Lincoln Vision Community Church",
    "lincoln-zomi": "Living Water Church (Lincoln, NE)",
    "new-beginning-community": "New Beginning Community Baptist Church",
    "new-covenant-community": "New Covenant Church",
    "new-life-baptist": "New Life Baptist Church",
    "north-metro-bible": "North Metro Bible Church",
    "northside-community": "Northside Church (Omaha, NE)",
    "pib-ssc": "PIB South Sioux",
    "restore-espanol": "Restore Church (Spanish)",
    "2nd-baptist": "Second Baptist Church (Omaha, NE)",
    "springfield-baptist": "Springfield Baptist Church",
    "st-matthew": "St. Matthew Baptist Church",
    "venture": "Venture Church",
    "way-maker": "Waymaker Baptist Church",
    "westside": "Westside Church",
    "woodbridge": "Woodbridge Church",
}  # <-- keep this closing brace

results = []
for entry in raw_data:
    img_src = entry.get("imgSrc", "")
    url = entry.get("url", "")
    if not img_src or not url:
        continue
    
    # Extract filename slug from imgSrc path
    raw_name = img_src.split("/")[-1]
    # Strip _orig suffix (if present) and file extension with optional query params
    raw_name = re.sub(r'(?:_orig)?\.(png|jpg|jpeg|gif|webp)(\?.*)?$', '', raw_name, flags=re.I)
    # Also handle .png?timestamp directly (without _orig)
    raw_name = re.sub(r'\.(png|jpg|jpeg|gif|webp)(\?.*)?$', '', raw_name, flags=re.I)
    filename = raw_name
    
    # Get clean name
    name = NAME_MAP.get(filename, "")
    if not name:
        name = filename.replace("-", " ").replace("_", " ").title()
    
    # Try to determine city from URL or name
    city_hint = ""
    if "omaha" in url.lower() or "(omaha" in name.lower():
        city_hint = "Omaha"
    elif "lincoln" in url.lower() or "lincoln" in name.lower():
        city_hint = "Lincoln"
    elif "norfolk" in url.lower():
        city_hint = "Norfolk"
    elif "beatrice" in url.lower():
        city_hint = "Beatrice"
    elif "falls-city" in url.lower():
        city_hint = "Falls City"
    elif "humboldt" in url.lower():
        city_hint = "Humboldt"
    elif "peru" in url.lower():
        city_hint = "Peru"
    elif "south-sioux" in url.lower() or "pib" in filename.lower():
        city_hint = "South Sioux City"
    
    results.append({
        "name": name,
        "website": url,
        "city": city_hint,
        "state": "NE",
        "denomination": "Southern Baptist Convention",
        "association": "Heartland Church Network",
        "source": "heartland_church_network_directory",
    })

# Save CSV
csv_path = "data/denom/heartland_church_network.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["name","website","city","state","denomination","association","source"])
    w.writeheader()
    w.writerows(results)

print(f"\nSaved {len(results)} churches to {csv_path}")
print(f"\nChurches:")
for r in results:
    print(f"  {r['name'][:50]:50s} | {r['website']}")
