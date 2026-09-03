"""
Scrape COGIC and Historically Black Church Websites for Emails
==============================================================
Targets 232 churches from church_contacts.csv that belong to COGIC,
AME, AME Zion, CME, National Baptist, Progressive Baptist, and
Full Gospel Baptist — all with websites but no emails.

Usage:
  python scrape_black_churches.py [--workers 12] [--output cogic_emails.csv]

Run from: E:/grid
"""

import csv, os, re, sys, time, random, json, threading
import urllib.request, urllib.error, socket
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

d = r"E:\grid"

CONTACT_PATHS = [
    "/", "/contact", "/contact-us", "/about", "/about-us",
    "/about/contact", "/staff", "/our-staff", "/leadership",
    "/our-leadership", "/about/staff", "/clergy", "/pastor",
    "/about/clergy", "/connect", "/give", "/giving",
    "/donate", "/support", "/missions", "/outreach",
    "/ministries", "/welcome", "/new-here",
]

from gw_filters import email as gw_email

TIMEOUT = 10
MAX_WORKERS = 10

stats_lock = threading.Lock()
results = []
seen_emails = set()

def extract_emails(html):
    """Extract all email addresses from HTML."""
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
    """Fetch a URL and return (status, html, error)."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.5",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            return (resp.status, html, None)
    except urllib.error.HTTPError as e:
        return (e.code, "", str(e))
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
        return (0, "", str(e))

def scrape_website(church_name, website):
    """Scrape a single church website for email addresses."""
    if not website:
        return
    
    site = website.strip().lower()
    if not site.startswith("http"):
        site = "https://" + site
    
    domain = re.sub(r'https?://(www\.)?', '', site).split('/')[0]
    found_emails = {}
    
    for path in CONTACT_PATHS:
        url = site.rstrip('/') + path
        status, html, err = fetch_url(url, TIMEOUT)
        
        if html:
            emails = extract_emails(html)
            for email in emails:
                # Filter: only @domain or common providers
                email_domain = email.split("@")[1]
                if email_domain == domain or email_domain in (
                    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
                    "icloud.com", "aol.com", "live.com", "msn.com",
                ):
                    score = score_email(email)
                    if email not in found_emails or score > found_emails[email][0]:
                        found_emails[email] = (score, path)
        
        # Small delay between pages
        time.sleep(random.uniform(0.1, 0.3))
    
    if found_emails:
        best = max(found_emails.items(), key=lambda x: x[1][0])
        email, (score, path) = best
        with stats_lock:
            results.append({
                "church_name": church_name[:80],
                "website": website,
                "email": email,
                "score": score,
                "path": path,
            })
        return True
    return False

def main():
    global results, seen_emails
    
    # Load contacts
    contacts = list(csv.DictReader(open(os.path.join(d, "church_contacts.csv"), encoding="utf-8-sig")))
    
    # Filter target churches
    TARGET_DENOMS = [
        "church of god in christ", "cogic",
        "african methodist episcopal", "ame ",
        "ame zion", "amez",
        "christian methodist episcopal", "cme",
        "national baptist convention", "progressive national baptist",
        "full gospel baptist", "national baptist of america",
    ]
    
    targets = []
    for r in contacts:
        denom = (r.get("denomination", "") or "").lower()
        name = (r.get("church_name", "") or "").lower()
        website = (r.get("website", "") or "").strip()
        
        if any(k in denom for k in TARGET_DENOMS) and website:
            targets.append({
                "church_name": r.get("church_name", ""),
                "website": website,
                "denomination": r.get("denomination", ""),
            })
    
    print(f"Targeting {len(targets)} churches with websites...")
    
    # Denomination breakdown
    from collections import Counter
    denom_counts = Counter(t["denomination"] for t in targets)
    print("\nTarget breakdown:")
    for k, v in denom_counts.most_common():
        print(f"  {k[:50]}: {v}")
    
    # Scrape
    batch_size = max(1, len(targets) // 20)
    found = 0
    failed_web = 0
    failed_timeout = 0
    
    start = time.time()
    completed = 0
    
    for i in range(0, len(targets), batch_size):
        batch = targets[i:i+batch_size]
        batch_done = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {}
            for t in batch:
                futures[executor.submit(scrape_website, t["church_name"], t["website"])] = t
            
            for f in as_completed(futures):
                batch_done += 1
                completed += 1
                if f.result():
                    found += 1
            
            # Progress every batch
            elapsed = time.time() - start
            rate = completed / elapsed if elapsed > 0 else 0
            print(f"\rProgress: {completed}/{len(targets)} | Found: {found} | Rate: {rate:.1f}/s | Elapsed: {int(elapsed)}s", end="")
    
    elapsed = time.time() - start
    print(f"\n\nDone in {elapsed:.0f}s. Found {found} emails from {len(targets)} targets.")
    
    # Save results
    output = os.path.join(d, "cogic_emails.csv")
    with open(output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["church_name","website","email","score","path"])
        w.writeheader()
        for r in results:
            w.writerow(r)
    
    print(f"Saved to: {output}")
    
    # Also save combine-all list
    all_pent = os.path.join(d, "send_list_black_churches.csv")
    with open(all_pent, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["email","church_name","denomination"])
        w.writeheader()
        for r in results:
            denom = ""
            for t in targets:
                if t["website"] == r["website"]:
                    denom = t["denomination"]
                    break
            w.writerow({"email": r["email"], "church_name": r["church_name"], "denomination": denom})
    
    print(f"Send list saved to: {all_pent}")

if __name__ == "__main__":
    main()
