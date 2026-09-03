#!/usr/bin/env python3
"""
Batch Domain Finder v2 — DuckDuckGo + Domain Guessing + Page Verification
==========================================================================
Three-tier website discovery:

  Tier 1 — DuckDuckGo Search (FREE, unlimited)
    Searches "Church Name City State" via DDG.
    Returns real verified church websites. Filters out Wikipedia/Yelp/etc.

  Tier 2 — Domain Guessing
    Name-based domain patterns (e.g. "first-baptist-church.org") checked via HEAD.

  Tier 3 — Page Title Verification
    For guessed domains: fetches the page, checks if church name appears in <title>.

Supports two modes:
  --db PATH     Normal mode: reads churches from SQLite, writes results back
  --csv INPUT   EC2 mode: reads church list from CSV, outputs results to CSV

Usage:
    # Normal mode (local)
    python scripts/enrichment/batch_domain_finder.py
    python scripts/enrichment/batch_domain_finder.py --limit 50000 --workers 20

    # CSV mode (EC2 instances — no DB needed)
    python batch_domain_finder.py --csv churches_chunk.csv --output results.csv --workers 10
"""
import csv, html, json, os, re, sys, time, sqlite3, urllib.request, urllib.error
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Optional DuckDuckGo ──
try:
    from ddgs import DDGS
    HAS_DDG = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        HAS_DDG = True
    except ImportError:
        HAS_DDG = False

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "pipeline")):
        break
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        size = os.path.getsize(os.path.join(PROJECT_DIR, "churches.db"))
        if size > 1000000:
            break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) < 1000000:
    cwd_db = os.path.join(os.getcwd(), "churches.db")
    if os.path.exists(cwd_db) and os.path.getsize(cwd_db) > 1000000:
        DB_PATH = cwd_db

MAX_WORKERS = 8
TIMEOUT = 10

stats = {"checked": 0, "ddg_found": 0, "guess_found": 0, "verified": 0, "errors": 0}
stats_lock = __import__("threading").Lock()

SKIP_DOMAINS = [
    "wikipedia.org", "facebook.com", "yelp.com", "yellowpages.com",
    "maps.google", "google.com/maps", "faithstreet.com", "usachurches.org",
    "nonprofitlocator.org", "charitynavigator.org", "guidestar.org",
    "linkedin.com", "twitter.com", "instagram.com", "youtube.com",
    "bbb.org", "manta.com", "merchantcircle.com", "citysearch.com",
    "chamberofcommerce.com", "opengovus.com", "govtrack.us",
    "maps.apple.com", "duckduckgo.com", "bing.com", "whitepages.com",
]

STOP_WORDS = {'THE', 'OF', 'A', 'AN', 'AND', 'IN', 'AT'}
ABBREVS = {
    'FIRST': 'f', 'BAPTIST': 'b', 'CHURCH': 'c', 'METHODIST': 'm',
    'LUTHERAN': 'l', 'PRESBYTERIAN': 'p', 'PENTECOSTAL': 'p',
    'CATHOLIC': 'c', 'EPISCOPAL': 'e', 'CHRISTIAN': 'c',
    'ASSEMBLIES': 'a', 'GOSPEL': 'g', 'CALVARY': 'c', 'CHAPEL': 'c',
    'NAZARENE': 'n', 'MISSIONARY': 'm', 'ALLIANCE': 'a',
    'INDEPENDENT': 'i', 'BIBLE': 'b', 'FELLOWSHIP': 'f',
}


# ── Tier 1: DuckDuckGo Search ──

def ddg_search(name, city, state):
    """Search DDG for a church's website. Returns URL or None."""
    if not HAS_DDG:
        return None
    query = f"{name} {city or ''} {state or ''}".strip()
    if not query:
        return None
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
    except Exception:
        return None
    for r in results:
        href = r.get("href", "").strip().rstrip("/")
        if not href:
            continue
        domain = href.lower().split("/")[2] if "://" in href else href.lower().split("/")[0]
        if any(s in domain for s in SKIP_DOMAINS):
            continue
        if "." not in domain or domain.count(".") > 3:
            continue
        if not href.startswith("http"):
            href = "https://" + href
        return href
    return None


# ── Tier 2: Domain Guessing ──

def generate_guesses(name, city, state):
    if not name:
        return []
    n = name.strip().upper()
    city_clean = (city or "").strip().lower().replace(" ", "").replace(".", "").replace("'", "")
    name_clean = re.sub(r'[^A-Z0-9 ]', '', n).strip()
    words = name_clean.split()
    sig_words = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    if not sig_words:
        return []
    guesses = set()
    full = '-'.join(w.lower() for w in sig_words[:4])
    if full:
        for tld in ['.org', '.com', '.church']:
            guesses.add(f"{full}{tld}")
            if city_clean:
                guesses.add(f"{full}{city_clean}{tld}")
    abbr = ''.join(ABBREVS.get(w, w[0].lower()) for w in sig_words[:3])
    if abbr and len(abbr) <= 6 and city_clean:
        guesses.add(f"{abbr}{city_clean}.org")
        guesses.add(f"{abbr}{city_clean}.com")
    if city_clean and full:
        guesses.add(f"{city_clean}{full}.org")
        guesses.add(f"{city_clean}{full}.com")
    return list(guesses)[:8]


def check_domain(domain):
    for proto in ['https', 'http']:
        try:
            url = f"{proto}://{domain}"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; GrantWizard/1.0)",
                "Accept": "text/html",
            }, method='HEAD')
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return url
        except urllib.error.HTTPError as e:
            if e.code in (200, 301, 302, 403):
                return f"{proto}://{domain}"
        except Exception:
            pass
    return None


# ── Tier 3: Page Title Verification ──

def verify_title(url, church_name):
    """Fetch page, check if church name appears in <title>. Returns (url, score)."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(100 * 1024)
    except Exception:
        return url, 0
    text = raw.decode("utf-8", errors="replace")
    title = ""
    m = re.search(r'<title[^>]*>(.*?)</title>', text, re.IGNORECASE | re.DOTALL)
    if m:
        title = html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
    if not title:
        return url, 0
    church_upper = church_name.strip().upper()
    title_upper = title.upper()
    if church_upper in title_upper and len(church_upper) > 5:
        return url, 90
    sig_words = [w for w in church_upper.split() if w not in STOP_WORDS and len(w) > 2]
    matches = sum(1 for w in sig_words if w in title_upper) if sig_words else 0
    if matches >= 3:
        return url, 70
    elif matches == 2:
        return url, 40
    elif matches == 1:
        return url, 15
    return url, 0


def process_church(name, city, state, church_id, use_ddg=True, verify=True):
    """Three-tier lookup. Returns (id, url, source, score) or None."""
    # Tier 1: DDG
    if use_ddg and HAS_DDG:
        try:
            url = ddg_search(name, city, state)
            if url:
                return (church_id, url, "ddg", 95)
        except Exception:
            pass
    # Tier 2: Guessing
    guesses = generate_guesses(name, city, state)
    if not guesses:
        return None
    for domain in guesses:
        url = check_domain(domain)
        if url:
            if verify:
                try:
                    verified_url, score = verify_title(url, name)
                    if score >= 40:
                        return (church_id, verified_url, "guess_verified", score)
                    elif score > 0:
                        return (church_id, url, "guess_partial", score)
                    else:
                        return (church_id, url, "guess_low", 5)
                except Exception:
                    return (church_id, url, "guess", 50)
            else:
                return (church_id, url, "guess", 50)
    return None


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def process_csv(input_csv, output_csv, workers, use_ddg, verify):
    """CSV mode: read churches from CSV, write results to CSV."""
    rows = []
    with open(input_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append((r.get("id", r.get("ID", "")), r.get("name", ""),
                         r.get("city", ""), r.get("state", "")))
    total = len(rows)
    log(f"CSV mode: checking {total:,} churches, output -> {output_csv}")
    found = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(process_church, r[1], r[2], r[3], r[0], use_ddg, verify): r[0] for r in rows}
        done = 0
        for f in as_completed(futures):
            done += 1
            r = f.result()
            if r:
                found.append(r)
            with stats_lock:
                stats["checked"] += 1
                if r:
                    if r[2] == "ddg":
                        stats["ddg_found"] += 1
                    else:
                        stats["guess_found"] += 1
            if done % 500 == 0:
                log(f"  {done:,}/{total:,} — DDG:{stats['ddg_found']} Guess:{stats['guess_found']}")
    ttl = stats["ddg_found"] + stats["guess_found"]
    log(f"Done: {stats['checked']:,} checked, {ttl:,} found")
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "website", "source", "confidence"])
        w.writerows(found)
    log(f"Saved: {output_csv}")
    return output_csv


def process_db(limit, offset, workers, use_ddg, verify, update_db):
    """DB mode: read churches from SQLite, write results back."""
    db = sqlite3.connect(DB_PATH)
    for col in ["website_scrape_status", "website_confidence", "website_source"]:
        try:
            db.execute(f"ALTER TABLE churches ADD COLUMN {col} TEXT DEFAULT 'pending'")
        except:
            pass
    query = ("SELECT id, name, city, state FROM churches "
             "WHERE (website IS NULL OR website = '') "
             "AND (website_scrape_status IS NULL OR website_scrape_status IN ('pending','not_found'))")
    if limit:
        query += f" LIMIT {limit}"
    elif offset:
        query += " LIMIT -1"
    if offset:
        query += f" OFFSET {offset}"
    rows = db.execute(query).fetchall()
    db.close()
    total = len(rows)
    log(f"DB mode: checking {total:,} churches")
    found = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(process_church, r[1], r[2], r[3], r[0], use_ddg, verify): r[0] for r in rows}
        done = 0
        for f in as_completed(futures):
            done += 1
            r = f.result()
            if r:
                found.append(r)
            with stats_lock:
                stats["checked"] += 1
                if r:
                    if r[2] == "ddg":
                        stats["ddg_found"] += 1
                    else:
                        stats["guess_found"] += 1
            if done % 500 == 0:
                log(f"  {done:,}/{total:,} — DDG:{stats['ddg_found']} Guess:{stats['guess_found']}")
    ttl = stats["ddg_found"] + stats["guess_found"]
    log(f"Done: {stats['checked']:,} checked, {ttl:,} found")
    if found and update_db:
        db = sqlite3.connect(DB_PATH)
        upd = 0
        for cid, url, source, score in found:
            status = "verified" if source == "ddg" else "found"
            db.execute("UPDATE churches SET website=?, website_scrape_status=?, "
                       "website_source=?, website_confidence=?, website_last_verified=datetime('now') "
                       "WHERE id=?", (url, status, source, score, cid))
            upd += 1
            if upd % 500 == 0:
                db.commit()
        db.commit()
        db.close()
        log(f"Updated {upd:,} records in DB")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(PROJECT_DIR, "data", f"batch_found_v2_{ts}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "website", "source", "confidence"])
        w.writerows(found)
    log(f"Saved: {csv_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch Domain Finder v2")
    parser.add_argument("--csv", type=str, help="Input CSV (EC2 mode)")
    parser.add_argument("--output", type=str, default="", help="Output CSV path")
    parser.add_argument("--limit", type=int, default=0, help="Max records (DB mode)")
    parser.add_argument("--offset", type=int, default=0, help="Skip N records")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="Parallel threads")
    parser.add_argument("--no-ddg", action="store_true", help="Skip DDG search")
    parser.add_argument("--no-verify", action="store_true", help="Skip title verification")
    parser.add_argument("--no-update", action="store_true", help="Skip DB update (DB mode)")
    args = parser.parse_args()

    if not HAS_DDG and not args.no_ddg:
        log("WARNING: DDG not installed. pip install ddgs")
        log("Falling back to domain guessing only.")

    if args.csv:
        output = args.output or args.csv.replace(".csv", "_results.csv")
        process_csv(args.csv, output, args.workers, not args.no_ddg, not args.no_verify)
    else:
        process_db(args.limit, args.offset, args.workers,
                   not args.no_ddg, not args.no_verify, not args.no_update)


if __name__ == "__main__":
    main()
