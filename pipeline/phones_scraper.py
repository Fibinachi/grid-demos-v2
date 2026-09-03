"""
EC2 Church Scraper - Emails + Phone Numbers
============================================
Scrapes church websites for email addresses AND phone numbers.
Phase 1: 5,582 contacts with known websites.
Phase 2: 273K IRS churches (search by name then scrape).

Usage: python ec2_phones_scraper.py <chunk_id>
Example: python ec2_phones_scraper.py 0
"""

import csv, os, re, sys, time, json, threading
import urllib.request, urllib.error, socket
from concurrent.futures import ThreadPoolExecutor, as_completed

CHUNK_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 0
WORK_DIR = "/home/ubuntu"
INPUT_FILE = os.path.join(WORK_DIR, f"ec2_phones_chunk_{CHUNK_ID}.csv")
OUTPUT_FILE = os.path.join(WORK_DIR, f"scraped_chunk_{CHUNK_ID}.csv")

# Pages to check on each website
CONTACT_PATHS = [
    "/", "/contact", "/contact-us", "/about", "/about-us",
    "/staff", "/our-staff", "/leadership", "/our-leadership",
    "/clergy", "/pastor", "/connect", "/give", "/donate",
    "/visit", "/location", "/find-us", "/welcome",
]

from gw_filters import email as gw_email
from gw_filters import clean as gw_clean

TIMEOUT = 10
MAX_WORKERS = 20

stats_lock = threading.Lock()
all_results = []
seen_emails = set()
processed = 0
found_count = 0

def extract_emails(html):
    mailtos = re.findall(r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', html)
    plain = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
    all_emails = []
    for e in mailtos + plain:
        e = e.strip().lower()
        if e not in seen_emails:
            seen_emails.add(e)
            all_emails.append(e)
    return all_emails

def extract_phones(html):
    """Extract US phone numbers from HTML."""
    patterns = [
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\+\d{1,2}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\d{3}[-.\s]\d{3}[-.\s]\d{4}(?!\d)',
    ]
    phones = set()
    for p in patterns:
        matches = re.findall(p, html)
        for m in matches:
            cleaned = re.sub(r'[^\d]', '', m)
            if len(cleaned) == 10:
                formatted = f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"
                phones.add(formatted)
            elif len(cleaned) == 11 and cleaned[0] == '1':
                cleaned = cleaned[1:]
                formatted = f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"
                phones.add(formatted)
    return list(phones)

def score_email(email):
    """Score email via gw_filters.email.score() — returns 0-10 scale for backward compat."""
    result = gw_email.score(email)
    return int(result["score"] * 10)

def fetch_url(url, timeout=10):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html",
        "Accept-Language": "en-US",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            return (resp.status, html, None)
    except Exception as e:
        return (0, "", str(e))

def scrape_one(church_name, website, denomination, existing_phone, city_state):
    global processed, found_count
    site = website.strip()
    if not site.startswith("http"):
        site = "https://" + site
    domain = re.sub(r'https?://(www\.)?', '', site).split('/')[0]
    
    found_emails = {}
    found_phones = set()
    
    for path in CONTACT_PATHS:
        url = site.rstrip('/') + path
        status, html, err = fetch_url(url, TIMEOUT)
        
        if html:
            # Extract emails
            emails = extract_emails(html)
            for email in emails:
                edomain = email.split("@")[1]
                if edomain == domain or edomain in ("gmail.com","yahoo.com","hotmail.com","outlook.com","icloud.com","aol.com","live.com","att.net","sbcglobal.net"):
                    s = score_email(email)
                    if email not in found_emails or s > found_emails[email][0]:
                        found_emails[email] = (s, path)
            
            # Extract phones
            phones = extract_phones(html)
            for p in phones:
                found_phones.add(p)
    
    with stats_lock:
        processed += 1
        best_email = ""
        best_score = 0
        if found_emails:
            best = max(found_emails.items(), key=lambda x: x[1][0])
            best_email = best[0]
            found_count += 1
        
        # Keep existing phone if we have one and didn't find a new one
        best_phone = existing_phone if existing_phone else ""
        if found_phones:
            # Pick the first phone found as best (they're all formatted same)
            best_phone = list(found_phones)[0]
        
        all_results.append({
            "church_name": church_name[:80],
            "website": website,
            "denomination": denomination[:60],
            "city_state": city_state,
            "email": best_email,
            "phone": best_phone,
        })
        
        if processed % 100 == 0:
            total = 1860
            pct = processed / total * 100
            rate = processed / (time.time() - start_time) if 'start_time' in dir() else 0
            print(f"[C{CHUNK_ID}] {processed}/{total} ({pct:.0f}%) | Found: {found_count} emails | {len(found_phones)} phones | {rate:.1f}/s")

start_time = time.time()

def main():
    global processed, found_count, all_results, seen_emails, start_time
    
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
                scrape_one,
                t.get("church_name", ""),
                t.get("website", ""),
                t.get("denomination", ""),
                t.get("phone", ""),
                t.get("city_state", ""),
            )
            futures[fut] = t
        
        for f in as_completed(futures):
            pass
    
    elapsed = time.time() - start_time
    print(f"\n[Chunk {CHUNK_ID}] DONE in {elapsed:.0f}s")
    print(f"  Processed: {processed}")
    print(f"  Emails found: {found_count}")
    print(f"  Hit rate: {found_count/processed*100:.1f}%")
    print(f"  Rate: {processed/elapsed:.1f}/s")
    
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["church_name","website","denomination","city_state","email","phone"])
        w.writeheader()
        w.writerows(all_results)
    
    print(f"[Chunk {CHUNK_ID}] Saved {len(all_results)} to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
