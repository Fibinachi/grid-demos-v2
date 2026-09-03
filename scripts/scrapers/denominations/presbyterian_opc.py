"""Scrape OPC church directory by iterating through all states via POST."""
import csv, json, os, re, sqlite3, sys, time, urllib.request, urllib.parse
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    db_path = os.path.join(PROJECT_DIR, "churches.db")
    if os.path.exists(db_path) and os.path.getsize(db_path) > 1024:
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
OUT_DIR = os.path.join(PROJECT_DIR, "data", "denom")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_CSV = os.path.join(OUT_DIR, "opc_churches.csv")

DENOM = "Orthodox Presbyterian Church"
SOURCE = "opc_scrape"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# All US states that might have OPC churches
STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
]

LOCATOR_URL = "https://www.opc.org/locator.html"


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def extract_addpointq_calls(html):
    """Extract AddPointQ calls from HTML by finding the function call and splitting args properly."""
    results = []
    idx = 0
    while True:
        start = html.find("AddPointQ(", idx)
        if start == -1:
            break
        
        # Find the matching closing paren
        depth = 0
        in_single = False
        in_double = False
        i = start + len("AddPointQ(")
        
        while i < len(html):
            ch = html[i]
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif ch == '(' and not in_single and not in_double:
                depth += 1
            elif ch == ')' and not in_single and not in_double:
                if depth == 0:
                    # Found the end
                    call = html[start:i+1]
                    results.append(call)
                    idx = i + 1
                    break
                depth -= 1
            i += 1
        else:
            idx = start + 1
    
    return results


def parse_addpointq_args(call):
    """Parse AddPointQ('lat','lng','addr_suffix','<h5>...</h5>','letter','color','City, State','KEY') into list of 8 args."""
    # Remove 'AddPointQ(' prefix and trailing ')'
    inner = call[len("AddPointQ("):-1]
    
    args = []
    current = ""
    in_single = False
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "'":
            in_single = not in_single
            current += ch
        elif ch == ',' and not in_single:
            args.append(current.strip())
            current = ""
        else:
            current += ch
        i += 1
    if current.strip():
        args.append(current.strip())
    
    return args


def fetch_churches_for_state(state):
    """POST to locator for a state and extract church data from AddPointQ calls."""
    data = urllib.parse.urlencode({
        'search_go': 'Y',
        'state': state,
        'search': 'Search'
    }).encode()
    
    req = urllib.request.Request(LOCATOR_URL, data=data, headers={
        'User-Agent': UA,
    })
    
    try:
        with urllib.request.urlopen(req, timeout=20) as f:
            html = f.read().decode()
    except Exception as e:
        log(f"  ERROR fetching {state}: {e}")
        return []
    
    # Extract AddPointQ calls using proper balanced parser
    calls = extract_addpointq_calls(html)
    results = []
    
    for call in calls:
        try:
            parts = parse_addpointq_args(call)
            if len(parts) < 8:
                continue
            
            lat = parts[0].strip("'")
            lng = parts[1].strip("'")
            html_content = parts[3].strip("'")
            
            # Extract church name from <h5>Name</h5>
            name_match = re.search(r'<h5>([^<]+)</h5>', html_content)
            name = name_match.group(1).strip() if name_match else ""
            
            # Extract address from <p class="ibfix">...</p>
            # Note: HTML may use escaped quotes (\") inside JS strings or regular quotes
            addr_match = re.search(r'<p[^>]*class="?\\?"?ibfix\\?"?[^>]*>(.*?)</p>', html_content)
            address = ""
            city = ""
            state_val = state
            zip_code = ""
            if addr_match:
                addr_text = addr_match.group(1)
                addr_text = re.sub(r'<br\s*/>', ' ', addr_text)
                addr_text = addr_text.strip()
                # Skip if this is the Contact or Meeting Info section
                if addr_text and not addr_text.startswith('Phone:') and not addr_text.startswith('Services:'):
                    address = addr_text
                
                # Try to extract city/state/zip from the address
                lines = addr_text.split('  ')
                if len(lines) >= 2 and not addr_text.startswith('Phone:') and not addr_text.startswith('Services:'):
                    # The city state line is usually after a double space or from city line
                    city_line = lines[-1].strip()
                    cm = re.match(r'(.+?)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)?', city_line)
                    if cm:
                        city = cm.group(1).strip()
                        state_val = cm.group(2)
                        zip_code = cm.group(3) or ""
            
            # Also try from parts[6] which has "City, State" format
            city_state = parts[6].strip("'") if len(parts) > 6 else ""
            if city_state and ',' in city_state:
                city_parts = city_state.split(',', 1)
                if not city:
                    city = city_parts[0].strip()
                state_val = city_parts[1].strip()[:2].upper()
            
            # Extract phone, email, website from remaining HTML
            phone = ""
            email = ""
            website = ""
            
            phone_match = re.search(r'Phone:\s*([^<]+)', html_content)
            if phone_match:
                phone = phone_match.group(1).strip()
            
            email_match = re.search(r'Email:\s*([^<]+)', html_content)
            if email_match:
                email_text = email_match.group(1).strip()
                email = decode_email(email_text)
            
            web_match = re.search(r'Website:\s*<a[^>]*href=\\"([^"]+)\\"', html_content)
            if web_match:
                website = web_match.group(1).strip()
            
            # Extract meeting info
            services = ""
            svc_match = re.search(r'Services:\s*([^<]+)', html_content)
            if svc_match:
                services = svc_match.group(1).strip()
            
            if name:
                results.append({
                    "name": name.strip().upper(),
                    "address": address,
                    "city": city,
                    "state": state_val,
                    "zip": zip_code,
                    "phone": phone,
                    "email": email,
                    "website": website,
                    "services": services,
                    "lat": lat,
                    "lng": lng,
                    "source_state": state,
                })
        except Exception as e:
            log(f"  Error parsing call: {e}")
            continue
    
    return results


def decode_email(encoded):
    """Decode HTML entity encoded email or obfuscated email."""
    # Check for HTML entity encoding like &#111;&#112;&#099;
    if '&#' in encoded:
        try:
            decoded = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), encoded)
            return decoded
        except:
            pass
    return encoded.strip()


def do_import(results):
    """Import OPC church data into the database."""
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    matched = 0
    inserted = 0
    for r in results:
        name = r.get("name", "").strip()
        city = r.get("city", "").strip().upper()
        state = r.get("state", "").strip().upper()
        
        if not name or not state:
            log(f"  SKIP (no name/state): {r.get('name','?')}")
            continue
        
        row = None
        for sql, params in [
            ("SELECT id, denomination, website FROM churches WHERE UPPER(name)=? AND state=? LIMIT 1", (name, state)),
            ("SELECT id, denomination, website FROM churches WHERE UPPER(name)=? AND city=? AND state=? LIMIT 1", (name, city, state)),
        ]:
            cur.execute(sql, params)
            row = cur.fetchone()
            if row:
                break
        if row:
            matched += 1
            cid, existing_denom, existing_web = row
            updates = []
            uparams = []
            if not existing_denom:
                updates.append("denomination=?")
                uparams.append(DENOM)
            if r.get("website") and not existing_web:
                updates.append("website=?")
                uparams.append(r["website"])
            if r.get("phone"):
                cur.execute("SELECT phone FROM churches WHERE id=?", (cid,))
                ep = cur.fetchone()
                if ep and not ep[0]:
                    updates.append("phone=?")
                    uparams.append(r["phone"])
            if updates:
                uparams.append(cid)
                cur.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id=?", uparams)
        else:
            inserted += 1
            cur.execute("""
                INSERT OR IGNORE INTO churches 
                (name, city, state, address, zip, phone, email, website, denomination, source, lat, lng)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                name, city, state,
                r.get("address", ""),
                r.get("zip", ""),
                r.get("phone", ""),
                r.get("email", ""),
                r.get("website", ""),
                DENOM, SOURCE,
                r.get("lat", ""),
                r.get("lng", ""),
            ))
    
    db.commit()
    db.close()
    return matched, inserted


def main():
    dry_run = "--dry-run" in sys.argv
    
    all_results = []
    for state in STATES:
        log(f"Fetching {state}...")
        churches = fetch_churches_for_state(state)
        if churches:
            log(f"  {len(churches)} churches found")
            all_results.extend(churches)
        time.sleep(0.3)
    
    # Deduplicate by name+state
    seen = set()
    unique = []
    for r in all_results:
        key = (r["name"], r["state"], r.get("city", ""))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    
    log(f"\nTotal unique churches: {len(unique)}")
    
    # Save CSV
    fields = ["name", "address", "city", "state", "zip", "phone", "email", "website", "services", "lat", "lng"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(unique)
    log(f"Saved to {OUT_CSV}")
    
    # Summary
    with_phone = sum(1 for r in unique if r.get("phone"))
    with_email = sum(1 for r in unique if r.get("email"))
    with_web = sum(1 for r in unique if r.get("website"))
    with_addr = sum(1 for r in unique if r.get("address"))
    log(f"\nResults: {len(unique)} total, {with_addr} with address, {with_phone} with phone, {with_email} with email, {with_web} with website")
    
    if not dry_run and unique:
        matched, inserted = do_import(unique)
        log(f"\nImport: {matched} matched, {inserted} new records")
    
    # Clean up temp file
    try:
        os.remove(os.path.join(PROJECT_DIR, "_opc_result.html"))
    except:
        pass

if __name__ == "__main__":
    main()
