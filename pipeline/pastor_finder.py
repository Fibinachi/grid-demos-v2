"""
EC2 Pastor Email Finder
=======================
For 14,993 churches with known pastor names:
  1. Find website via domain guessing (fast)
  2. Guess pastor email from name + domain
  3. Mark guesses as 'guess' source for later enrichment

Usage: python ec2_pastor_finder.py
"""

import csv, os, re, sys, time, json, socket, threading
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

WORK_DIR = "/home/ubuntu"
INPUT_FILE = os.path.join(WORK_DIR, "pastor_targets.csv")
OUTPUT_FILE = os.path.join(WORK_DIR, "pastor_emails_found.csv")

TIMEOUT = 8
MAX_WORKERS = 30

stats_lock = threading.Lock()
results = []
processed = 0
found_website = 0
found_email = 0

def generate_domain_guesses(name, city, state):
    n = name.strip().upper()
    city_clean = city.strip().lower().replace(" ", "").replace(".", "").replace("'", "")
    words = re.sub(r'[^A-Z0-9 ]', '', n).strip().split()
    stop = {'THE','OF','A','AN','AND','IN','AT','TO','FOR'}
    sig = [w for w in words if w not in stop and len(w) > 1]
    
    if not sig:
        return []
    
    abbrevs = {
        'FIRST':'f','BAPTIST':'b','CHURCH':'c','METHODIST':'m',
        'LUTHERAN':'l','PRESBYTERIAN':'p','PENTECOSTAL':'p',
        'CATHOLIC':'c','EPISCOPAL':'e','CHRISTIAN':'c',
        'ASSEMBLIES':'a','GOSPEL':'g','CALVARY':'c','CHAPEL':'c',
        'NAZARENE':'n','MISSIONARY':'m','ALLIANCE':'a',
        'INDEPENDENT':'i','BIBLE':'b','FELLOWSHIP':'f',
        'MINISTRIES':'m','WORSHIP':'w','COMMUNITY':'c',
        'INTERNATIONAL':'i','UNITED':'u','CHRIST':'c',
    }
    
    guesses = set()
    full = '-'.join(w.lower() for w in sig[:4])
    if full:
        guesses.add(f"{full}.org")
        guesses.add(f"{full}.com")
        guesses.add(f"{full}.church")
        if city_clean:
            guesses.add(f"{full}{city_clean}.org")
            guesses.add(f"{full}{city_clean}.com")
    
    abbr = ''.join(abbrevs.get(w, w[0].lower()) for w in sig[:3])
    if abbr and len(abbr) <= 6 and city_clean:
        guesses.add(f"{abbr}{city_clean}.org")
        guesses.add(f"{abbr}{city_clean}.com")
    
    if city_clean and full:
        guesses.add(f"{city_clean}{full}.org")
        guesses.add(f"{city_clean}{full}.com")
    
    # Also try just church+city
    if city_clean and sig:
        first_word = sig[0].lower()
        guesses.add(f"{first_word}{city_clean}.org")
    
    return list(guesses)[:8]

def check_domain(domain):
    try:
        url = f"https://{domain}"
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return (url, resp.status, resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        if e.code in (200, 301, 302):
            try: return (url, e.code, e.read().decode("utf-8", errors="replace"))
            except: return (url, e.code, "")
        return None
    except:
        return None

def generate_email_guesses(pastor_ico, domain):
    """Generate likely pastor emails from name + domain."""
    ico = pastor_ico.upper().strip()
    for t in ['REV','REVEREND','PASTOR','BISHOP','FATHER','MINISTER','DR','DOCTOR','MOTHER','SISTER','BROTHER','MRS','MS','MR']:
        ico = ico.replace(t, '')
    ico = ico.strip().lstrip('.,- ').strip()
    parts = ico.split()
    
    first = parts[0].lower().strip('.,- ') if parts else ''
    last = ''
    for p in parts:
        p = p.strip('.,- ')
        if p and p.lower() not in ('jr','sr','ii','iii','iv','de','la','van','von') and len(p) > 1:
            last = p.lower()
    
    patterns = []
    if first and last:
        patterns.append(f"{first}.{last}@{domain}")
        patterns.append(f"{first}{last}@{domain}")
        patterns.append(f"{first[0]}{last}@{domain}")
    if last:
        patterns.append(f"{last}@{domain}")
        patterns.append(f"pastor.{last}@{domain}")
    if first:
        patterns.append(f"pastor{first}@{domain}")
    patterns.append(f"pastor@{domain}")
    
    return list(set(patterns))

def check_email_resolves(email):
    if not email or '@' not in email:
        return False
    domain = email.split('@')[1]
    try:
        socket.getaddrinfo(domain, 80)
        return True
    except:
        return False

def process_one(church_name, city, state, pastor_ico):
    global processed, found_website, found_email
    
    website = ""
    email = ""
    phone = ""
    email_source = ""
    
    # Step 1: Domain guessing
    guesses = generate_domain_guesses(church_name, city, state)
    domain = ""
    page_html = ""
    for guess in guesses:
        result = check_domain(guess)
        if result:
            url, status, html = result
            website = url
            domain = guess.split('/')[0].split(':')[0]
            page_html = html
            break
    
    # Step 2: Scrape found website for real emails
    if domain and page_html:
        found_website += 1
        
        # Extract all emails from homepage
        found_emails = set()
        for m in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_html):
            e = m.group().strip().lower()
            edomain = e.split("@")[1]
            if edomain == domain or edomain in ("gmail.com","yahoo.com","hotmail.com","outlook.com","icloud.com","aol.com","live.com","att.net"):
                found_emails.add(e)
        
        # Also scrape contact/about pages
        for path in ["/contact", "/about", "/staff", "/leadership", "/pastor", "/clergy"]:
            try:
                url = website.rstrip('/') + path
                req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                    for m in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html):
                        e = m.group().strip().lower()
                        edomain = e.split("@")[1]
                        if edomain == domain or edomain in ("gmail.com","yahoo.com","hotmail.com","outlook.com","icloud.com","aol.com","live.com","att.net"):
                            found_emails.add(e)
            except:
                pass
        
        # Pick best email: pastor-titled > named > first found
        if found_emails:
            pastor_match = [e for e in found_emails if any(w in e.split('@')[0] for w in ['pastor','rev','reverend','bishop','minister','rector','vicar','father','clergy'])]
            if pastor_match:
                email = pastor_match[0]
                email_source = "scraped_pastor"
            else:
                email = list(found_emails)[0]
                email_source = "scraped"
            found_email += 1
    
    # Step 3: If no real email found, try guessing from pastor name + domain
    if not email and domain:
        email_guesses = generate_email_guesses(pastor_ico, domain)
        for eg in email_guesses:
            if check_email_resolves(eg):
                email = eg
                email_source = "guess"
                found_email += 1
                break
    
    with stats_lock:
        processed += 1
        results.append({
            "church_name": church_name[:60],
            "website": website,
            "domain": domain,
            "email": email,
            "email_source": email_source,
            "city": city,
            "state": state,
            "pastor_ico": pastor_ico[:50],
        })
        
        # Save checkpoint every 200 records
        if len(results) % 200 == 0:
            ckpt = OUTPUT_FILE.replace('.csv', '_ckpt.csv')
            import csv as csvmod
            with open(ckpt, "w", newline="", encoding="utf-8") as f:
                w = csvmod.DictWriter(f, fieldnames=["church_name","website","domain","email","email_source","city","state","pastor_ico"])
                w.writeheader()
                w.writerows(results)
        
        if processed % 200 == 0:
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            pct = processed / 15000 * 100
            print(f"[{processed}/15000 ({pct:.0f}%)] Web:{found_website} Email:{found_email} | {rate:.1f}/s")

start_time = time.time()

def main():
    global start_time
    
    targets = []
    with open(INPUT_FILE, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            targets.append(r)
    
    total = len(targets)
    print(f"Loaded {total} targets from {INPUT_FILE}")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for t in targets:
            fut = executor.submit(
                process_one,
                t.get("church_name",""),
                t.get("city",""),
                t.get("state",""),
                t.get("pastor_ico",""),
            )
            futures[fut] = t
        
        for f in as_completed(futures):
            pass
    
    elapsed = time.time() - start_time
    print(f"\nDONE in {elapsed:.0f}s")
    print(f"Processed: {processed}")
    print(f"Websites found: {found_website} ({found_website/processed*100:.1f}%)")
    print(f"Emails guessed: {found_email} ({found_email/processed*100:.1f}%)")
    
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["church_name","website","domain","email","email_source","city","state","pastor_ico"])
        w.writeheader()
        w.writerows(results)
    
    print(f"Saved: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
