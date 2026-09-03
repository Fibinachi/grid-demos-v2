#!/usr/bin/env python3
"""
SBC State Convention Scraper — URL-only (fast)
===============================================
Extracts church data from state convention sitemaps.
All states use URL slug name extraction (no detail page fetching).
AL and FL have good structured URL patterns.
MS and VA also use URL slug patterns.

Sources:
  - AL: alsbom.org (16 sitemaps, ~3,200) - /church-directory/name/
  - FL: flbaptist.org (14 sitemaps, ~2,674) - /locations/name/
  - MS: mbcb.org (2 sitemaps, ~1,999) - /church/name-2/
  - VA: sbcv.org (1 sitemap, 888) - /churches/name/

Usage:
    python scripts/scrapers/denominations/sbc_state_conventions.py
"""
import csv, os, re, sys
import urllib.request
from datetime import datetime
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent
OUT_DIR = PROJECT_DIR / "data" / "denom"
OUT_DIR.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def fetch(url):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(r, timeout=15) as f:
            return f.read().decode("utf-8", "replace")
    except:
        return None

def get_urls(sitemap_url):
    xml = fetch(sitemap_url)
    if not xml:
        return []
    locs = re.findall(r'<loc[^>]*>(.*?)</loc>', xml, re.DOTALL)
    clean = []
    for u in locs:
        u = u.strip()
        if u.startswith("<![CDATA[") and u.endswith("]]>"):
            u = u[9:-3]
        clean.append(u)
    return clean

def name_from_slug(url, pattern):
    m = re.search(pattern, url)
    if m:
        name = m.group(1).replace("-", " ").replace("_", " ").title()
        name = re.sub(r'\s*-\d+\s*$', '', name)
        return name
    return ""

def process_state(sitemaps, state, association, source, pattern, skip_pattern=None):
    results = []
    all_urls = []
    for su in sitemaps:
        urls = get_urls(su)
        log(f"  {su.split('/')[-1]}: {len(urls)} URLs")
        all_urls.extend(urls)
    
    for url in all_urls:
        if skip_pattern and re.search(skip_pattern, url):
            continue
        name = name_from_slug(url, pattern)
        results.append({
            "name": name, "website": url, "address": "", "city": "",
            "phone": "", "state": state,
            "denomination": "Southern Baptist Convention",
            "association": association, "source": source,
        })
    return results

def main():
    log("SBC State Convention Scraper")
    all_results = []
    
    # AL: /church-directory/church-name/
    log("\n--- Alabama ---")
    al = process_state(
        [f"https://alsbom.org/churches-directory-sitemap{i}.xml" for i in range(1, 17)],
        "AL", "Alabama Baptist Convention", "alsbom_sitemap",
        r'/church-directory/([^/]+)/?$',
        skip_pattern=r'/church-directory/?$')
    all_results.extend(al)
    
    # FL: /locations/church-name/
    log("\n--- Florida ---")
    fl = process_state(
        [f"https://flbaptist.org/locations-sitemap{i}.xml" for i in range(1, 15)],
        "FL", "Florida Baptist Convention", "flbaptist_sitemap",
        r'/locations/([^/]+)/?$',
        skip_pattern=r'/locations/?$')
    all_results.extend(fl)
    
    # MS: /church/church-name-2/
    log("\n--- Mississippi ---")
    ms = process_state(
        ["https://www.mbcb.org/church-sitemap.xml", "https://www.mbcb.org/church-sitemap2.xml"],
        "MS", "Mississippi Baptist Convention Board", "mbcb_sitemap",
        r'/church/([^/]+)/?$')
    all_results.extend(ms)
    
    # VA-SBCV: /churches/church-name/
    log("\n--- Virginia SBCV ---")
    va = process_state(
        ["https://sbcv.org/churches-sitemap.xml"],
        "VA", "Southern Baptist Conservatives of Virginia", "sbcv_sitemap",
        r'/churches/([^/]+)/?$',
        skip_pattern=r'/churches/?$')
    all_results.extend(va)
    
    # Save individual
    def save(arr, fn):
        p = OUT_DIR / fn
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["name","website","address","city","state","phone","denomination","association","source"])
            w.writeheader()
            for r in arr:
                w.writerow(r)
        log(f"Saved {len(arr)} -> {fn}")
    
    save(al, "sbc_alabama_churches.csv")
    save(fl, "sbc_florida_churches.csv")
    save(ms, "sbc_mississippi_churches.csv")
    save(va, "sbc_virginia_sbcv_churches.csv")
    
    log(f"\n{'='*60}")
    log(f"Total: {len(all_results):,} churches")
    for state, n in sorted(Counter(r["state"] for r in all_results).items()):
        log(f"  {state}: {n:,}")
    
    combined = OUT_DIR / "sbc_state_conventions_combined.csv"
    with open(combined, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name","website","address","city","state","phone","denomination","association","source"])
        w.writeheader()
        for r in all_results:
            w.writerow(r)
    log(f"Combined: {combined}")

if __name__ == "__main__":
    main()
