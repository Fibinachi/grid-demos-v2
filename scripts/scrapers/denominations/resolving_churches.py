#!/usr/bin/env python3
"""Fast scraper for resolving domains - incremental writes, 5s timeout."""
import csv, os, re, urllib.request, urllib.error, ssl
from concurrent.futures import ThreadPoolExecutor, as_completed

base = os.path.dirname(os.path.abspath(__file__))
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

GENERIC = ['info@','contact@','hello@','admin@','webmaster@','support@',
    'mail@','office@','email@','inquiries@','ask@','media@','press@',
    'donate@','jobs@','hr@','careers@','volunteer@','noreply@','no-reply@',
    'do-not-reply@','bounce@','spam@','feedback@','newsletter@','subscribe@',
    'orders@','sales@','billing@','register@','membership@']

PATHS = ['/team','/staff','/about','/about-us','/contact','/contact-us',
    '/board','/board-of-directors','/people','/our-team','/our-staff',
    '/leadership','/grantmaking','/grants','/who-we-are','/']

with open(os.path.join(base, 'staff_scrape_resolving.csv')) as f:
    rows = list(csv.DictReader(f))

print(f"Scraping {len(rows)} resolving domains...", flush=True)
out_path = os.path.join(base, 'staff_real_contacts.csv')

def scrape(ein, name, domain):
    emails = set()
    for base_url in [f"https://www.{domain}", f"https://{domain}"]:
        for path in PATHS:
            try:
                req = urllib.request.Request(base_url+path, headers={'User-Agent':'Mozilla/5.0'})
                resp = urllib.request.urlopen(req, timeout=5, context=ctx)
                html = resp.read().decode('utf-8', errors='replace')
                for m in re.finditer(r'[\w.+-]+@[\w-]+\.\w+', html):
                    e = m.group().lower().strip()
                    lp, dom = e.split('@')
                    if any(e.startswith(p) for p in GENERIC): continue
                    if any(x in dom for x in ['gmail.com','yahoo.com','hotmail.com','outlook.com']): continue
                    if len(lp) < 2: continue
                    emails.add(e)
            except: pass
    return ein, name, domain, list(emails)

fc = 0
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['EIN','NAME','DOMAIN','STAFF_EMAILS'])
    with ThreadPoolExecutor(max_workers=30) as ex:
        futs = {ex.submit(scrape, r['EIN'], r['NAME'], r['DOMAIN']): r for r in rows}
        done = 0
        for fut in as_completed(futs):
            ein, name, domain, emails = fut.result()
            w.writerow([ein, name, domain, '; '.join(emails[:5])])
            f.flush()
            done += 1
            if emails: fc += 1
            if done % 10 == 0:
                print(f"  {done}/{len(rows)} (found: {fc})", flush=True)

print(f"\nDone! {fc}/{len(rows)} with emails -> {out_path}", flush=True)
