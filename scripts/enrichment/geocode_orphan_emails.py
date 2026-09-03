"""Geocode orphan records (email but no city/state) using website scraping + Nominatim."""
import sqlite3, urllib.request, urllib.parse, json, time, re, os

conn = sqlite3.connect('churches.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("""
    SELECT id, name, email, phone, website 
    FROM churches 
    WHERE email != '' AND email IS NOT NULL 
      AND (city IS NULL OR city = '') 
      AND (state IS NULL OR state = '')
    ORDER BY id
""")
orphans = c.fetchall()
print(f"Orphan records to geocode: {len(orphans)}")

# US state abbreviations + name mapping
STATE_MAP = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
    'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
    'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
    'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
    'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
    'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
    'wisconsin': 'WI', 'wyoming': 'WY'
}

# Area code -> state mapping (first digit of area code)
# Rough mapping for common area codes
AREA_CODE_STATE = {
    907: 'AK', 205: 'AL', 251: 'AL', 334: 'AL', 256: 'AL', 938: 'AL',
    479: 'AR', 501: 'AR', 870: 'AR', 480: 'AZ', 520: 'AZ', 602: 'AZ', 623: 'AZ', 928: 'AZ',
    209: 'CA', 213: 'CA', 310: 'CA', 323: 'CA', 408: 'CA', 415: 'CA', 510: 'CA', 530: 'CA',
    559: 'CA', 562: 'CA', 619: 'CA', 626: 'CA', 650: 'CA', 661: 'CA', 707: 'CA', 714: 'CA',
    760: 'CA', 805: 'CA', 818: 'CA', 831: 'CA', 858: 'CA', 909: 'CA', 916: 'CA', 925: 'CA',
    949: 'CA', 951: 'CA', 303: 'CO', 719: 'CO', 720: 'CO', 970: 'CO',
    203: 'CT', 475: 'CT', 860: 'CT', 959: 'CT',
    202: 'DC', 302: 'DE', 239: 'FL', 305: 'FL', 321: 'FL', 352: 'FL', 386: 'FL', 407: 'FL',
    561: 'FL', 727: 'FL', 754: 'FL', 772: 'FL', 786: 'FL', 813: 'FL', 850: 'FL', 863: 'FL',
    904: 'FL', 941: 'FL', 954: 'FL', 404: 'GA', 470: 'GA', 478: 'GA', 678: 'GA', 706: 'GA',
    762: 'GA', 770: 'GA', 912: 'GA', 808: 'HI', 515: 'IA', 563: 'IA', 319: 'IA', 641: 'IA',
    712: 'IA', 208: 'ID', 217: 'IL', 224: 'IL', 309: 'IL', 312: 'IL', 331: 'IL', 618: 'IL',
    630: 'IL', 708: 'IL', 773: 'IL', 779: 'IL', 815: 'IL', 847: 'IL', 872: 'IL',
    219: 'IN', 260: 'IN', 317: 'IN', 463: 'IN', 574: 'IN', 765: 'IN', 812: 'IN', 930: 'IN',
    316: 'KS', 620: 'KS', 785: 'KS', 913: 'KS',
    270: 'KY', 364: 'KY', 502: 'KY', 606: 'KY', 859: 'KY',
    225: 'LA', 318: 'LA', 337: 'LA', 504: 'LA', 985: 'LA',
    339: 'MA', 351: 'MA', 413: 'MA', 508: 'MA', 617: 'MA', 774: 'MA', 781: 'MA', 857: 'MA',
    978: 'MA', 240: 'MD', 301: 'MD', 410: 'MD', 443: 'MD', 667: 'MD',
    207: 'ME', 231: 'MI', 248: 'MI', 269: 'MI', 313: 'MI', 517: 'MI', 586: 'MI', 616: 'MI',
    734: 'MI', 810: 'MI', 906: 'MI', 947: 'MI', 989: 'MI',
    218: 'MN', 320: 'MN', 507: 'MN', 612: 'MN', 651: 'MN', 763: 'MN', 952: 'MN',
    314: 'MO', 417: 'MO', 573: 'MO', 636: 'MO', 660: 'MO', 816: 'MO', 975: 'MO',
    228: 'MS', 601: 'MS', 662: 'MS', 769: 'MS',
    406: 'MT', 252: 'NC', 336: 'NC', 704: 'NC', 743: 'NC', 828: 'NC', 910: 'NC', 919: 'NC',
    980: 'NC', 984: 'NC', 701: 'ND', 308: 'NE', 402: 'NE', 531: 'NE',
    603: 'NH', 201: 'NJ', 551: 'NJ', 609: 'NJ', 732: 'NJ', 848: 'NJ', 856: 'NJ', 862: 'NJ',
    908: 'NJ', 973: 'NJ', 505: 'NM', 575: 'NM',
    702: 'NV', 725: 'NV', 212: 'NY', 315: 'NY', 329: 'NY', 332: 'NY', 347: 'NY', 363: 'NY',
    516: 'NY', 518: 'NY', 585: 'NY', 607: 'NY', 631: 'NY', 646: 'NY', 680: 'NY', 716: 'NY',
    718: 'NY', 838: 'NY', 845: 'NY', 914: 'NY', 917: 'NY', 934: 'NY',
    216: 'OH', 220: 'OH', 234: 'OH', 283: 'OH', 330: 'OH', 380: 'OH', 419: 'OH', 440: 'OH',
    513: 'OH', 567: 'OH', 614: 'OH', 740: 'OH', 937: 'OH',
    405: 'OK', 539: 'OK', 580: 'OK', 918: 'OK',
    458: 'OR', 503: 'OR', 541: 'OR', 971: 'OR',
    215: 'PA', 223: 'PA', 267: 'PA', 272: 'PA', 412: 'PA', 445: 'PA', 484: 'PA', 570: 'PA',
    610: 'PA', 717: 'PA', 724: 'PA', 814: 'PA', 835: 'PA', 878: 'PA',
    401: 'RI', 803: 'SC', 843: 'SC', 854: 'SC', 864: 'SC',
    605: 'SD', 423: 'TN', 615: 'TN', 629: 'TN', 731: 'TN', 865: 'TN', 901: 'TN', 931: 'TN',
    210: 'TX', 214: 'TX', 254: 'TX', 325: 'TX', 361: 'TX', 409: 'TX', 430: 'TX', 432: 'TX',
    469: 'TX', 512: 'TX', 682: 'TX', 713: 'TX', 726: 'TX', 737: 'TX', 806: 'TX', 817: 'TX',
    830: 'TX', 832: 'TX', 903: 'TX', 915: 'TX', 936: 'TX', 940: 'TX', 956: 'TX', 972: 'TX',
    979: 'TX', 385: 'UT', 435: 'UT', 801: 'UT',
    276: 'VA', 434: 'VA', 540: 'VA', 571: 'VA', 703: 'VA', 757: 'VA', 804: 'VA',
    802: 'VT', 206: 'WA', 253: 'WA', 360: 'WA', 425: 'WA', 509: 'WA', 564: 'WA',
    262: 'WI', 414: 'WI', 534: 'WI', 608: 'WI', 715: 'WI', 920: 'WI',
    304: 'WV', 681: 'WV', 307: 'WY'
}

def area_code_to_state(phone):
    """Guess state from phone area code."""
    if not phone:
        return None
    digits = re.sub(r'\D', '', phone)
    if len(digits) >= 3:
        ac = int(digits[:3])
        return AREA_CODE_STATE.get(ac)
    return None

def extract_city_from_name(name):
    """Extract potential city name from church name."""
    if not name:
        return None
    # Common patterns: "CityName CHURCH", "CityName BAPTIST", etc.
    # Look for known US city names in the church name
    # For now, just check if name starts with what looks like a city
    parts = name.split()
    if len(parts) >= 2:
        # Check if last part is CHURCH/BAPTIST/etc - then first part might be city
        suffixes = {'CHURCH', 'BAPTIST', 'PRESBYTERIAN', 'METHODIST', 'LUTHERAN', 'CATHOLIC',
                     'SDA', 'ADVENTIST', 'MINISTRIES', 'MINISTRY', 'FELLOWSHIP', 'TEMPLE',
                     'MOSQUE', 'SYNAGOGUE', 'MISSION', 'CHAPEL'}
        first_word = parts[0].rstrip(',')
        return first_word
    return None

def try_website_for_location(website):
    """Quick scrape of website for location info in footer/header."""
    if not website or website in ('https://', 'http://', ''):
        return None
    try:
        req = urllib.request.Request(website, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=8)
        html = resp.read(50000).decode('utf-8', 'replace').lower()
        
        # Look for city, state patterns in text
        found_locations = []
        for state_name, state_abbr in STATE_MAP.items():
            if state_name in html:
                found_locations.append(state_abbr)
            # Also check for "City, ST" pattern
            for match in re.finditer(rf'([a-z\s]+),\s*{state_abbr}', html):
                city = match.group(1).strip().title()
                if len(city) > 2:
                    found_locations.append((city, state_abbr))
        
        if found_locations:
            return found_locations
        return None
    except:
        return None

def try_nominatim(name, state_hint=None):
    """Forward geocode by name with optional state hint."""
    query = name
    if state_hint:
        query += f", {state_hint}"
    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1, "addressdetails": 1})
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        if data:
            r = data[0]
            addr = r.get("address", {})
            city = addr.get("city", "") or addr.get("town", "") or addr.get("village", "") or addr.get("hamlet", "")
            state = addr.get("state", "")
            state_abbr = STATE_MAP.get(state.strip().lower(), state)
            return city, state_abbr
    except:
        pass
    return None, None

fixed = 0
for r in orphans:
    cid = r['id']
    name = r['name']
    phone = r['phone']
    website = r['website']
    
    print(f"\n[{cid}] {name[:50]:50s}")
    
    # Strategy 1: Try website for address
    if website and website not in ('https://', 'http://'):
        print(f"  Trying website {website[:50]}...")
        loc = try_website_for_location(website)
        if loc:
            print(f"  Found in website: {loc}")
    
    # Strategy 2: Try Nominatim with name + state hint from area code
    state_hint = area_code_to_state(phone)
    if state_hint:
        print(f"  Area code suggests: {state_hint}")
    
    city, state = try_nominatim(name, state_hint)
    if city and state:
        print(f"  ✅ Nominatim: {city}, {state}")
        c.execute("UPDATE churches SET city=?, state=?, geocode_source='nominatim_name' WHERE id=?", (city, state, cid))
        fixed += 1
    else:
        print(f"  ❌ No Nominatim result")
    
    time.sleep(1.0)

conn.commit()
print(f"\n=== Geocoded: {fixed}/{len(orphans)} ===")
conn.close()
