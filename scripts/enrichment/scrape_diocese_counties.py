"""Scrape TEC diocese county boundaries from Wikipedia infoboxes.
Outputs: data/tec_diocese_counties.json — maps diocese name → [county_names]
"""
import requests, json, re, time

# All US TEC dioceses from Wikipedia list, with Wikipedia page names
DIOCESES = [
    "Episcopal Diocese of Alabama",
    "Episcopal Diocese of Alaska",
    "Episcopal Diocese of Arizona",
    "Episcopal Diocese of Arkansas",
    "Episcopal Diocese of Atlanta",
    "Episcopal Diocese of California",
    "Episcopal Diocese of Central Florida",
    "Episcopal Diocese of Central Gulf Coast",
    "Episcopal Diocese of Central New York",
    "Episcopal Diocese of Chicago",
    "Episcopal Diocese of Colorado",
    "Episcopal Diocese of Connecticut",
    "Episcopal Diocese of Dallas",
    "Episcopal Diocese of Delaware",
    "Episcopal Diocese of East Carolina",
    "Episcopal Diocese of East Tennessee",
    "Episcopal Diocese of Eastern Oregon",
    "Episcopal Diocese of Easton",
    "Episcopal Diocese of El Camino Real",
    "Episcopal Diocese of Florida",
    "Episcopal Diocese of Georgia",
    "Episcopal Diocese of Hawaii",
    "Episcopal Diocese of Idaho",
    "Episcopal Diocese of Indianapolis",
    "Episcopal Diocese of Iowa",
    "Episcopal Diocese of Kansas",
    "Episcopal Diocese of Kentucky",
    "Episcopal Diocese of Lexington",
    "Episcopal Diocese of Long Island",
    "Episcopal Diocese of Los Angeles",
    "Episcopal Diocese of Louisiana",
    "Episcopal Diocese of Maine",
    "Episcopal Diocese of Maryland",
    "Episcopal Diocese of Massachusetts",
    "Episcopal Diocese of Michigan",
    "Episcopal Diocese of Milwaukee",  # now part of Wisconsin
    "Episcopal Diocese of Minnesota",
    "Episcopal Diocese of Mississippi",
    "Episcopal Diocese of Missouri",
    "Episcopal Diocese of Montana",
    "Episcopal Diocese of Nebraska",
    "Episcopal Diocese of Nevada",
    "Episcopal Diocese of New Hampshire",
    "Episcopal Diocese of New Jersey",
    "Episcopal Diocese of New York",
    "Episcopal Diocese of Newark",
    "Episcopal Diocese of North Carolina",
    "Episcopal Diocese of North Dakota",
    "Episcopal Diocese of Northern California",
    "Episcopal Diocese of Northern Indiana",
    "Episcopal Diocese of Northern Michigan",
    "Episcopal Diocese of Northwest Texas",
    "Episcopal Diocese of Northwestern Pennsylvania",
    "Episcopal Diocese of Ohio",
    "Episcopal Diocese of Oklahoma",
    "Episcopal Diocese of Olympia",
    "Episcopal Diocese of Oregon",
    "Episcopal Diocese of Pennsylvania",
    "Episcopal Diocese of Pittsburgh",
    "Episcopal Diocese of Rhode Island",
    "Episcopal Diocese of Rio Grande",
    "Episcopal Diocese of Rochester",
    "Episcopal Diocese of San Diego",
    "Episcopal Diocese of San Joaquin",
    "Episcopal Diocese of South Carolina",
    "Episcopal Diocese of South Dakota",
    "Episcopal Diocese of Southeast Florida",
    "Episcopal Diocese of Southern Ohio",
    "Episcopal Diocese of Southern Virginia",
    "Episcopal Diocese of Southwest Florida",
    "Episcopal Diocese of Southwestern Virginia",
    "Episcopal Diocese of Spokane",
    "Episcopal Diocese of Springfield",
    "Episcopal Diocese of Tennessee",
    "Episcopal Diocese of Texas",
    "Episcopal Diocese of Upper South Carolina",
    "Episcopal Diocese of Utah",
    "Episcopal Diocese of Vermont",
    "Episcopal Diocese of Virginia",
    "Episcopal Diocese of Washington",
    "Episcopal Diocese of West Missouri",
    "Episcopal Diocese of West Tennessee",
    "Episcopal Diocese of West Texas",
    "Episcopal Diocese of West Virginia",
    "Episcopal Diocese of Western Kansas",
    "Episcopal Diocese of Western Louisiana",
    "Episcopal Diocese of Western Massachusetts",
    "Episcopal Diocese of Western New York",
    "Episcopal Diocese of Western North Carolina",
    "Episcopal Diocese of Wisconsin",
    "Episcopal Diocese of Wyoming",
    "Navajoland Area Mission",
    "Episcopal Diocese of the Great Lakes",
    "Episcopal Diocese of the Susquehanna",
]

def fetch_wikitext(page_title):
    """Fetch raw wikitext for a Wikipedia page."""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "parse",
        "page": page_title,
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
    }
    try:
        r = requests.get(url, params=params, timeout=15, headers={"User-Agent": "GrantWizard/1.0"})
        if r.status_code == 200:
            data = r.json()
            return data.get("parse", {}).get("wikitext", "")
        else:
            print(f"  HTTP {r.status_code} for {page_title}")
            return None
    except Exception as e:
        print(f"  Error for {page_title}: {e}")
        return None

def parse_territory(wikitext):
    """Extract territory/counties from infobox."""
    # Find the infobox - it starts with {{Infobox diocese
    infobox_start = wikitext.find("{{Infobox diocese")
    if infobox_start == -1:
        infobox_start = wikitext.find("{{Infobox diocese")
    if infobox_start == -1:
        return None
    
    # Find the territory/counties line
    infobox_section = wikitext[infobox_start:infobox_start + 3000]
    
    for field in ["territory", "counties", "jurisdiction"]:
        pattern = rf'\|\s*{field}\s*=\s*(.+?)(?:\n\||\n}})'
        m = re.search(pattern, infobox_section, re.IGNORECASE)
        if m:
            territory_text = m.group(1).strip()
            # Clean up wikitext markup
            territory_text = re.sub(r'\[\[([^\]|]+?)\]\]', r'\1', territory_text)  # [[Link]]
            territory_text = re.sub(r'\[\[[^\]]+\|([^\]]+)\]\]', r'\1', territory_text)  # [[Link|text]]
            territory_text = re.sub(r'\{\{[^}]+\}\}', '', territory_text)  # {{template}}
            territory_text = re.sub(r'<[^>]+>', '', territory_text)  # <ref> etc
            territory_text = re.sub(r'&lt;ref[^&]*&lt;/ref&gt;', '', territory_text)
            territory_text = territory_text.replace("''", "").replace("'''", "")
            
            # Extract county names - split on commas, "and", newlines
            counties = re.split(r',|\band\b|\n|•', territory_text)
            counties = [c.strip().rstrip('.').strip() for c in counties if c.strip()]
            # Filter to likely county names
            counties = [c for c in counties if len(c) > 2 and not c.lower().startswith(('see ', 'part of', 'including', 'all of', 'the ', 'also', 'plus'))]
            
            return counties
    return None

results = {}
for i, diocese in enumerate(DIOCESES):
    short_name = diocese.replace("Episcopal Diocese of ", "")
    print(f"[{i+1}/{len(DIOCESES)}] {short_name}...", end=" ", flush=True)
    
    wt = fetch_wikitext(diocese)
    if wt:
        counties = parse_territory(wt)
        if counties:
            # Clean county names
            cleaned = []
            for c in counties:
                c = c.strip()
                # Remove parenthetical like " (AZ)"
                c = re.sub(r'\s*\([^)]+\)\s*', '', c).strip()
                # Remove common suffixes for better matching
                c = re.sub(r'\s+County$', '', c, flags=re.IGNORECASE).strip()
                if c and len(c) > 2:
                    cleaned.append(c)
            results[short_name] = cleaned
            print(f"{len(cleaned)} counties: {', '.join(cleaned[:5])}...")
        else:
            print("no territory field found")
    else:
        print("failed to fetch")
    
    time.sleep(0.3)  # Be nice to Wikipedia

# Save
with open("data/tec_diocese_counties.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\nSaved {len(results)} dioceses to data/tec_diocese_counties.json")

# Quick stats
single_county = sum(1 for v in results.values() if len(v) == 1)
multi_county = sum(1 for v in results.values() if len(v) > 1)
print(f"Single-county: {single_county}, Multi-county: {multi_county}")
