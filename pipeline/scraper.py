"""
EC2 Mega Church Email Scraper
==============================
Fast church website email scraper for EC2 instances.
Usage: python ec2_scraper.py <chunk_index>
Example: python ec2_scraper.py 0
"""

import csv, os, re, sys, time, random, json, threading
import urllib.request, urllib.error, socket
from concurrent.futures import ThreadPoolExecutor, as_completed

CHUNK_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 0
WORK_DIR = "/home/ubuntu"
CHUNK_FILE = os.path.join(WORK_DIR, f"ec2_chunk_{CHUNK_ID}.csv")
OUTPUT_FILE = os.path.join(WORK_DIR, f"emails_chunk_{CHUNK_ID}.csv")

CONTACT_PATHS = [
    "/", "/contact", "/contact-us", "/about", "/about-us",
    "/staff", "/our-staff", "/leadership", "/our-leadership",
    "/clergy", "/pastor", "/connect", "/give", "/donate",
]

from gw_filters import email as gw_email

TIMEOUT = 8
MAX_WORKERS = 20

stats_lock = threading.Lock()
all_results = []
seen_emails = set()
processed = 0
found_count = 0
error_count = 0

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

def score_email(email):
    """Score email via gw_filters.email.score() — returns 0-10 scale for backward compat."""
    result = gw_email.score(email)
    return int(result["score"] * 10)

def fetch_url(url, timeout=8):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html",
        "Accept-Language": "en-US",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            return (resp.status, html, None)
    except urllib.error.HTTPError as e:
        return (e.code, "", str(e))
    except Exception as e:
        return (0, "", str(e))

def scrape_one(church_name, website, target_group):
    global processed, found_count, error_count
    site = website.strip()
    if not site.startswith("http"):
        site = "https://" + site
    domain = re.sub(r'https?://(www\.)?', '', site).split('/')[0]
    
    found = {}
    for path in CONTACT_PATHS:
        url = site.rstrip('/') + path
        status, html, err = fetch_url(url, TIMEOUT)
        if html:
            emails = extract_emails(html)
            for email in emails:
                edomain = email.split("@")[1]
                if edomain == domain or edomain in ("gmail.com","yahoo.com","hotmail.com","outlook.com","icloud.com","aol.com","live.com"):
                    s = score_email(email)
                    if email not in found or s > found[email][0]:
                        found[email] = (s, path)
    
    with stats_lock:
        processed += 1
        if found:
            best = max(found.items(), key=lambda x: x[1][0])
            email, (score, path) = best
            found_count += 1
            all_results.append({
                "church_name": church_name[:80],
                "website": website,
                "email": email,
                "target_group": target_group,
            })
        else:
            error_count += 1
        
        if processed % 50 == 0:
            pct = processed / 694 * 100
            print(f"[Chunk {CHUNK_ID}] {processed}/694 ({pct:.0f}%) | Found: {found_count} | Errors: {error_count}")

def main():
    global processed, found_count, error_count, all_results, seen_emails
    
    targets = []
    with open(CHUNK_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            targets.append(r)
    
    print(f"[Chunk {CHUNK_ID}] Loaded {len(targets)} targets from {CHUNK_FILE}")
    start = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for t in targets:
            fut = executor.submit(scrape_one, t["church_name"], t["website"], t.get("target_group", ""))
            futures[fut] = t
            time.sleep(0.02)  # rate limit a bit
        
        for f in as_completed(futures):
            pass  # progress is tracked in scrape_one
    
    elapsed = time.time() - start
    print(f"\n[Chunk {CHUNK_ID}] Done in {elapsed:.0f}s")
    print(f"  Processed: {processed}")
    print(f"  Found: {found_count}")
    print(f"  Rate: {processed/elapsed:.1f}/s")
    
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["church_name","website","email","target_group"])
        w.writeheader()
        for r in all_results:
            w.writerow(r)
    
    print(f"[Chunk {CHUNK_ID}] Saved {len(all_results)} emails to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
