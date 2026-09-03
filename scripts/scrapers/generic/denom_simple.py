#!/usr/bin/env python3
"""
Denomination Directory Scrapers — Simple HTTP-based scrapers.
Targets: ELCA, LCMS, UMC, PCUSA, Catholic (via masstimes.org)

Run locally or on EC2. Outputs CSV to data/denom_scrape/
"""
import csv, json, os, re, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "data", "denom_scrape")
os.makedirs(OUTPUT_DIR, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
HEADERS = {"User-Agent": UA}
TIMEOUT = 15
PAGE_DELAY = 1.5

RESULTS = []

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def fetch(url, data=None):
    for attempt in range(3):
        try:
            r = urllib.request.Request(url, data=data, headers=HEADERS)
            with urllib.request.urlopen(r, timeout=TIMEOUT) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt == 2:
                log(f"  FAILED: {url[:80]} — {e}")
                return None
            time.sleep(2)

def save(name):
    if not RESULTS:
        log(f"  No results for {name}")
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"{name}_{ts}.csv")
    fields = ["source", "name", "address", "city", "state", "zip",
              "website", "email", "phone", "denomination", "diocese_synod",
              "lat", "lng", "source_url", "scraped_at"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(RESULTS)
    log(f"  Saved {len(RESULTS)} records -> {path}")


# ═══════════════════════════════════════════════════════════════════
# CATHOLIC — via masstimes.org (covers all US parishes)
# masstimes.org has a JSON API: https://www.masstimes.org/api/
# ═══════════════════════════════════════════════════════════════════

def scrape_catholic_masstimes():
    """
    Scrape Catholic parishes from masstimes.org.
    Has ~17,000 US parishes with names, addresses, lat/lng.
    Uses their search API by state.
    """
    log("✝️ Catholic parishes via masstimes.org...")
    
    states = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
              "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
              "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
              "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
              "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]
    
    total = 0
    for state in states:
        # masstimes.org uses a search endpoint
        url = f"https://www.masstimes.org/api/search?q={state}&type=church"
        html = fetch(url)
        if not html:
            continue
        
        # Extract church cards from the HTML
        # Each church is in a div with class containing church info
        churches = re.findall(
            r'<div[^>]*class="[^"]*church-card[^"]*"[^>]*>.*?'
            r'<h[23][^>]*>(.*?)</h[23]>.*?'
            r'(?:<p[^>]*>(.*?)</p>)?',
            html, re.DOTALL
        )
        
        if not churches:
            # Try alternate: find all church names in links
            churches = re.findall(
                r'<a[^>]*href="/church/(\d+)"[^>]*>(.*?)</a>',
                html, re.DOTALL
            )
            for cid, cname in churches:
                cname = re.sub(r'<[^>]+>', '', cname).strip()
                if cname:
                    RESULTS.append({
                        "source": "masstimes",
                        "name": cname,
                        "denomination": "Roman Catholic",
                        "source_url": f"https://www.masstimes.org/church/{cid}",
                        "scraped_at": datetime.now().isoformat(),
                    })
                    total += 1
        
        log(f"  {state}: {len(churches)} churches")
        time.sleep(PAGE_DELAY)
    
    log(f"  Total: {total} Catholic parishes")
    save("catholic_masstimes")


# ═══════════════════════════════════════════════════════════════════
# ELCA — elca.org/find-a-congregation
# Uses a search API at elca.org
# ═══════════════════════════════════════════════════════════════════

def scrape_elca():
    """Scrape ELCA congregations from their finder."""
    log("✝️ ELCA congregations...")
    
    # ELCA uses a locator at: https://elca.org/find-a-congregation
    # Data is loaded via AJAX. Try the search endpoint.
    states = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
              "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
              "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
              "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
              "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]
    
    total = 0
    for state in states:
        url = f"https://elca.org/find-a-congregation?state={state}"
        html = fetch(url)
        if not html:
            continue
        
        # Find congregation entries
        entries = re.findall(
            r'<div[^>]*class="[^"]*congregation[^"]*"[^>]*>.*?'
            r'<h[23][^>]*>(.*?)</h[23]>',
            html, re.DOTALL
        )
        
        if not entries:
            # Try: find church-like links
            entries = re.findall(
                r'<a[^>]*href="([^"]*)"[^>]*class="[^"]*congregation[^"]*"[^>]*>(.*?)</a>',
                html, re.DOTALL
            )
        
        for entry in entries:
            if isinstance(entry, tuple):
                href, name = entry
            else:
                href, name = "", entry
            name = re.sub(r'<[^>]+>', '', name).strip()
            if name and len(name) > 5:
                RESULTS.append({
                    "source": "elca",
                    "name": name,
                    "denomination": "ELCA",
                    "source_url": f"https://elca.org{href}" if href.startswith("/") else href,
                    "scraped_at": datetime.now().isoformat(),
                })
                total += 1
        
        log(f"  {state}: {len(entries) if isinstance(entries, list) else 0} congregations")
        time.sleep(PAGE_DELAY)
    
    log(f"  Total: {total} ELCA congregations")
    save("elca")


# ═══════════════════════════════════════════════════════════════════
# UMC — umc.org/find-a-church
# ═══════════════════════════════════════════════════════════════════

def scrape_umc():
    """Scrape United Methodist churches from their locator."""
    log("✝️ UMC churches...")
    
    states = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
              "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
              "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
              "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
              "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]
    
    total = 0
    for state in states:
        url = f"https://www.umc.org/find-a-church?state={state}"
        html = fetch(url)
        if not html:
            # Try alternate URL patterns
            url = f"https://www.umc.org/en/find-a-church/search?country=US&state={state}"
            html = fetch(url)
            if not html:
                continue
        
        # Find church entries - UMC typically uses structured data
        entries = re.findall(
            r'class="[^"]*church-name[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL
        )
        if not entries:
            entries = re.findall(
                r'<h[23][^>]*class="[^"]*"[^>]*>(.*?Church.*?)</h[23]>',
                html, re.DOTALL
            )
        
        for entry in entries:
            name = re.sub(r'<[^>]+>', '', entry).strip()
            if name and len(name) > 5:
                RESULTS.append({
                    "source": "umc",
                    "name": name,
                    "denomination": "United Methodist",
                    "scraped_at": datetime.now().isoformat(),
                })
                total += 1
        
        log(f"  {state}: {len(entries)} churches")
        time.sleep(PAGE_DELAY)
    
    log(f"  Total: {total} UMC churches")
    save("umc")


# ═══════════════════════════════════════════════════════════════════
# PCUSA — pcusa.org/congregations
# ═══════════════════════════════════════════════════════════════════

def scrape_pcusa():
    """Scrape PCUSA congregations."""
    log("✝️ PCUSA congregations...")
    
    states = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
              "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
              "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
              "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
              "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]
    
    total = 0
    for state in states:
        url = f"https://www.pcusa.org/congregations/?state={state}"
        html = fetch(url)
        if not html:
            continue
        
        entries = re.findall(
            r'class="[^"]*congregation-name[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL
        )
        if not entries:
            entries = re.findall(
                r'<a[^>]*href="/congregation/[^"]*"[^>]*>(.*?)</a>',
                html, re.DOTALL
            )
        
        for entry in entries:
            name = re.sub(r'<[^>]+>', '', entry).strip()
            if name and len(name) > 5:
                RESULTS.append({
                    "source": "pcusa",
                    "name": name,
                    "denomination": "PCUSA",
                    "scraped_at": datetime.now().isoformat(),
                })
                total += 1
        
        log(f"  {state}: {len(entries)} congregations")
        time.sleep(PAGE_DELAY)
    
    log(f"  Total: {total} PCUSA congregations")
    save("pcusa")


# ═══════════════════════════════════════════════════════════════════
# URJ — Reform Judaism (urj.org/congregations)
# ═══════════════════════════════════════════════════════════════════

def scrape_urj():
    """Scrape URJ (Reform) synagogue directory."""
    log("🕍 Reform Judaism (URJ) synagogues...")
    url = "https://urj.org/congregations"
    html = fetch(url)
    if not html:
        log("  Failed to fetch URJ directory")
        return
    
    entries = re.findall(
        r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        html, re.DOTALL
    )
    for href, name in entries:
        name = re.sub(r'<[^>]+>', '', name).strip()
        if name and ('temple' in name.lower() or 'synagogue' in name.lower() or 'congregation' in name.lower()):
            RESULTS.append({
                "source": "urj",
                "name": name,
                "denomination": "Reform Judaism",
                "source_url": href if href.startswith("http") else f"https://urj.org{href}",
                "scraped_at": datetime.now().isoformat(),
            })
    
    log(f"  Found {len(RESULTS)} URJ synagogues")
    save("urj")

# ═══════════════════════════════════════════════════════════════════
# USCJ — Conservative Judaism (uscj.org/congregations)
# ═══════════════════════════════════════════════════════════════════

def scrape_uscj():
    """Scrape USCJ (Conservative) synagogue directory."""
    log("🕍 Conservative Judaism (USCJ) synagogues...")
    url = "https://uscj.org/congregations"
    html = fetch(url)
    if not html:
        log("  Failed to fetch USCJ directory")
        return
    
    entries = re.findall(
        r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        html, re.DOTALL
    )
    for href, name in entries:
        name = re.sub(r'<[^>]+>', '', name).strip()
        if name and len(name) > 5:
            RESULTS.append({
                "source": "uscj",
                "name": name,
                "denomination": "Conservative Judaism",
                "source_url": href if href.startswith("http") else f"https://uscj.org{href}",
                "scraped_at": datetime.now().isoformat(),
            })
    
    log(f"  Found {len(RESULTS)} USCJ synagogues")
    save("uscj")

# ═══════════════════════════════════════════════════════════════════
# Chabad — chabad.org centers
# ═══════════════════════════════════════════════════════════════════

def scrape_chabad():
    """Scrape Chabad Lubavitch centers directory."""
    log("🕍 Chabad Lubavitch centers...")
    url = "https://www.chabad.org/centers/default_cdo/aid/118181/jewish/Chabad-Lubavitch-Centers.htm"
    html = fetch(url)
    if not html:
        log("  Failed to fetch Chabad directory")
        return
    
    entries = re.findall(
        r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        html, re.DOTALL
    )
    for href, name in entries:
        name = re.sub(r'<[^>]+>', '', name).strip()
        if name and ('chabad' in name.lower() or len(name) > 10):
            RESULTS.append({
                "source": "chabad",
                "name": name,
                "denomination": "Chabad Lubavitch",
                "source_url": href if href.startswith("http") else f"https://www.chabad.org{href}",
                "scraped_at": datetime.now().isoformat(),
            })
    
    log(f"  Found {len(RESULTS)} Chabad centers")
    save("chabad")

# ═══════════════════════════════════════════════════════════════════
# ISNA — Islamic Society of North America mosque directory
# ═══════════════════════════════════════════════════════════════════

def scrape_isna():
    """Scrape ISNA mosque directory."""
    log("🕌 ISNA mosques...")
    url = "https://isna.net/mosques/"
    html = fetch(url)
    if not html:
        log("  Failed to fetch ISNA directory")
        return
    
    entries = re.findall(
        r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        html, re.DOTALL
    )
    for href, name in entries:
        name = re.sub(r'<[^>]+>', '', name).strip()
        if name and ('mosque' in name.lower() or 'masjid' in name.lower() or 'islamic' in name.lower()):
            RESULTS.append({
                "source": "isna",
                "name": name,
                "denomination": "Muslim (ISNA)",
                "source_url": href if href.startswith("http") else f"https://isna.net{href}",
                "scraped_at": datetime.now().isoformat(),
            })
    
    log(f"  Found {len(RESULTS)} ISNA mosques")
    save("isna")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

SOURCES = {
    "catholic": "Catholic parishes via masstimes.org",
    "elca": "ELCA congregations",
    "umc": "United Methodist churches",
    "pcusa": "PCUSA congregations",
    "urj": "Reform Judaism (URJ) synagogues",
    "uscj": "Conservative Judaism synagogues",
    "chabad": "Chabad Lubavitch centers",
    "isna": "ISNA mosques",
    "all": "Run all sources",
}

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Denomination Directory Scrapers")
    parser.add_argument("source", nargs="?", default="", help="Source to scrape")
    parser.add_argument("--list", action="store_true", help="List sources")
    args = parser.parse_args()
    
    if args.list:
        print("Available sources:")
        for k, v in SOURCES.items():
            print(f"  {k:15s} {v}")
        return
    
    targets = []
    if args.source == "all":
        targets = ["catholic", "elca", "umc", "pcusa", "urj", "uscj", "chabad", "isna"]
    elif args.source in SOURCES:
        targets = [args.source]
    else:
        print(f"Use --list or one of: {', '.join(SOURCES.keys())}")
        return
    
    FUNCS = {
        "catholic": scrape_catholic_masstimes,
        "elca": scrape_elca,
        "umc": scrape_umc,
        "pcusa": scrape_pcusa,
        "urj": scrape_urj,
        "uscj": scrape_uscj,
        "chabad": scrape_chabad,
        "isna": scrape_isna,
    }
    
    for key in targets:
        log(f"\n{'='*60}")
        log(f"Scraping: {SOURCES[key]}")
        log(f"{'='*60}")
        try:
            FUNCS[key]()
        except Exception as e:
            log(f"  ERROR: {e}")
    
    log("\nDone!")

if __name__ == "__main__":
    main()
