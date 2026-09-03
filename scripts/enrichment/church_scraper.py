#!/usr/bin/env python3
"""
Universal Church+Staff Scraper — deploy to EC2
==============================================
For each church: generate domain → HTTP check → scrape page → extract staff → write to DB

Two modes:
  --csv INPUT         EC2 mode: reads churches from CSV, outputs results as CSV
  --db PATH           Local mode: reads/writes SQLite directly

Outputs all findings immediately — website, emails, phones, staff names.

Usage:
    # EC2 mode (no DB access)
    python3 church_scraper.py --csv churches_chunk.csv --output results.csv --workers 20

    # Local DB mode
    python3 church_scraper.py --db /path/to/churches.db --limit 1000 --workers 25

Designed for t2.micro (1GB RAM) — no Playwright, just HTTP + regex.
"""
import csv, html, json, os, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ── Domain guessing (same logic as batch_domain_finder) ──
STOP_WORDS = {'THE', 'OF', 'A', 'AN', 'AND', 'IN', 'AT'}
ABBREVS = {
    'FIRST':'f','BAPTIST':'b','CHURCH':'c','METHODIST':'m',
    'LUTHERAN':'l','PRESBYTERIAN':'p','PENTECOSTAL':'p',
    'CATHOLIC':'c','EPISCOPAL':'e','CHRISTIAN':'c',
    'ASSEMBLIES':'a','GOSPEL':'g','CALVARY':'c','CHAPEL':'c',
    'NAZARENE':'n','MISSIONARY':'m','ALLIANCE':'a',
    'INDEPENDENT':'i','BIBLE':'b','FELLOWSHIP':'f',
}

def generate_guesses(name, city, state):
    if not name: return []
    n = name.strip().upper()
    city_clean = (city or "").strip().lower().replace(" ","").replace(".","").replace("'","")
    name_clean = re.sub(r'[^A-Z0-9 ]','',n).strip()
    words = name_clean.split()
    sig_words = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    if not sig_words: return []
    guesses = set()
    full = '-'.join(w.lower() for w in sig_words[:4])
    if full:
        for tld in ['.org','.com','.church']:
            guesses.add(full+tld)
            if city_clean: guesses.add(full+city_clean+tld)
    abbr = ''.join(ABBREVS.get(w,w[0].lower()) for w in sig_words[:3])
    if abbr and len(abbr)<=6 and city_clean:
        guesses.add(abbr+city_clean+'.org'); guesses.add(abbr+city_clean+'.com')
    if city_clean and full:
        guesses.add(city_clean+full+'.org'); guesses.add(city_clean+full+'.com')
    return list(guesses)[:8]

# ── HTTP checks ──
def check_domain(domain):
    for proto in ['https','http']:
        try:
            url = f"{proto}://{domain}"
            req = urllib.request.Request(url, method='HEAD',
                headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            with urllib.request.urlopen(req, timeout=8) as r:
                return url, r.getcode()
        except urllib.error.HTTPError as e:
            if e.code in (200,301,302,403): return f"{proto}://{domain}", e.code
        except: pass
    return None, None

def scrape_page(url):
    """Download page HTML, extract all useful data."""
    result = {"title":"","emails":[],"phones":[],"staff":[],"social":[],"has_staff_page":False}
    try:
        req = urllib.request.Request(url,
            headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                     "Accept":"text/html"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read(500*1024)  # 500KB max
    except: return result
    
    text = raw.decode("utf-8","replace")
    
    # Title
    m = re.search(r'<title[^>]*>(.*?)</title>', text, re.IGNORECASE|re.DOTALL)
    if m: result["title"] = html.unescape(re.sub(r'<[^>]+>','',m.group(1))).strip()
    
    # Emails from mailto: links and text
    emails = set()
    for m in re.finditer(r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text):
        emails.add(m.group(1).lower())
    for m in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text):
        e = m.group(0).lower()
        if not any(s in e for s in ['png','jpg','css','.js','example']) and '.' in e.split('@')[1]:
            emails.add(e)
    result["emails"] = list(emails)[:10]
    
    # Phones
    phones = set()
    for m in re.finditer(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text):
        p = re.sub(r'[^\d]','',m.group(0))
        if len(p)==10: phones.add(p)
    result["phones"] = list(phones)[:5]
    
    # Staff names from page patterns
    staff = set()
    # Pattern: role: name or name - role
    staff_patterns = [
        r'(?:Pastor|Reverend|Rev\.?|Rector|Fr\.?|Father|Minister|Deacon|'
        r'Deaconess|Elder|Bishop|Canon|Vicar|Chaplain|Secretary|'
        r'Administrator|Director|Coordinator|Treasurer|Clerk|'
        r'Lead Pastor|Senior Pastor|Youth Pastor|Executive Pastor|'
        r'Worship Pastor|Children.s Pastor|Music Director|'
        r'Office Manager|Business Manager|Associate Pastor)'
        r'(?:\s*[:\-–]\s*|\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})'
    ]
    for pat in staff_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            # Extract the name (capture group)
            # The pattern might capture differently, let's normalize
            full = m.group(0).strip()
            # Find the role prefix and name
            for role_word in ['Pastor','Reverend','Rev.','Rector','Father','Minister',
                           'Deacon','Bishop','Secretary','Director','Coordinator',
                           'Lead Pastor','Senior Pastor','Youth Pastor','Executive Pastor',
                           'Worship Pastor','Music Director','Office Manager']:
                if role_word.lower() in full.lower():
                    parts = full.lower().split(role_word.lower(),1)
                    if len(parts)==2:
                        rest = parts[1].strip().lstrip(':').lstrip('-').lstrip('\u2013').lstrip('\u2014').strip()
                        name = rest
                        # Take just first name + last name (2-3 words)
                        name_parts = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', rest)
                        if name_parts:
                            name = name_parts[0].strip()
                        if name and len(name)>4:
                            staff.add((name.strip(), role_word))
        break  # Only need first pattern
    
    # Also look for /staff, /leadership, /about-us, /pastor links
    for m in re.finditer(r'href=[\'"]([^\'"]*(?:staff|leadership|about.?us|pastor|team|clergy|directory)[^\'"]*)[\'"]', text, re.IGNORECASE):
        href = m.group(1)
        if not href.startswith('http'):
            from urllib.parse import urljoin
            href = urljoin(url, href)
        result["has_staff_page"] = True
        result["staff_page_url"] = href
    
    result["staff"] = list(staff)[:15]
    return result

def scrape_church(cid, name, city, state):
    """Full pipeline: domain guess → check → scrape → extract staff."""
    result = {
        "id":cid,"name":name,"city":city,"state":state,
        "domain":"","url":"","title":"",
        "status":"not_found","confidence":0,
        "emails":"","phones":"","staff_names":"","staff_roles":"",
        "social":"","has_staff_page":0,"staff_page_url":"",
    }
    
    guesses = generate_guesses(name, city, state)
    if not guesses: return result
    
    # Check each guess
    for domain in guesses:
        url, status = check_domain(domain)
        if url:
            result["domain"] = domain
            result["url"] = url
            result["status"] = "live"
            result["confidence"] = 30
            
            # Scrape the page
            page = scrape_page(url)
            result["title"] = page["title"]
            
            # Title verification
            if page["title"]:
                cu = name.strip().upper()
                tu = page["title"].upper()
                if cu in tu and len(cu)>5:
                    result["confidence"] = 90
                else:
                    sig = [w for w in cu.split() if w not in STOP_WORDS and len(w)>2]
                    matches = sum(1 for w in sig if w in tu) if sig else 0
                    if sig:
                        ratio = matches/len(sig)
                        result["confidence"] = int(ratio*100) if ratio>=0.5 else 30
            
            # Extract data
            if page["emails"]:
                result["emails"] = "; ".join(page["emails"][:5])
            if page["phones"]:
                result["phones"] = "; ".join(page["phones"][:3])
            if page["staff"]:
                names = [s[0] for s in page["staff"]]
                roles = [s[1] for s in page["staff"]]
                result["staff_names"] = "; ".join(names[:8])
                result["staff_roles"] = "; ".join(roles[:8])
            if page.get("social"):
                result["social"] = "; ".join(page["social"][:5])
            if page.get("has_staff_page"):
                result["has_staff_page"] = 1
                result["staff_page_url"] = page.get("staff_page_url","")
            
            # If title verified high confidence, keep this result
            if result["confidence"] >= 60:
                break
            # Otherwise try next domain candidate
    
    return result


CSV_FIELDS = [
    "id","name","city","state",
    "domain","url","title",
    "status","confidence",
    "emails","phones",
    "staff_names","staff_roles",
    "social","has_staff_page","staff_page_url",
]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", help="Input CSV (id,name,city,state)")
    parser.add_argument("--output", default="scraper_results.csv")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--skip-existing", action="store_true", help="Skip churches that already have websites")
    parser.add_argument("--db", default="churches.db", help="SQLite DB path")
    args = parser.parse_args()
    
    workers = args.workers
    print(f"[{datetime.now()}] Starting scraper with {workers} workers...")
    
    # Load churches
    churches = []
    if args.csv:
        with open(args.csv,'r',encoding='utf-8') as f:
            for r in csv.DictReader(f):
                churches.append({
                    "id":r.get("id",r.get("church_id","")),
                    "name":r.get("name",""),
                    "city":r.get("city",""),
                    "state":r.get("state",""),
                })
    else:
        import sqlite3
        db = sqlite3.connect(args.db or "churches.db")
        where = ""
        if args.skip_existing:
            where = "WHERE (website IS NULL OR website = '')"
        q = f"SELECT id, name, city, state FROM churches {where} ORDER BY id"
        if args.limit: q += f" LIMIT {args.limit}"
        churches = [{"id":str(r[0]),"name":r[1],"city":r[2],"state":r[3]} for r in db.execute(q).fetchall()]
        db.close()
    
    print(f"Loaded {len(churches):,} churches")
    if not churches: return
    
    # Process
    start = time.time()
    results = []
    done = found = 0
    
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(scrape_church, c["id"],c["name"],c["city"],c["state"]):c for c in churches}
        for f in as_completed(futures):
            r = f.result()
            results.append(r)
            done += 1
            if r["status"] != "not_found":
                found += 1
            
            # Immediate write option: append to CSV periodically
            if done % 100 == 0:
                elapsed = time.time()-start
                rate = done/elapsed if elapsed>0 else 0
                print(f"  {done:,}/{len(churches):,} ({rate:.0f}/s) — found {found:,}")
                
                # Periodically flush to CSV
                if done % 1000 == 0:
                    with open(args.output,'w',newline='',encoding='utf-8') as f:
                        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore')
                        w.writeheader()
                        w.writerows(results)
                    print(f"    Flushed {len(results):,} results to {args.output}")
    
    elapsed = time.time()-start
    # Final write
    with open(args.output,'w',newline='',encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(results)
    
    print(f"\nDone! {done:,} churches in {elapsed:.0f}s")
    print(f"Found websites: {found:,}")
    churches_with_staff = sum(1 for r in results if r["staff_names"])
    print(f"Staff extracted: {churches_with_staff:,}")
    churches_with_phones = sum(1 for r in results if r["phones"])
    print(f"Phones found: {churches_with_phones:,}")
    churches_with_emails = sum(1 for r in results if r["emails"])
    print(f"Emails found: {churches_with_emails:,}")


if __name__ == "__main__":
    main()
