#!/usr/bin/env python3
"""
Episcopal Asset Map Scraper — Playwright-based
===============================================
Uses Playwright to extract all ~6,800 Episcopal churches from the Asset Map.
Scrapes paginated list, then detail pages for website/email/phone/rector.

Usage:
    OUTPUT_DIR=/home/ec2-user/data python3 episcopal_scraper.py
"""
import csv, json, os, re, sys, time
from datetime import datetime
from playwright.sync_api import sync_playwright

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/home/ec2-user/data/denom_scrape")
os.makedirs(OUTPUT_DIR, exist_ok=True)
BASE = "https://www.episcopalassetmap.org"


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def scrape():
    results = []
    seen_nids = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        # Step 1: Paginated list
        page_num = 0
        empty_pages = 0
        while empty_pages < 3:
            url = f"{BASE}/list?keywords=&type%5Bchurch%5D=church&page={page_num}"
            log(f"List page {page_num}...")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(5000)
            except Exception as e:
                log(f"  Timeout: {e}")
                empty_pages += 1
                page_num += 1
                continue

            nids = page.evaluate("""
                () => {
                    const spans = document.querySelectorAll('[class*="nid--"]');
                    return Array.from(spans).map(s => {
                        const match = s.className.match(/nid--(\\d+)/);
                        const name = s.textContent.trim();
                        return match ? { nid: parseInt(match[1]), name: name } : null;
                    }).filter(x => x !== null && x.name.length > 3);
                }
            """)

            if not nids or len(nids) == 0:
                empty_pages += 1
                log(f"  Empty ({empty_pages}/3)")
                page_num += 1
                continue

            empty_pages = 0
            for item in nids:
                if item['nid'] not in seen_nids:
                    seen_nids.add(item['nid'])
                    results.append({"url": f"{BASE}/node/{item['nid']}",
                                    "nid": item['nid'],
                                    "name_from_list": item['name']})

            log(f"  Page {page_num}: {len(nids)} churches (total {len(results)})")
            page_num += 1

        log(f"Found {len(results)} churches total")

        # Step 2: Detail pages
        for i, church in enumerate(results):
            if i % 50 == 0:
                log(f"Detail {i}/{len(results)}...")
            try:
                page.goto(church['url'], wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
                detail = page.evaluate("""() => {
                    const text = document.body.innerText;
                    const links = Array.from(document.querySelectorAll('a'));
                    const website = links.find(l => {
                        const h = l.href;
                        return h.startsWith('http') && !h.includes('episcopalassetmap')
                            && !h.includes('google.com') && !h.includes('facebook')
                            && !h.includes('twitter') && h.length < 200;
                    });
                    const email = links.find(l => l.href.startsWith('mailto:'));
                    const m1 = text.match(/Rector|Priest|Clergy|Vicar|Pastor[:\s]+([^\\n]+)/i);
                    const m2 = text.match(/Phone:\\s*([^\\n]+)/i);
                    const m3 = text.match(/URL:\\s*([^\\n]+)/i);
                    const m4 = text.match(/Address:\\s*([^\\n]+(?:\\n[^\\n]+)*?)(?=\\n\\w+:)/i);
                    const h1 = document.querySelector('h1');
                    return {
                        name: h1 ? h1.textContent.trim() : '',
                        website: website ? website.href : (m3 ? m3[1].trim() : ''),
                        email: email ? email.href.replace('mailto:', '') : '',
                        rector: m1 ? m1[1].trim() : '',
                        phone: m2 ? m2[1].trim() : '',
                        address: m4 ? m4[1].replace(/\\n/g, ', ').trim() : '',
                    };
                }""")
                church.update(detail)
            except Exception as e:
                log(f"  Error: {e}")
            time.sleep(0.3)

        browser.close()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"episcopal_full_{ts}.csv")
    fields = ["name", "name_from_list", "url", "website", "email", "rector", "phone", "address"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    log(f"Saved {len(results)} churches to {path}")
    return path


if __name__ == "__main__":
    scrape()
