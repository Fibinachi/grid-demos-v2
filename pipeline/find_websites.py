"""
Phase 1b+2: Church Website Finder
==================================
Finds church websites by:
  1. Domain guessing (common URL patterns) - instant
  2. DuckDuckGo search fallback - free, slow
  3. Scrapes found websites for emails + phones

Usage: python ec2_find_websites.py <chunk_id>
  chunk_id determines which CSV file to process

Expects: /home/ubuntu/find_chunk_{chunk_id}.csv
  Columns: church_name, city, state, street, zip, denomination
Saves to: /home/ubuntu/found_chunk_{chunk_id}.csv
"""

import csv, os, re, sys, time, json, socket, threading, subprocess
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

CHUNK_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 0
WORK_DIR = "/home/ubuntu"
INPUT_FILE = os.path.join(WORK_DIR, f"find_chunk_{CHUNK_ID}.csv")
OUTPUT_FILE = os.path.join(WORK_DIR, f"found_chunk_{CHUNK_ID}.csv")

TIMEOUT = 10
MAX_WORKERS = 8

# Google Knowledge Graph API key
KG_API_KEY = "AIzaSyBXQspPD9GFR6s7QKpl8W1mpgL9syPtZi4"
KG_CACHE = {}  # Avoid duplicate lookups

stats_lock = threading.Lock()
all_results = []
processed = 0
found_site = 0
found_email = 0

# Common church website patterns
def generate_domain_guesses(name, city, state):
    """Generate likely domain names for a church."""
    n = name.strip().upper()
    city_clean = city.strip().lower().replace(" ", "").replace(".", "").replace("'", "")
    state_clean = state.strip().lower()
    name_clean = re.sub(r'[^A-Z0-9 ]', '', n).strip()
    
    # Get significant words
    words = name_clean.split()
    stop_words = {'THE', 'OF', 'A', 'AN', 'AND', 'IN', 'AT'}
    sig_words = [w for w in words if w not in stop_words and len(w) > 1]
    
    if not sig_words:
        return []
    
    # Common abbreviations
    abbrevs = {
        'FIRST': 'f', 'BAPTIST': 'b', 'CHURCH': 'c', 'METHODIST': 'm',
        'LUTHERAN': 'l', 'PRESBYTERIAN': 'p', 'PENTECOSTAL': 'p',
        'CATHOLIC': 'c', 'EPISCOPAL': 'e', 'CHRISTIAN': 'c',
        'ASSEMBLIES': 'a', 'GOSPEL': 'g', 'CALVARY': 'c', 'CHAPEL': 'c',
        'NAZARENE': 'n', 'MISSIONARY': 'm', 'ALLIANCE': 'a',
        'INDEPENDENT': 'i', 'BIBLE': 'b', 'FELLOWSHIP': 'f',
    }
    
    guesses = set()
    
    # Pattern: FullNameCity.org (FirstBaptistSpringfield.org)
    full = '-'.join(w.lower() for w in sig_words[:4])
    if full:
        guesses.add(f"{full}.org")
        guesses.add(f"{full}.com")
        guesses.add(f"{full}.church")
        if city_clean:
            guesses.add(f"{full}{city_clean}.org")
            guesses.add(f"{full}{city_clean}.com")
    
    # Pattern: abbreviation + city (fbcspringfield.org)
    abbr = ''.join(abbrevs.get(w, w[0].lower()) for w in sig_words[:3])
    if abbr and len(abbr) <= 6:
        guesses.add(f"{abbr}{city_clean}.org")
        guesses.add(f"{abbr}{city_clean}.com")
    
    # Pattern: CityChurch.org (springfieldfirstbaptist.org)
    if city_clean and full:
        guesses.add(f"{city_clean}{full}.org")
        guesses.add(f"{city_clean}{full}.com")
    
    # Pattern: ChurchCityState.org
    if city_clean and state_clean:
        guesses.add(f"{full}.{city_clean}{state_clean}.org")
    
    return list(guesses)[:10]

def check_domain(domain):
    """Check if a domain resolves (DNS lookup or HTTP check)."""
    try:
        url = f"https://{domain}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            return (url, resp.status, resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        if e.code in (200, 301, 302):
            try:
                html = e.read().decode("utf-8", errors="replace")
                return (url, e.code, html)
            except:
                return (url, e.code, "")
        return None
    except Exception:
        return None

def search_duckduckgo(query):
    """Search DuckDuckGo for a query and return result URLs."""
    url = f"https://html.duckduckgo.com/html/?q={urllib.request.quote(query)}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        
        # Extract result links from DDG HTML
        results = []
        for m in re.finditer(r'class="result__url"[^>]*href="([^"]+)"', html):
            results.append(m.group(1))
        # Also try extracting from redirect URLs
        for m in re.finditer(r'uddg=([^"&]+)', html):
            results.append(urllib.request.unquote(m.group(1)))
        return results
    except Exception:
        return []

def kg_lookup(name, city, state):
    """Look up a church via Google Knowledge Graph API.
    Returns dict with website, description, and social links or None."""
    query = f"{name} {city} {state}"
    cache_key = query.strip().lower()
    
    if cache_key in KG_CACHE:
        return KG_CACHE[cache_key]
    
    url = f"https://kgsearch.googleapis.com/v1/entities:search?query={urllib.request.quote(query)}&key={KG_API_KEY}&limit=3"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        
        items = data.get("itemListElement", [])
        for item in items:
            entity = item.get("result", {})
            score = item.get("resultScore", 0)
            if score < 1:
                continue
            
            name_found = entity.get("name", "")
            # Must match the church name somewhat
            if not any(w.lower() in name_found.lower() for w in name.split()[:2] if len(w) > 3):
                continue
            
            result = {
                "name": name_found,
                "website": entity.get("url", ""),
                "description": entity.get("description", ""),
                "detail": entity.get("detailedDescription", {}).get("articleBody", ""),
                "sameAs": entity.get("sameAs", []),
                "score": score,
            }
            
            # Clean website URL
            web = result["website"]
            if web and not web.startswith("http"):
                web = "https://" + web
            result["website"] = web
            
            KG_CACHE[cache_key] = result
            return result
    except Exception:
        pass
    
    KG_CACHE[cache_key] = None
    return None

def extract_emails(html, domain):
    emails = []
    for m in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html):
        e = m.group().strip().lower()
        edomain = e.split("@")[1]
        if edomain == domain or edomain in ("gmail.com","yahoo.com","hotmail.com","outlook.com","icloud.com","aol.com","live.com","att.net"):
            emails.append(e)
    return emails

def extract_phones(html):
    phones = set()
    for m in re.finditer(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', html):
        cleaned = re.sub(r'[^\d]', '', m.group())
        if len(cleaned) == 10:
            phones.add(f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}")
    return list(phones)

def process_one(church_name, city, state, street, zipcode, denomination, ein):
    global processed, found_site, found_email
    
    website = ""
    email = ""
    phone = ""
    
    # STEP 0: Try Google Knowledge Graph first (verified data)
    kg_result = kg_lookup(church_name, city, state)
    if kg_result:
        website = kg_result.get("website", "")
        description = kg_result.get("description", "") or kg_result.get("detail", "")[:200]
        same_as = kg_result.get("sameAs", [])
        
        # Fetch the website to extract emails/phones
        if website:
            try:
                req = urllib.request.Request(website, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                    domain = re.sub(r'https?://(www\.)?', '', website).split('/')[0].split(':')[0]
                    emails = extract_emails(html, domain)
                    if emails:
                        email = emails[0]
                    phones = extract_phones(html)
                    if phones:
                        phone = phones[0]
            except:
                pass
    
    # STEP 1: Domain guessing (fallback if KG found nothing)
    if not website:
        guesses = generate_domain_guesses(church_name, city, state)
        for domain in guesses:
            result = check_domain(domain)
            if result:
                url, status, html = result
                website = url
                if html:
                    emails = extract_emails(html, re.sub(r'https?://', '', url).split('/')[0].split(':')[0])
                    if emails:
                        email = emails[0]
                    phones = extract_phones(html)
                    if phones:
                        phone = phones[0]
                break
    
    # STEP 2: DuckDuckGo search fallback
    if not website:
        query = f"{church_name} {city} {state} official website"
        results = search_duckduckgo(query)
        time.sleep(0.5)  # rate limit
        
        for result_url in results[:5]:
            skip = ['wikipedia', 'facebook', 'yelp', 'linkedin', 'instagram', 'twitter', 'yellowpages']
            if not any(s in result_url.lower() for s in skip):
                # Try to fetch the page
                try:
                    req = urllib.request.Request(result_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        html = resp.read().decode("utf-8", errors="replace")
                        website = result_url
                        domain = re.sub(r'https?://(www\.)?', '', result_url).split('/')[0].split(':')[0]
                        emails = extract_emails(html, domain)
                        if emails:
                            email = emails[0]
                        phones = extract_phones(html)
                        if phones:
                            phone = phones[0]
                        break
                except:
                    continue
    
    with stats_lock:
        processed += 1
        if website:
            found_site += 1
        if email:
            found_email += 1
        
        all_results.append({
            "church_name": church_name[:80],
            "website": website,
            "email": email,
            "phone": phone,
            "city": city,
            "state": state,
            "street": street,
            "zip": zipcode,
            "denomination": (denomination or "")[:60],
            "ein": ein,
        })
        
        # Save checkpoint every 100 records
        if len(all_results) % 100 == 0:
            ckpt = OUTPUT_FILE.replace('.csv', '_ckpt.csv')
            with open(ckpt, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["church_name","website","email","phone","city","state","street","zip","denomination","ein"])
                w.writeheader()
                w.writerows(all_results)
            # Push to orchestrator for real-time DB update
            try:
                subprocess.run(
                    ["scp", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                     "-i", "/home/ubuntu/.ssh/grantwizard-key.pem",
                     ckpt, "ec2-user@18.118.136.255:~/grantwizard/incoming/"],
                    capture_output=True, timeout=8
                )
            except:
                pass
        
        if processed % 100 == 0:
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            print(f"[C{CHUNK_ID}] {processed} done | Sites:{found_site} | Emails:{found_email} | {rate:.1f}/s | {int(elapsed)}s")

start_time = time.time()

def main():
    global processed, found_site, found_email, all_results, start_time
    
    targets = []
    with open(INPUT_FILE, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            targets.append(r)
    
    total = len(targets)
    print(f"[Chunk {CHUNK_ID}] Loaded {total} targets from {INPUT_FILE}")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for t in targets:
            fut = executor.submit(
                process_one,
                t.get("church_name", ""),
                t.get("city", ""),
                t.get("state", ""),
                t.get("street", ""),
                t.get("zip", ""),
                t.get("denomination", ""),
                t.get("ein", ""),
            )
            futures[fut] = t
        
        for f in as_completed(futures):
            pass
    
    elapsed = time.time() - start_time
    print(f"\n[Chunk {CHUNK_ID}] DONE in {elapsed:.0f}s")
    print(f"  Processed: {processed}")
    print(f"  Sites found: {found_site} ({found_site/processed*100:.1f}%)")
    print(f"  Emails found: {found_email}")
    print(f"  Rate: {processed/elapsed:.1f}/s")
    
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "church_name","website","email","phone",
            "city","state","street","zip","denomination","ein",
        ])
        w.writeheader()
        w.writerows(all_results)
    
    print(f"[Chunk {CHUNK_ID}] Saved {len(all_results)} to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
