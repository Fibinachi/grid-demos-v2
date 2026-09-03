#!/usr/bin/env python3
"""
Facebook Church Page Scraper — EC2 Batch Runner
=================================================
Processes churches from a CSV input file in batches.
Designed to run on EC2 instances that don't have the local DB.

Usage:
    python facebook_scraper_ec2.py --csv churches.csv --batch 50 --batch-num 0
    python facebook_scraper_ec2.py --csv churches.csv --resume

Output: facebook_results.csv (appended)
"""
import csv, json, os, re, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime

OUT_DIR = os.path.expanduser("~/facebook_results")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_CSV = os.path.join(OUT_DIR, "facebook_results.csv")
CHECKPOINT = os.path.join(OUT_DIR, "checkpoint.json")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]
ua_idx = [0]

def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))

def fetch(url, timeout=12):
    ua = USER_AGENTS[ua_idx[0] % len(USER_AGENTS)]
    ua_idx[0] += 1
    try:
        r = urllib.request.Request(url, headers={
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return f.read().decode("utf-8", "replace")
    except:
        return None

def find_fb_on_website(website):
    if not website:
        return None
    html = fetch(website, timeout=8)
    if not html:
        return None
    for m in re.finditer(r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9.]+(?:/[a-zA-Z0-9.]+)?', html, re.I):
        url = m.group(0).rstrip("/")
        if any(k in url.lower() for k in ["share", "sharer", "plugins", "dialog", "like", "login"]):
            continue
        page_id = url.split("facebook.com/")[-1]
        if len(page_id) > 3 and page_id != "pages":
            return url
    return None

def google_search_fb(name, city, state):
    query = 'site:facebook.com "%s" "%s" "%s"' % (name[:40], city[:20], state)
    html = fetch("https://www.google.com/search?q=" + urllib.parse.quote(query), timeout=10)
    if not html:
        return None
    for m in re.finditer(r'https?://(?:www\.|m\.)?facebook\.com/[a-zA-Z0-9.]+(?:/[a-zA-Z0-9.]+)?', html, re.I):
        url = m.group(0).rstrip("/")
        if any(k in url.lower() for k in ["share", "sharer", "plugins", "dialog", "like", "login"]):
            continue
        page_id = url.split("facebook.com/")[-1]
        if len(page_id) > 3 and page_id != "pages":
            return url
    return None

def scrape_fb_page(page_url):
    result = {"page_name": "", "category": "", "phone": "", "email": "", "website": "",
              "address": "", "city": "", "state": "", "zip": "", "about_text": "", "follower_count": ""}
    if not page_url:
        return result
    for try_url in [page_url.replace("www.", "m."), page_url, page_url + "/about"]:
        html = fetch(try_url, timeout=15)
        if not html:
            continue
        m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
        if m:
            result["page_name"] = re.sub(r'\s*[|-]\s*Facebook\s*$', '', m.group(1).strip(), flags=re.I)
        for pat in [r'"category"[^:]*:\s*"([^"]+)"', r'class="[^"]*category[^"]*"[^>]*>([^<]+)<']:
            m2 = re.search(pat, html, re.I)
            if m2: result["category"] = m2.group(1).strip(); break
        for pat in [r'"about"[^:]*:\s*"([^"]+)"', r'class="[^"]*about[^"]*"[^>]*>([^<]+)<']:
            m2 = re.search(pat, html, re.I)
            if m2: result["about_text"] = m2.group(1).strip()[:500]; break
        for m2 in re.finditer(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', html):
            d = re.sub(r'\D', '', m2.group(0))
            if len(d) == 10: result["phone"] = "+1" + d; break
        for m2 in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html):
            e = m2.group(0).lower()
            if not any(x in e for x in ["facebook.com", "example.com", "test.com"]):
                result["email"] = e; break
        m2 = re.search(r'https?://(?:www\.)?(?!facebook\.com|fb\.com)[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s"\'<>&]*)?', html)
        if m2:
            u = m2.group(0).strip()
            if not any(d in u.lower() for d in ["facebook.com", "fb.com", "google.com"]):
                result["website"] = u
        m2 = re.search(r'([A-Z][A-Za-z .]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)?', html)
        if m2:
            result["city"] = m2.group(1).strip()
            result["state"] = m2.group(2).strip()
            if m2.group(3): result["zip"] = m2.group(3).strip()
        for m2 in re.finditer(r'(\d[\d,]*)\s*(?:followers?|likes?)', html, re.I):
            try: result["follower_count"] = str(int(m2.group(1).replace(",", "")))
            except: pass
            break
        break
    return result

def process_one(church):
    cid = church["id"]
    name = church["name"]
    city = church.get("city", "")
    state = church.get("state", "")
    website = church.get("website", "")
    
    result = {"church_id": cid, "church_name": name, "facebook_page_found": False,
              "page_url": "", "page_name": "", "category": "", "phone": "", "email": "",
              "website": "", "address": "", "city": "", "state": "", "zip": "",
              "about_text": "", "follower_count": "", "source": "", "error": ""}
    
    page_url = None
    source = ""
    
    if website:
        page_url = find_fb_on_website(website)
        if page_url: source = "website_link"; time.sleep(0.5)
    if not page_url and city and state:
        page_url = google_search_fb(name, city, state)
        if page_url: source = "google_search"; time.sleep(1.0)
    if not page_url:
        page_url = google_search_fb(name, "", state)
        if page_url: source = "google_name_only"; time.sleep(1.0)
    
    if page_url:
        result["facebook_page_found"] = True
        result["source"] = source
        fb = scrape_fb_page(page_url)
        for k in fb: result[k] = fb[k]
        result["page_url"] = page_url
        time.sleep(1.0)
    else:
        result["error"] = "not_found"
    
    return result

def save_batch(results):
    fieldnames = ["church_id", "church_name", "facebook_page_found", "page_url", "page_name",
                  "category", "phone", "email", "website", "address", "city", "state", "zip",
                  "about_text", "follower_count", "source", "error"]
    mode = "a" if os.path.exists(OUT_CSV) else "w"
    with open(OUT_CSV, mode, newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == "w": w.writeheader()
        for r in results:
            row = {k: r.get(k, "") for k in fieldnames}
            w.writerow(row)

def load_done_ids():
    done = set()
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("church_id"): done.add(row["church_id"])
    return done

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Input CSV of churches")
    parser.add_argument("--batch", type=int, default=50, help="Batch size")
    parser.add_argument("--batch-num", type=int, default=None, help="Specific batch number to run")
    parser.add_argument("--resume", action="store_true", help="Skip already-processed IDs")
    args = parser.parse_args()
    
    with open(args.csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        churches = list(reader)
    
    log("Loaded %d churches from %s" % (len(churches), args.csv))
    
    if args.resume:
        done = load_done_ids()
        churches = [c for c in churches if c.get("id") not in done]
        log("Skipping %d already done, %d remaining" % (len(done), len(churches)))
    
    # Split into batches
    batches = [churches[i:i+args.batch] for i in range(0, len(churches), args.batch)]
    log("Split into %d batches of %d" % (len(batches), args.batch))
    
    if args.batch_num is not None:
        batches = [batches[args.batch_num]]
        log("Running batch %d only (%d churches)" % (args.batch_num, len(batches[0])))
    
    for bnum, batch in enumerate(batches):
        actual_num = args.batch_num if args.batch_num is not None else bnum
        log("--- Batch %d/%d (%d churches) ---" % (actual_num + 1, len(batches), len(batch)))
        results = []
        t0 = time.time()
        for i, church in enumerate(batch):
            result = process_one(church)
            results.append(result)
            if (i+1) % 10 == 0:
                found = sum(1 for r in results if r["facebook_page_found"])
                log("  %d/%d in batch, %d found" % (i+1, len(batch), found))
        
        save_batch(results)
        found = sum(1 for r in results if r["facebook_page_found"])
        elapsed = time.time() - t0
        log("Batch done: %d/%d found (%.1f%%) in %.0fs" % (found, len(batch), 100*found/len(batch), elapsed))
    
    # Final count
    done = load_done_ids()
    found = 0
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV) as f:
            for row in csv.DictReader(f):
                if row.get("facebook_page_found") == "True":
                    found += 1
    log("")
    log("=" * 50)
    log("COMPLETE: %d processed, %d found (%.1f%%)" % (len(done), found, 100*found/len(done) if done else 0))
    log("Results: %s" % OUT_CSV)

if __name__ == "__main__":
    main()
