#!/usr/bin/env python3
"""
LOC Telephone Directory Collection — Church Listing Extractor

Phase 1: Inventory — fetch all Yellow Pages directories from the LOC collection
Phase 2: Download OCR text for each directory  
Phase 3: Parse church listings (name, address, phone) from OCR text

The LOC U.S. Telephone Directory Collection has ~3,481 directories on microfilm.
A subset are digitized and have OCR text available.

OCR text URLs follow the pattern:
  https://tile.loc.gov/storage-services/public/gdcmassbookdig/{call_number}/{call_number}.text.txt
"""

import json, os, re, time, requests, sqlite3
from pathlib import Path
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────
BASE_DIR = Path("E:/grid")
DATA_DIR = BASE_DIR / "data" / "loc_phone_dirs"
OCR_DIR = DATA_DIR / "ocr_text"
INVENTORY_FILE = DATA_DIR / "inventory.json"
RESULTS_DIR = DATA_DIR / "results"
CHURCHES_DB = BASE_DIR / "churches.db"

LOC_USER_AGENT = "LOC-API-Client/1.0 (research project)"
COLLECTION_URL = "https://www.loc.gov/collections/united-states-telephone-directory-collection/"
API_BASE = "https://www.loc.gov"
OCR_BASE = "https://tile.loc.gov/storage-services/public/gdcmassbookdig"

os.makedirs(OCR_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

HEADERS = {"User-Agent": LOC_USER_AGENT}


# ── Phase 1: Inventory ────────────────────────────────────────────────────
def fetch_inventory(save=True):
    """Fetch ALL Yellow Pages items from the LOC collection."""
    all_items = []
    page = 1
    
    print("📋 Fetching LOC telephone directory inventory...")
    
    while True:
        url = f"{COLLECTION_URL}?fo=json&c=200&sp={page}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code != 200:
                print(f"  Page {page}: HTTP {r.status_code}, stopping")
                break
            
            data = r.json()
            results = data.get("content", {}).get("results", [])
            if not results:
                print(f"  Page {page}: empty, done")
                break
            
            pagination = data.get("content", {}).get("pagination", "?")
            
            yp_count = 0
            for item in results:
                title = item.get("title", "")
                is_yp = "yellow" in title.lower()
                if is_yp:
                    yp_count += 1
                    all_items.append(item)
            
            print(f"  Page {page}: {len(results)} items, {yp_count} YP | pagination: {pagination}")
            page += 1
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  Page {page}: error — {e}")
            time.sleep(2)
            continue
    
    print(f"\n✅ Total Yellow Pages found: {len(all_items)}")
    
    if save and all_items:
        with open(INVENTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(all_items, f, indent=2, ensure_ascii=False)
        print(f"📁 Inventory saved: {INVENTORY_FILE}")
    
    return all_items


def load_inventory():
    """Load cached inventory."""
    if INVENTORY_FILE.exists():
        with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def summarize_inventory(items):
    """Print summary of the inventory."""
    by_location = {}
    by_decade = {}
    
    for item in items:
        loc_list = item.get("item", {}).get("location", [])
        location = " / ".join(loc_list) if loc_list else "Unknown"
        date = item.get("date", "?")
        call_no = item.get("item", {}).get("call_number", ["?"])[0]
        
        if location not in by_location:
            by_location[location] = {"count": 0, "dates": [], "latest": None}
        by_location[location]["count"] += 1
        by_location[location]["dates"].append(date)
        by_location[location]["latest"] = max(by_location[location]["latest"] or "0", str(date))
        
        decade = f"{str(date)[:3]}0s" if date and date != "?" else "Unknown"
        by_decade[decade] = by_decade.get(decade, 0) + 1
    
    print(f"\n📊 INVENTORY SUMMARY")
    print(f"{'='*60}")
    print(f"Total Yellow Pages directories: {len(items)}")
    print(f"Unique locations: {len(by_location)}")
    print(f"\nBy decade:")
    for dec in sorted(by_decade):
        print(f"  {dec}: {by_decade[dec]}")
    
    print(f"\nTop locations (by directory count):")
    top = sorted(by_location.items(), key=lambda x: x[1]["count"], reverse=True)[:20]
    for loc, info in top:
        print(f"  {loc}: {info['count']} dirs ({min(info['dates'])}-{max(info['dates'])})")
    
    print(f"\nMost recent per location:")
    recent = sorted(by_location.items(), key=lambda x: x[1]["latest"], reverse=True)[:15]
    for loc, info in recent:
        print(f"  {loc}: latest {info['latest']} ({info['count']} dirs)")


# ── Phase 2: Download OCR Text ─────────────────────────────────────────────
def download_ocr(item, force=False):
    """Download OCR text for a single directory. Returns path or None."""
    call_no = item.get("item", {}).get("call_number", [None])[0]
    if not call_no:
        return None
    
    out_path = OCR_DIR / f"{call_no}.txt"
    if out_path.exists() and not force:
        return out_path
    
    ocr_url = f"{OCR_BASE}/{call_no}/{call_no}.text.txt"
    
    try:
        r = requests.get(ocr_url, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            with open(out_path, "w", encoding="utf-8", errors="ignore") as f:
                f.write(r.text)
            return out_path
        elif r.status_code == 404:
            # Try alternate URL pattern
            ocr_url2 = f"{OCR_BASE}/{call_no}/{call_no}.txt"
            r2 = requests.get(ocr_url2, headers=HEADERS, timeout=30)
            if r2.status_code == 200:
                with open(out_path, "w", encoding="utf-8", errors="ignore") as f:
                    f.write(r2.text)
                return out_path
    except Exception as e:
        pass
    
    return None


def download_all_ocr(items, workers=8):
    """Download OCR text for all items with parallel workers."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    
    print(f"\n📥 Downloading OCR text for {len(items)} directories ({workers} workers)...")
    
    # Filter to items with call numbers that need downloading
    valid_items = []
    already = 0
    for idx, item in enumerate(items):
        call_no = item.get("item", {}).get("call_number", [None])[0]
        if call_no:
            out_path = OCR_DIR / f"{call_no}.txt"
            if not out_path.exists():
                valid_items.append((idx, item))
            else:
                already += 1
    
    print(f"  {len(valid_items)} to download, {already} already present")
    
    if not valid_items:
        print("  All already downloaded!")
        return 0, 0, already
    
    stats = {"downloaded": 0, "failed": 0}
    lock = threading.Lock()
    
    # Use a session for connection reuse
    session = requests.Session()
    session.headers.update(HEADERS)
    
    def download_one(item_tuple):
        idx, item = item_tuple
        call_no = item.get("item", {}).get("call_number", [None])[0]
        if not call_no:
            with lock:
                stats["failed"] += 1
            return False
        
        out_path = OCR_DIR / f"{call_no}.txt"
        ocr_url = f"{OCR_BASE}/{call_no}/{call_no}.text.txt"
        
        try:
            r = session.get(ocr_url, timeout=15)
            if r.status_code == 200:
                with open(out_path, "w", encoding="utf-8", errors="ignore") as f:
                    f.write(r.text)
                with lock:
                    stats["downloaded"] += 1
                return True
        except:
            pass
        
        with lock:
            stats["failed"] += 1
        return False
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(download_one, t): t for t in valid_items}
        for i, future in enumerate(as_completed(futures)):
            try:
                future.result(timeout=20)
            except:
                with lock:
                    stats["failed"] += 1
            
            total = stats["downloaded"] + stats["failed"]
            if total % 25 == 0 or total <= 3:
                pct = total / len(valid_items) * 100
                print(f"  [{total}/{len(valid_items)} {pct:.0f}%] ✅{stats['downloaded']} ❌{stats['failed']}")
    
    print(f"\n  Done: ✅{stats['downloaded']} downloaded, ❌{stats['failed']} failed, ⏭{already} already present")
    return stats["downloaded"], stats["failed"], already


# ── Phase 3: Parse Church Listings ──────────────────────────────────────────

# Church-related keywords for identifying church name lines
CHURCH_KEYWORDS = re.compile(
    r'(Church|Chapel|Tabernacle|Temple|Synagogue|Mosque|Cathedral|'
    r'Parish|Mission|Fellowship|Assembly\s+of\s+God|Congregation|Ministr(?:y|ies)|'
    r'Sanctuary|Abbey|Basilica|Shrine|Diocese|'
    r'Pentecostal|Adventist|Nazarene|Covenant|Orthodox)',
    re.IGNORECASE
)

# Lines that are definitely NOT church names (pastor/address/service info)
NOT_CHURCH_NAME = re.compile(
    r'^('
    r'Rev\.?\s|Pastor\b|Minister\b|Father\b|Rabbi\b|Dr\.?\s|Mr\.?\s|Mrs\.?\s|Ms\.?\s|Bishop\b|'
    r'Deacon|Elder\b|S\.?S\.?\s|Sunday\s+School|BTU?\s|Worship\s+(?:Service|11|10|\d)|'
    r'Morning\s+Worship|Evening\s+Worship|Service\s+\d|'
    r'Res\s|Residence\b|If\s+no\s+answer|Sun\s+(?:School|Services)'
    r')',
    re.IGNORECASE
)

# Lines that are clearly service schedule info, not church names
SERVICE_INFO = re.compile(
    r'^('
    r'S\.?S\.?\s+\d|Sunday\s+School|B\.?\s*T\.?\s*U\.?\s|BTU|'
    r'Worship\s+(?:Service|11|10|\d)|Morning\s+Worship|Evening\s+Worship|'
    r'Services?\s+\d|Sun\s+School|Prayer\s+Meeting|Bible\s+Study|'
    r'Teachers?\s+Meeting|Training\s+Union|^\d{1,2}:\d{2}\s*(?:AM|PM)'
    r')',
    re.IGNORECASE
)

# Garbage lines that are clearly not church entries
GARBAGE_LINES = re.compile(
    r'^('
    r'The\s+Classified|Published\s+for|venience\s+of|subscribers|'
    r'Telephone\s+Directory|^\s*\|?\s*\d+\s*$|^\s*\(Cont|^\s*Continued|'
    r'^\s*[-—â]{5,}\s*$|^\s*Page\s+\d|^\s*Compiled\s+by'
    r')',
    re.IGNORECASE
)

# Phone number at end of line after dashes: "---------------- 6-0151"
PHONE_AFTER_DASHES = re.compile(r'[-—â\s]{5,}\s*(\d{1,2}[-–]\d{4})')

# Phone inline: "Church Name 630 S 14th-7-2694" (address-phone on same line)
# The phone part after address: "14th-7-2694" where the number before the second dash is 1-2 digits
PHONE_INLINE = re.compile(r'(?:^|\s)(\d{1,2}[-–]\d{4})(?:\s|$|,|\.)')

# Phone with exchange name: "VErnon 3-2436", "AL 4-3186"
PHONE_EXCHANGE = re.compile(r'([A-Z]{2,8}\s+\d[-–]\d{4})', re.IGNORECASE)

# Old numeric phone: "7-2633", "59-6673", "3-1749"
PHONE_OLD_NUMERIC = re.compile(r'(?<!\d)(\d{1,2}[-–]\d{4})(?!\d)')

# Address with phone after dashes: "420 Graymnt Av N---------------- 3-3319"
ADDR_WITH_PHONE = re.compile(
    r'(\d+\s+[A-Za-z].*?(?:St|Ave?|Rd|Dr|Blvd|Ln|Way|Ct|Pl|Hwy|Pkwy|Cir|Ter|Hts|Highway|PI|Wy|Blvd?)\b)\s*[-—â]{3,}\s*(\d{1,2}[-–]\d{4})',
    re.IGNORECASE
)

# Street types for address detection
STREET_TYPES = r'(St|Ave?|Rd|Dr|Blvd|Ln|Way|Ct|Pl|Hwy|Route|Pkwy|Cir|Ter|Hts|Highway|PI|Wy|Blvd?|N|S|E|W)\b'


# ── Phone Modernization ──────────────────────────────────────────────────────

# Phone keypad: letters → numbers
_PHONE_KEYPAD = str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                               '22233344455566677778889999')

# Area code lookup: (state, city) → area code
# Built from NANPA database + manual curation for major cities
_AREA_CODES = {
    # Alabama
    ('Alabama', 'Birmingham'): '205',
    ('Alabama', 'Mobile'): '251',
    ('Alabama', 'Montgomery'): '334',
    ('Alabama', 'Huntsville'): '256',
    ('Alabama', 'Tuscaloosa'): '205',
    ('Alabama', 'Florence'): '256',
    ('Alabama', 'Gadsden'): '256',
    ('Alabama', 'Anniston'): '256',
    ('Alabama', 'Decatur'): '256',
    ('Alabama', 'Selma'): '334',
    # Alaska
    ('Alaska', 'Anchorage'): '907',
    ('Alaska', 'Fairbanks'): '907',
    ('Alaska', 'Juneau'): '907',
    # Arizona
    ('Arizona', 'Phoenix'): '602',
    ('Arizona', 'Tucson'): '520',
    ('Arizona', 'Mesa'): '480',
    # Arkansas
    ('Arkansas', 'Little Rock'): '501',
    # California
    ('California', 'Los Angeles'): '213',
    ('California', 'San Francisco'): '415',
    ('California', 'Oakland'): '510',
    ('California', 'San Diego'): '619',
    ('California', 'Sacramento'): '916',
    ('California', 'San Jose'): '408',
    ('California', 'Fresno'): '559',
    ('California', 'Long Beach'): '562',
    ('California', 'Pasadena'): '626',
    ('California', 'Anaheim'): '714',
    # Colorado
    ('Colorado', 'Denver'): '303',
    ('Colorado', 'Colorado Springs'): '719',
    # Connecticut
    ('Connecticut', 'Hartford'): '860',
    ('Connecticut', 'New Haven'): '203',
    # DC
    ('District of Columbia', 'Washington'): '202',
    # Florida
    ('Florida', 'Miami'): '305',
    ('Florida', 'Orlando'): '407',
    ('Florida', 'Tampa'): '813',
    ('Florida', 'Jacksonville'): '904',
    ('Florida', 'St. Petersburg'): '727',
    # Georgia
    ('Georgia', 'Atlanta'): '404',
    ('Georgia', 'Savannah'): '912',
    # Hawaii
    ('Hawaii', 'Honolulu'): '808',
    # Illinois
    ('Illinois', 'Chicago'): '312',
    ('Illinois', 'Springfield'): '217',
    # Indiana
    ('Indiana', 'Indianapolis'): '317',
    # Iowa
    ('Iowa', 'Des Moines'): '515',
    ('Iowa', 'Davenport'): '563',
    # Kansas
    ('Kansas', 'Wichita'): '316',
    # Kentucky
    ('Kentucky', 'Louisville'): '502',
    # Louisiana
    ('Louisiana', 'New Orleans'): '504',
    # Maryland
    ('Maryland', 'Baltimore'): '410',
    # Massachusetts
    ('Massachusetts', 'Boston'): '617',
    # Michigan
    ('Michigan', 'Detroit'): '313',
    # Minnesota
    ('Minnesota', 'Minneapolis'): '612',
    ('Minnesota', 'St. Paul'): '651',
    # Missouri
    ('Missouri', 'St. Louis'): '314',
    ('Missouri', 'Kansas City'): '816',
    # Nebraska
    ('Nebraska', 'Omaha'): '402',
    # Nevada
    ('Nevada', 'Las Vegas'): '702',
    # New Jersey
    ('New Jersey', 'Newark'): '973',
    ('New Jersey', 'Jersey City'): '201',
    # New Mexico
    ('New Mexico', 'Albuquerque'): '505',
    # New York
    ('New York', 'New York'): '212',
    ('New York', 'Buffalo'): '716',
    ('New York', 'Rochester'): '585',
    ('New York', 'Albany'): '518',
    ('New York', 'Syracuse'): '315',
    # North Carolina
    ('North Carolina', 'Charlotte'): '704',
    ('North Carolina', 'Raleigh'): '919',
    # Ohio
    ('Ohio', 'Cleveland'): '216',
    ('Ohio', 'Columbus'): '614',
    ('Ohio', 'Cincinnati'): '513',
    ('Ohio', 'Toledo'): '419',
    # Oklahoma
    ('Oklahoma', 'Oklahoma City'): '405',
    ('Oklahoma', 'Tulsa'): '918',
    # Oregon
    ('Oregon', 'Portland'): '503',
    # Pennsylvania
    ('Pennsylvania', 'Philadelphia'): '215',
    ('Pennsylvania', 'Pittsburgh'): '412',
    # Rhode Island
    ('Rhode Island', 'Providence'): '401',
    # South Carolina
    ('South Carolina', 'Columbia'): '803',
    # Tennessee
    ('Tennessee', 'Nashville'): '615',
    ('Tennessee', 'Memphis'): '901',
    # Texas
    ('Texas', 'Houston'): '713',
    ('Texas', 'Dallas'): '214',
    ('Texas', 'San Antonio'): '210',
    ('Texas', 'Austin'): '512',
    ('Texas', 'Fort Worth'): '817',
    ('Texas', 'El Paso'): '915',
    # Utah
    ('Utah', 'Salt Lake City'): '801',
    # Virginia
    ('Virginia', 'Richmond'): '804',
    ('Virginia', 'Norfolk'): '757',
    # Washington
    ('Washington', 'Seattle'): '206',
    ('Washington', 'Spokane'): '509',
    # Wisconsin
    ('Wisconsin', 'Milwaukee'): '414',
}


def _lookup_area_code(state, city):
    """Look up area code by state and city. Returns None if unknown."""
    if not state or not city:
        return None
    
    state = state.strip()
    city = city.strip()
    
    # Exact match
    key = (state, city)
    if key in _AREA_CODES:
        return _AREA_CODES[key]
    
    # Try just the first word of the city (e.g., "Los Angeles Central Area" → "Los Angeles")
    first_city = city.split()[0] if city else ""
    for (s, c), ac in _AREA_CODES.items():
        if s.lower() == state.lower() and c.lower().startswith(first_city.lower()):
            return ac
    
    return None


def modernize_phone(old_phone, state="", city=""):
    """
    Convert old-style phone number to modern E.164-ish format.
    
    Input formats:
      'ST 6-5378' → (205) 786-5378
      'TR 9-8271' → (205) 879-8271
      '7-2633'    → (205) 7-2633  (missing exchange prefix)
    
    Returns: (modern_phone, area_code, is_full_number)
    """
    if not old_phone or not old_phone.strip():
        return old_phone, None, False
    
    phone = old_phone.strip()
    
    # Already modern: (205) 555-1234 or 555-1234
    if re.match(r'^\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}$', phone):
        return phone, re.search(r'(\d{3})', phone).group(1), True
    
    # Exchange format: 'ST 6-5378', 'TR 9-8271', 'VErnon 3-2436'
    m = re.match(r'([A-Z]{2,8})\s+(\d)[-–](\d{4})', phone, re.IGNORECASE)
    if m:
        exchange = m.group(1).upper().translate(_PHONE_KEYPAD)  # ST → 78
        digit = m.group(2)
        number = m.group(3)
        local = f'{exchange}{digit}-{number}'  # 786-5378
        
        area_code = _lookup_area_code(state, city)
        if area_code:
            return f'({area_code}) {local}', area_code, True
        else:
            return local, None, False
    
    # Old numeric only: '7-2633', '59-6673'
    m = re.match(r'(\d{1,2})[-–](\d{4})$', phone)
    if m:
        local = f'{m.group(1)}-{m.group(2)}'
        area_code = _lookup_area_code(state, city)
        if area_code:
            return f'({area_code}) {local}', area_code, False  # incomplete (missing exchange prefix)
        else:
            return local, None, False
    
    # Other formats — return as-is
    return phone, None, False


def modernize_phones_in_results(results):
    """Add modernized phone numbers to extraction results."""
    modernized = 0
    for entry in results:
        old_phone = entry.get("phone", "")
        if old_phone:
            modern, area_code, is_full = modernize_phone(
                old_phone, 
                entry.get("state", ""), 
                entry.get("city", "")
            )
            entry["phone_modern"] = modern
            entry["area_code"] = area_code
            entry["phone_is_full"] = is_full
            if modern != old_phone:
                modernized += 1
        else:
            entry["phone_modern"] = None
            entry["area_code"] = None
            entry["phone_is_full"] = False
    
    return modernized


def clean_ocr_text(text):
    """Clean up common OCR artifacts."""
    # Fix common OCR errors
    text = text.replace('â', '-')  # OCR often reads — or – as â
    text = text.replace('€', '-')
    text = text.replace('â€', '—')
    text = text.replace('---', '—')
    return text


def extract_phone_from_line(line):
    """Extract phone number from a line. Returns phone string or None."""
    # Try exchange format first: "VErnon 3-2436"
    m = PHONE_EXCHANGE.search(line)
    if m:
        return m.group(1).strip()
    
    # Try dashed separator: "---------------- 6-0151"
    m = PHONE_AFTER_DASHES.search(line)
    if m:
        return m.group(1).strip()
    
    # Try old numeric: standalone "7-2633"
    m = PHONE_OLD_NUMERIC.search(line)
    if m:
        return m.group(1).strip()
    
    return None


def extract_address_from_line(line):
    """Extract street address from a line."""
    # Pattern: number + street name + street type
    m = re.search(r'(\d+\s+[A-Za-z0-9].*?' + STREET_TYPES + r')', line, re.IGNORECASE)
    if m:
        addr = m.group(1).strip()
        # Don't return if it's just a phone-like number
        if re.match(r'^\d{1,2}[-–]\d{4}$', addr):
            return None
        return addr
    return None


def split_name_addr_phone(line):
    """Split a line that has church name + address + phone all together.
    Example: 'Greater Shiloh Baptist Church 630 S 14th-7-2694'
    Returns (name, address, phone) tuple.
    """
    phone = extract_phone_from_line(line)
    
    # If phone found, try to separate address from name
    if phone:
        # Find where the phone is and work backwards
        phone_idx = line.find(phone)
        before_phone = line[:phone_idx].strip()
        
        # Try to find address at end of before_phone
        addr = extract_address_from_line(before_phone)
        if addr:
            name = before_phone[:before_phone.rfind(addr)].strip().rstrip('—').strip()
            return name, addr, phone
        else:
            # No clear address — just split off the phone
            return before_phone, '', phone
    
    # No phone — try to find address at end
    addr = extract_address_from_line(line)
    if addr:
        name = line[:line.rfind(addr)].strip().rstrip('—').strip()
        return name, addr, None
    
    return line, '', None


def find_churches_sections(text):
    """Find all church-related sections in Yellow Pages OCR text.
    Returns list of (section_text, denomination) tuples.
    """
    text = clean_ocr_text(text)
    
    # Find all section headers related to churches
    section_headers = [
        r'\n\s*CHURCHES[—-]\s*([A-Za-z\']+(?:\s*\(Cont\'?d\))?)',
        r'\n\s*([A-Za-z\']+)\s+CHURCHES',
        r'\n\s*CHURCHES\s*\n',
    ]
    
    sections = []
    
    for header_pattern in section_headers:
        for m in re.finditer(header_pattern, text, re.IGNORECASE):
            start = m.start()
            denom = m.group(1).strip() if m.lastindex and m.lastindex >= 1 else "General"
            
            # Find end of this section (next category or next churches section)
            # Look for next ALL CAPS section header that's not a continuation
            end_match = re.search(
                r'\n\s*[A-Z][A-Z\s&/\'-]{4,40}\s*\n(?!\s*(?:Services|Sunday|Worship|BTU|Morning|Evening|Pastor|Rev|S\.\s?S))',
                text[start+50:start+80000]
            )
            if end_match:
                end = start + 50 + end_match.start()
            else:
                end = min(len(text), start + 80000)
            
            section_text = text[start:end]
            sections.append((section_text, denom))
    
    # Deduplicate by start position (keep first occurrence)
    seen = set()
    unique = []
    for section, denom in sections:
        key = section[:100]
        if key not in seen:
            seen.add(key)
            unique.append((section, denom))
    
    return unique


def parse_church_entries(section_text, city="", state="", denom=""):
    """Parse church listings from a churches section of OCR text."""
    entries = []
    lines = section_text.split('\n')
    
    current = None  # Current church being built
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            if current and current.get("name"):
                entries.append(current)
                current = None
            continue
        
        # Skip garbage lines
        if GARBAGE_LINES.match(line):
            continue
        
        # Skip service schedule lines (ALWAYS skip these)
        if SERVICE_INFO.match(line):
            continue
        
        # Skip header lines (section titles, continuation markers)
        if re.match(r'^\s*(?:CHURCHES|Continued|Cont\'?d)\b', line, re.IGNORECASE):
            continue
        
        # Skip non-church lines (pastor info, etc.)
        if NOT_CHURCH_NAME.match(line) and not CHURCH_KEYWORDS.search(line):
            # Could be address or phone line for current entry
            if current:
                # Check for address+phone with dashes
                m = ADDR_WITH_PHONE.search(line)
                if m:
                    if not current.get("address"):
                        current["address"] = m.group(1).strip()
                    if not current.get("phone"):
                        current["phone"] = m.group(2).strip()
                else:
                    addr = extract_address_from_line(line)
                    if addr and not current.get("address"):
                        current["address"] = addr
                
                phone = extract_phone_from_line(line)
                if phone and not current.get("phone"):
                    current["phone"] = phone
            continue
        
        # Check if this line contains a church name keyword
        has_church_kw = bool(CHURCH_KEYWORDS.search(line))
        
        if has_church_kw:
            # Save previous entry
            if current and current.get("name"):
                entries.append(current)
            
            # Parse name/address/phone from this line
            name, addr, phone = split_name_addr_phone(line)
            
            current = {
                "name": name,
                "address": addr or "",
                "phone": phone or "",
                "city": city,
                "state": state,
                "denomination": denom,
            }
        elif current:
            # Continuation line for current entry
            m = ADDR_WITH_PHONE.search(line)
            if m:
                if not current.get("address"):
                    current["address"] = m.group(1).strip()
                if not current.get("phone"):
                    current["phone"] = m.group(2).strip()
            else:
                addr = extract_address_from_line(line)
                if addr and not current.get("address"):
                    current["address"] = addr
            
            phone = extract_phone_from_line(line)
            if phone and not current.get("phone"):
                current["phone"] = phone
    
    # Don't forget last entry
    if current and current.get("name"):
        entries.append(current)
    
    # Clean up and deduplicate
    seen_names = set()
    cleaned = []
    for e in entries:
        # Clean phone
        if e.get("phone"):
            e["phone"] = re.sub(r'\s+', ' ', e["phone"]).strip().strip('—').strip()
        
        # Clean name
        if e.get("name"):
            e["name"] = re.sub(r'\s+', ' ', e["name"]).strip()
            # Remove leading/trailing dashes and pipes
            e["name"] = e["name"].strip('—|').strip()
        
        # Skip very short names or obvious false positives
        name = e.get("name", "")
        if len(name) < 10 or name.upper() == "CHURCHES":
            continue
        if re.match(r'^\d+\s+(?:Av|St|Rd|Dr)', name):
            continue
        
        # Deduplicate by name
        name_key = name.lower().strip()
        if name_key not in seen_names:
            seen_names.add(name_key)
            cleaned.append(e)
    
    return cleaned


def extract_all_churches(items, limit=None):
    """Extract church listings from all downloaded OCR texts."""
    print(f"\n⛪ Extracting church listings from OCR texts...")
    
    all_churches = []
    processed = 0
    with_churches = 0
    total_entries = 0
    
    dirs_to_process = items[:limit] if limit else items
    
    for item in dirs_to_process:
        call_no = item.get("item", {}).get("call_number", [None])[0]
        if not call_no:
            continue
        
        ocr_path = OCR_DIR / f"{call_no}.txt"
        if not ocr_path.exists():
            continue
        
        processed += 1
        
        try:
            with open(ocr_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except:
            continue
        
        # Get location info
        # Location is typically ["United States -- Alabama -- Birmingham"]
        loc_list = item.get("item", {}).get("location", [])
        created = item.get("item", {}).get("created_published", [""])[0]
        
        state = ""
        city = ""
        
        if loc_list:
            # Parse "United States -- Alabama -- Birmingham" format
            parts = [p.strip() for p in loc_list[0].split("--")]
            # Remove "United States" / "U.S." prefix
            geo_parts = [p for p in parts if p.lower() not in ("united states", "usa", "u.s.", "")]
            if len(geo_parts) >= 2:
                state = geo_parts[-2]
                city = geo_parts[-1]
            elif len(geo_parts) == 1:
                city = geo_parts[0]
        
        # Fallback: extract state from created_published like "Alabama, 1961"
        if not state and created:
            m = re.match(r'([A-Za-z\s]+),?\s*\d{4}', created)
            if m:
                state = m.group(1).strip()
        
        date = item.get("date", "?")
        
        # Find ALL churches sections (by denomination)
        sections = find_churches_sections(text)
        if not sections:
            continue
        
        # Collect entries from all sections, deduplicating by name within this directory
        seen_this_dir = set()
        
        for section_text, denom in sections:
            entries = parse_church_entries(section_text, city, state, denom)
            
            for e in entries:
                name_key = (e.get("name", "") + "|" + e.get("address", "")).lower().strip().lstrip("|").strip()
                if name_key and name_key not in seen_this_dir:
                    seen_this_dir.add(name_key)
                    # Add date metadata
                    e["source_date"] = date
                    e["source_call_no"] = call_no
                    e["source_title"] = item.get("title", "")
                    all_churches.append(e)
                    total_entries += 1
        
        if seen_this_dir:
            with_churches += 1
        
        if processed % 50 == 0:
            print(f"  Processed: {processed} dirs | {with_churches} with churches | {total_entries} entries")
    
    print(f"\n✅ Done: {processed} processed, {with_churches} with churches, {total_entries} total church entries")
    
    # Modernize phone numbers
    if all_churches:
        modernized = modernize_phones_in_results(all_churches)
        phones_with = sum(1 for c in all_churches if c.get("phone"))
        modern_with = sum(1 for c in all_churches if c.get("phone_modern"))
        print(f"📞 Phone modernization: {modernized} converted | {phones_with} raw → {modern_with} modern")
    
    return all_churches


# ── Phase 4: Match to GRID ──────────────────────────────────────────────────
def match_to_grid(churches):
    """Match extracted church entries to existing GRID churches by phone."""
    print(f"\n🔗 Matching {len(churches)} entries to GRID...")
    
    conn = sqlite3.connect(str(CHURCHES_DB))
    conn.row_factory = sqlite3.Row
    
    # Load existing phones from church_contact_values (phones not in churches table)
    cursor = conn.execute("""
        SELECT cv.church_id, cv.value as phone, c.name, c.address, c.city, c.state
        FROM church_contact_values cv
        JOIN churches c ON cv.church_id = c.id
        WHERE cv.contact_type = 'phone' AND cv.value IS NOT NULL AND cv.value != ''
    """)
    # Index by last 7 digits (most stable part across formats)
    existing_by_last7 = {}
    for row in cursor.fetchall():
        phone = row["phone"]
        if phone:
            clean = re.sub(r'[^\d]', '', phone)
            if clean and len(clean) >= 7:
                last7 = clean[-7:]
                if last7 not in existing_by_last7:
                    existing_by_last7[last7] = []
                existing_by_last7[last7].append(dict(row))
    
    matched = 0
    new_phones = 0
    
    for church in churches:
        phone = church.get("phone_modern") or church.get("phone", "")
        if phone:
            clean = re.sub(r'[^\d]', '', phone)
            if clean and len(clean) >= 7:
                last7 = clean[-7:]
                
                if last7 in existing_by_last7:
                    candidates = existing_by_last7[last7]
                    area_code = church.get("area_code")
                    
                    # Prefer same area code if available
                    best = candidates[0]
                    if area_code:
                        for cand in candidates:
                            cand_clean = re.sub(r'[^\d]', '', cand["phone"])
                            if cand_clean.startswith(area_code):
                                best = cand
                                break
                    
                    church["grid_match_id"] = best["church_id"]
                    church["grid_match_name"] = best["name"]
                    church["grid_match_city"] = best["city"]
                    church["grid_match_state"] = best["state"]
                    matched += 1
                    continue
        
        if church.get("phone"):
            new_phones += 1
    
    conn.close()
    
    print(f"  📞 Phone-matched to GRID: {matched}")
    print(f"  📞 New phones (not in GRID): {new_phones}")
    print(f"  ❓ No phone: {len(churches) - matched - new_phones}")
    
    return churches


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="LOC Phone Directory Church Extractor")
    parser.add_argument("--inventory", action="store_true", help="Fetch/re-fetch inventory")
    parser.add_argument("--download", action="store_true", help="Download OCR text")
    parser.add_argument("--extract", action="store_true", help="Extract church listings")
    parser.add_argument("--match", action="store_true", help="Match to GRID database")
    parser.add_argument("--all", action="store_true", help="Run all phases")
    parser.add_argument("--limit", type=int, default=None, help="Limit directories to process")
    parser.add_argument("--force", action="store_true", help="Force re-download")
    parser.add_argument("--summary", action="store_true", help="Show inventory summary")
    
    args = parser.parse_args()
    
    if args.all:
        args.inventory = args.download = args.extract = args.match = True
    
    # ── Inventory ──
    if args.inventory or args.summary:
        items = fetch_inventory()
        if items:
            summarize_inventory(items)
    else:
        items = load_inventory()
        if items and args.summary:
            summarize_inventory(items)
    
    if not items:
        print("No inventory loaded. Run with --inventory first.")
        return
    
    # ── Download OCR ──
    if args.download:
        download_all_ocr(items[:args.limit] if args.limit else items)
    
    # ── Extract churches ──
    if args.extract:
        churches = extract_all_churches(items, limit=args.limit)
        
        # Save raw results
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = RESULTS_DIR / f"loc_churches_{ts}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(churches, f, indent=2, ensure_ascii=False)
        print(f"📁 Saved: {out_path} ({len(churches)} churches)")
        
        # ── Match to GRID ──
        if args.match:
            churches = match_to_grid(churches)
            match_path = RESULTS_DIR / f"loc_churches_matched_{ts}.json"
            with open(match_path, "w", encoding="utf-8") as f:
                json.dump(churches, f, indent=2, ensure_ascii=False)
            print(f"📁 Saved matched: {match_path}")


if __name__ == "__main__":
    main()
