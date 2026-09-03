#!/usr/bin/env python3
"""
Domain Verification Scraper
===========================
Visits shared/duplicate domains (2+ churches assigned the same URL),
scrapes page content, and matches each church against what's actually on the site.

Strategy:
  1. Find all domains shared by 2+ churches
  2. Visit each domain ONCE, extract title + meta + body text
  3. Score each assigned church against the page content (name, city, state)
  4. Keep the best match (score >= 30), clear websites from the rest
  5. Parked/placeholder domains → clear ALL assignments

Usage:
    python scripts/enrichment/verify_domains.py              # Full run
    python scripts/enrichment/verify_domains.py --dry-run     # Preview only
    python scripts/enrichment/verify_domains.py --workers 15  # Faster
"""
import csv, os, re, sys, time, sqlite3, urllib.request, urllib.error
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import html

# ── Path resolution ──
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
MAX_HTML_BYTES = 200 * 1024

stats = {"scraped": 0, "errors": 0, "kept": 0, "cleared": 0}
stats_lock = __import__("threading").Lock()

STOP_WORDS = {'THE', 'OF', 'A', 'AN', 'AND', 'IN', 'AT', 'TO', 'FOR', 'BY', 'IS', 'ARE', 'WAS', 'WERE'}

PARKED_INDICATORS = [
    'domain is parked', 'buy this domain', 'domain for sale',
    'this domain may be for sale', 'godaddy', 'sedo parking',
    'coming soon', 'under construction', 'website is coming soon',
    'hostgator', 'bluehost', 'siteground',
    'this domain is registered', 'domain name for sale',
    'purchase this domain', 'this domain is available',
]


def extract_page_text(url):
    """Fetch a page and extract title + meta + body text. Returns (title, meta, body, http_status_or_error)."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(MAX_HTML_BYTES)
            http_status = resp.status
    except urllib.error.HTTPError as e:
        return "", "", "", f"HTTP_{e.code}"
    except Exception as e:
        return "", "", "", str(e)[:60]

    text = raw.decode("utf-8", errors="replace")

    # Extract title
    title = ""
    m = re.search(r'<title[^>]*>(.*?)</title>', text, re.IGNORECASE | re.DOTALL)
    if m:
        title = html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()

    # Extract meta description
    meta_desc = ""
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', text, re.IGNORECASE)
    if not m:
        m = re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']', text, re.IGNORECASE)
    if m:
        meta_desc = html.unescape(m.group(1)).strip()

    # Extract & clean body
    m = re.search(r'<body[^>]*>(.*?)</body>', text, re.IGNORECASE | re.DOTALL)
    body_text = m.group(1) if m else text
    body_text = re.sub(r'<script[^>]*>.*?</script>', '', body_text, flags=re.IGNORECASE | re.DOTALL)
    body_text = re.sub(r'<style[^>]*>.*?</style>', '', body_text, flags=re.IGNORECASE | re.DOTALL)
    body_text = re.sub(r'<[^>]+>', ' ', body_text)
    body_text = html.unescape(body_text)
    body = re.sub(r'\s+', ' ', body_text).strip()[:5000]

    return title, meta_desc, body, http_status


from gw_filters import web as gw_web


def score_match(church_name, city, state, title, meta_desc, body):
    """
    Score how well a church matches a page's content.
    Delegates to gw_filters.web.score_match().
    Returns (score_0_100, [reasons]).
    """
    result = gw_web.score_match(church_name, city, state, title, meta_desc, body)
    reasons = result["signals"]
    score = int(result["score"] * 100)
    return score, reasons

    # ── City/State in page ──
    if city_upper and len(city_upper) > 3 and city_upper in search_text:
        score += 20
        reasons.append(f"city_in_page({city})")
    if state_upper and len(state_upper) == 2 and state_upper in search_text:
        score += 10
        reasons.append("state_in_page")

    # ── Church name in body ──
    if church_upper in search_text and len(church_upper) > 5:
        score += 15
        reasons.append("name_in_body")
    elif sig_words:
        matches = sum(1 for w in sig_words if w in body.upper())
        if matches >= 3:
            score += 10
            reasons.append("body_3+_sig_words")
        elif matches >= 2:
            score += 5
            reasons.append("body_2_sig_words")

    # ── Negative: parked/placeholder ──
    for ind in PARKED_INDICATORS:
        if ind in search_text.lower():
            score = int(score * 0.3)  # Drastically reduce score
            reasons.append(f"parked({ind})")
            break

    return min(score, 100), reasons


def verify_domain(domain_url, churches):
    """
    Visit a domain once, scrape content, score all assigned churches.
    churches: list of (id, name, city, state)
    Returns: (domain_url, [(id, name, city, state, score, reasons_str, action)])
    """
    title, meta_desc, body, status = extract_page_text(domain_url)

    if isinstance(status, str) and (status.startswith("HTTP_") or status.startswith("http")):
        # HTTP error or connection issue - clear all
        return domain_url, [(c[0], c[1], c[2], c[3], 0, f"fetch_error:{status}", "clear") for c in churches]

    if not title and not body:
        return domain_url, [(c[0], c[1], c[2], c[3], 0, f"empty_content", "clear") for c in churches]

    results = []
    for church_id, name, city, state in churches:
        match = gw_web.score_match(name, city, state, title or "", meta_desc or "", body or "")
        score = int(match["score"] * 100)  # Convert 0-1 to 0-100
        reasons = ";".join(match["signals"])
        action = "keep" if score >= 30 else "clear"
        results.append((church_id, name, city, state, score, reasons, action))

    # Sort by score descending
    results.sort(key=lambda r: -r[4])

    # Keep only the TOP match if its score >= 30, clear others
    if results and results[0][4] >= 30:
        results[0] = (*results[0][:5], results[0][5], "keep")
        for i in range(1, len(results)):
            results[i] = (*results[i][:5], results[i][5], "clear")
    else:
        # No good match — clear all
        results = [(*r[:5], r[5], "clear") for r in results]

    return domain_url, results


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Domain Verification Scraper")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB changes")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="Parallel threads")
    parser.add_argument("--min-shared", type=int, default=2, help="Min churches sharing a domain")
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH)

    # Find all shared domains
    shared = db.execute(f"""
        SELECT website, COUNT(id) as cnt
        FROM churches
        WHERE website IS NOT NULL AND website != ''
        GROUP BY website
        HAVING cnt >= {args.min_shared}
        ORDER BY cnt DESC
    """).fetchall()

    total_domains = len(shared)
    total_churches_assigned = sum(r[1] for r in shared)

    log(f"Found {total_domains:,} shared domains affecting {total_churches_assigned:,} churches")

    if total_domains == 0:
        print("No shared domains to verify. Exiting.")
        return

    # Load churches per domain
    domain_churches = defaultdict(list)
    for url, cnt in shared:
        rows = db.execute("""
            SELECT id, name, city, state
            FROM churches
            WHERE website = ?
            ORDER BY id
        """, (url,)).fetchall()
        domain_churches[url] = rows

    db.close()

    if args.dry_run:
        print(f"\n{'='*60}")
        print(f"DRY RUN — No changes will be made")
        print(f"{'='*60}")
        shown = 0
        for url, churches in sorted(domain_churches.items(), key=lambda x: -len(x[1])):
            if shown >= 25:
                break
            print(f"\n  {len(churches):3d}x  {url}")
            for c in churches[:5]:
                print(f"       ID {c[0]}: {c[1][:45]} ({c[2]}, {c[3]})")
            if len(churches) > 5:
                print(f"       ... and {len(churches)-5} more")
            shown += 1
        print(f"\n  ({total_domains - 25} more domains not shown)")
        return

    # ── Scrape & Verify ──
    log(f"Starting verification of {total_domains:,} domains with {args.workers} workers...")
    start_time = time.time()

    all_results = {}
    items = list(domain_churches.items())
    completed = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(verify_domain, url, churches): url for url, churches in items}

        for future in as_completed(futures):
            url, results = future.result()
            all_results[url] = results
            completed += 1

            with stats_lock:
                stats["scraped"] += 1
                for r in results:
                    if r[6] == "keep":
                        stats["kept"] += 1
                    else:
                        stats["cleared"] += 1

            if completed % 100 == 0:
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                log(f"  {completed}/{total_domains} domains — "
                    f"kept {stats['kept']:,}, clear {stats['cleared']:,} "
                    f"({rate:.1f}/sec)")

    elapsed = time.time() - start_time
    log(f"\nVerification complete in {elapsed/60:.1f} min")
    log(f"  Domains checked: {stats['scraped']:,}")
    log(f"  Kept:  {stats['kept']:,}")
    log(f"  Clear: {stats['cleared']:,}")

    # ── Apply to DB ──
    kept_list = []
    clear_list = []

    for url, results in all_results.items():
        for r in results:
            church_id, name, city, state, score, reasons, action = r
            entry = (church_id, name, city, state, url, score, reasons)
            if action == "keep":
                kept_list.append(entry)
            else:
                clear_list.append(entry)

    # Print summary
    print(f"\n{'='*60}")
    print(f"CHANGES TO APPLY")
    print(f"{'='*60}")
    print(f"  Keep websites for:  {len(kept_list):,} churches")
    print(f"  Clear websites for: {len(clear_list):,} churches")

    # Show interesting results
    print(f"\nTop shared domains results:")
    shown = 0
    for url in sorted(all_results.keys(), key=lambda u: -len(domain_churches[u]))[:20]:
        results = all_results[url]
        kept = [r for r in results if r[6] == "keep"]
        cleared = [r for r in results if r[6] == "clear"]
        if kept:
            print(f"  {url}: {len(kept)} kept, {len(cleared)} cleared")
            for r in kept:
                print(f"    ✅ ID {r[0]}: {r[1][:40]} ({r[2]}, {r[3]}) score={r[4]}")
            for r in cleared[:3]:
                print(f"    ❌ ID {r[0]}: {r[1][:40]} ({r[2]}, {r[3]}) score={r[4]}")
            if len(cleared) > 3:
                print(f"    ❌ ... and {len(cleared)-3} more")
        else:
            print(f"  {url}: ALL {len(cleared)} cleared (no match found)")

    # Actually apply
    print(f"\nUpdating database...")
    db = sqlite3.connect(DB_PATH)
    db.execute("BEGIN TRANSACTION")
    for entry in clear_list:
        db.execute("UPDATE churches SET website = '', website_scrape_status = 'not_found' WHERE id = ?",
                   (entry[0],))
    db.commit()

    # Also update status for kept ones to confirmed
    for entry in kept_list:
        db.execute("UPDATE churches SET website_scrape_status = 'verified' WHERE id = ?",
                   (entry[0],))
    db.commit()
    db.close()

    log(f"✅ Database updated: {len(clear_list):,} cleared, {len(kept_list):,} marked verified")

    # Save report CSV
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(PROJECT_DIR, "data", f"domain_verification_{ts}.csv")
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["domain", "church_id", "church_name", "city", "state", "score", "reasons", "action"])
        for url, results in all_results.items():
            for r in results:
                w.writerow([url, r[0], r[1], r[2], r[3], r[4], r[5], r[6]])

    log(f"Report saved: {report_path}")

    # Final stats
    db = sqlite3.connect(DB_PATH)
    w = db.execute("SELECT COUNT(id) FROM churches WHERE website IS NOT NULL AND website != ''").fetchone()[0]
    v = db.execute("SELECT COUNT(id) FROM churches WHERE website_scrape_status='verified'").fetchone()[0]
    nf = db.execute("SELECT COUNT(id) FROM churches WHERE website_scrape_status='not_found'").fetchone()[0]
    f_count = db.execute("SELECT COUNT(id) FROM churches WHERE website_scrape_status='found'").fetchone()[0]
    db.close()
    print(f"\n{'='*60}")
    print(f"FINAL DATABASE STATE")
    print(f"{'='*60}")
    print(f"  Total websites:         {w:,}")
    print(f"  Verified (confirmed):   {v:,}")
    print(f"  Found (batch, unverif): {f_count:,}")
    print(f"  Not found (cleared):    {nf:,}")


if __name__ == "__main__":
    main()
