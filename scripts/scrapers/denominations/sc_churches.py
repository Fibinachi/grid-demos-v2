"""
South Carolina Church Finder
Fetches usachurches.org pages to identify SC churches,
then scrapes their websites for emails.
"""
import csv, os, re, time, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(SCRIPT_DIR, "sc_church_emails.csv")
CONTACTS = os.path.join(SCRIPT_DIR, "church_contacts.csv")
MAX_WORKERS = 30

def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))
    sys.stdout.flush()

def fetch(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except:
        return None

def check_state(page_url):
    html = fetch(page_url)
    if html:
        m = re.search(r',\s*([A-Z]{2})\s+\d{5}', html)
        if m:
            return m.group(1)
    return None

def scrape_email(website):
    if not website:
        return ""
    for path in ["", "/contact", "/about", "/staff"]:
        url = website.rstrip("/") + path
        html = fetch(url)
        if html:
            for m in re.finditer(r'mailto:([^"\'>\s]+)', html):
                e = m.group(1).lower()
                if "@" in e and not any(x in e for x in [".png", ".jpg", "noreply"]):
                    return e
            domain = website.replace("https://","").replace("http://","").split("/")[0].replace("www.","")
            for m in re.finditer(r"[\w.+-]+@" + re.escape(domain), html, re.IGNORECASE):
                e = m.group(0).lower()
                if not any(x in e for x in [".png", ".jpg"]):
                    return e
        time.sleep(0.2)
    return ""

def main():
    log("South Carolina Church Finder")
    rows = list(csv.DictReader(open(CONTACTS, encoding="utf-8-sig")))
    log("Total: %d churches" % len(rows))
    
    log("Phase 1: Identifying SC churches...")
    sc_churches = []
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(check_state, r.get("page_url","").strip()): r for r in rows if r.get("page_url")}
        for i, future in enumerate(as_completed(futures)):
            r = futures[future]
            state = future.result()
            if state == "SC":
                sc_churches.append(r)
            if (i + 1) % 500 == 0:
                log("  Checked %d/%d, found %d SC" % (i+1, len(futures), len(sc_churches)))
    
    log("Found %d SC churches" % len(sc_churches))
    
    log("Phase 2: Scraping emails...")
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(scrape_email, r.get("website","").strip()): r for r in sc_churches}
        for i, future in enumerate(as_completed(futures)):
            r = futures[future]
            email = future.result()
            results.append({"church_name": r.get("church_name",""), "website": r.get("website",""), "email": email})
            if (i + 1) % 50 == 0:
                found = sum(1 for x in results if x["email"])
                log("  %d/%d, %d found" % (i+1, len(sc_churches), found))
                save_results(results)
    
    save_results(results)
    found = sum(1 for x in results if x["email"])
    log("Done! %d SC churches, %d with emails" % (len(sc_churches), found))

def save_results(results):
    if not results:
        return
    keys = ["church_name", "website", "email"]
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in results:
            w.writerow(r)

if __name__ == "__main__":
    main()
