#!/usr/bin/env python3
"""
Search API Website Finder — Serper / Google CSE Pipeline
==========================================================
Programmatic pipeline to find church websites using a search API with
Jaro-Winkler string distance matching.

Pipeline steps:
  1. Query search API: `"[Church Name]" [City] [State]`
  2. Collect top N (default: 5) organic results
  3. Filter out known non-church domains (wikipedia, yelp, mapquest, etc.)
  4. Score each result URL against the church name using Jaro-Winkler similarity
  5. Pick the best match above a confidence threshold
  6. Optionally verify by fetching the page and checking title tag
  7. Write results to churches.db

Scoring:
  - Jaro-Winkler gives high scores to strings that share a common prefix
    and similar character composition. Church names often appear verbatim
    in the URL path or page title (e.g., "First Baptist Church Springfield"
    → "first-baptist-church-springfield.org").
  - Combined with page title verification, this eliminates the "Batch Guess"
    bottleneck (which had a 51% bad-guess rate).

Usage:
    # Full run
    python scripts/enrichment/search_api_finder.py

    # Test with limit
    python scripts/enrichment/search_api_finder.py --limit 1000 --dry-run

    # Use Google CSE instead of Serper
    python scripts/enrichment/search_api_finder.py --api google_cse

    # Resume from checkpoint
    python scripts/enrichment/search_api_finder.py --resume

Environment variables:
    SERPER_API_KEY=...       (for Serper — default)
    GOOGLE_CSE_KEY=...       (for Google Custom Search)
    GOOGLE_CSE_ID=...        (for Google Custom Search)

Requires:
    pip install requests

Cost estimate (Serper):
    - 100 free credits, then $0.004/query
    - 229K missing websites → ~$916 full run (or ~$550 with CSE at $5/1K)
    - Practical approach: run in batches, target high-value churches first
"""
import json, os, re, sys, time, sqlite3, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from difflib import SequenceMatcher

# ── Jaro-Winkler implementation (no external deps) ──

def _jaro(s1, s2):
    """Compute Jaro similarity between two strings."""
    if s1 == s2:
        return 1.0
    len_s1, len_s2 = len(s1), len(s2)
    if len_s1 == 0 or len_s2 == 0:
        return 0.0
    
    match_dist = max(len_s1, len_s2) // 2 - 1
    if match_dist < 0:
        match_dist = 0
    
    s1_matches = [False] * len_s1
    s2_matches = [False] * len_s2
    
    matches = 0
    transpositions = 0
    
    for i in range(len_s1):
        start = max(0, i - match_dist)
        end = min(i + match_dist + 1, len_s2)
        for j in range(start, end):
            if s2_matches[j]:
                continue
            if s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break
    
    if matches == 0:
        return 0.0
    
    k = 0
    for i in range(len_s1):
        if not s1_matches[i]:
            continue
        while k < len_s2 and not s2_matches[k]:
            k += 1
        if k < len_s2 and s1[i] != s2[k]:
            transpositions += 1
        k += 1
    
    return (matches / len_s1 + matches / len_s2 +
            (matches - transpositions / 2) / matches) / 3.0


def jaro_winkler(s1, s2, prefix_scale=0.1):
    """Compute Jaro-Winkler similarity, which boosts scores for common prefixes."""
    j = _jaro(s1, s2)
    prefix_len = 0
    for i in range(min(len(s1), len(s2), 4)):
        if s1[i] == s2[i]:
            prefix_len += 1
        else:
            break
    return j + (prefix_len * prefix_scale * (1 - j))


def name_url_similarity(church_name, url):
    """Score how well a URL matches a church name.
    
    Uses Jaro-Winkler on the normalized domain + path vs normalized church name.
    Returns score between 0 and 1.
    """
    if not url:
        return 0.0
    
    # Extract meaningful parts from URL
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower().rstrip('/')
    
    # Remove common prefixes
    domain = re.sub(r'^(www\d?\.)', '', domain)
    
    # Create "URL name" from domain + path
    url_name = domain + path
    url_name = re.sub(r'[^a-z0-9]', ' ', url_name)
    url_name = re.sub(r'\s+', ' ', url_name).strip()
    
    # Normalize church name
    norm_name = church_name.lower()
    norm_name = re.sub(r'[^a-z0-9]', ' ', norm_name)
    norm_name = re.sub(r'\s+', ' ', norm_name).strip()
    
    return jaro_winkler(norm_name, url_name)


# ── Known non-church domains to filter ──

NON_CHURCH_DOMAINS = {
    'wikipedia.org', 'yelp.com', 'yellowpages.com', 'mapquest.com',
    'google.com', 'facebook.com', 'instagram.com', 'twitter.com', 'x.com',
    'linkedin.com', 'youtube.com', 'pinterest.com', 'tripadvisor.com',
    'bbb.org', 'guidestar.org', 'charitynavigator.org', 'justgive.org',
    'causes.com', 'gofundme.com', 'patreon.com', 'donate.com',
    'city-data.com', 'neighborhoodscout.com', 'niche.com',
    'realtor.com', 'zillow.com', 'redfin.com', 'apartments.com',
    'chamberofcommerce.com', 'manta.com', 'merchantcircle.com',
    'whitepages.com', '411.com', 'finder.com', 'npost.com',
    'factual.com', 'infogroup.com', 'data-axle.com',
    'census.gov', 'data.gov', 'usa.gov',
    'amazon.com', 'ebay.com', 'etsy.com',
    'patch.com', 'nextdoor.com',
}

# ── Config ──
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
CHECKPOINT = os.path.join(PROJECT_DIR, 'data', 'search_api_checkpoint.json')

# Search API settings
SEARCH_API = os.environ.get('SEARCH_API', 'serper')  # 'serper' or 'google_cse'
SERPER_KEY = os.environ.get('SERPER_API_KEY', '')
GOOGLE_CSE_KEY = os.environ.get('GOOGLE_CSE_KEY', '')
GOOGLE_CSE_ID = os.environ.get('GOOGLE_CSE_ID', '')

# Scoring thresholds
MIN_SIMILARITY_SCORE = 0.55       # Jaro-Winkler threshold for URL acceptance
PAGE_TITLE_BOOST = 0.10           # Bonus if church name appears in page title
PAGE_TITLE_MIN_SIMILARITY = 0.40  # Lower threshold accepted if title matched

# Rate limiting
API_DELAY = 0.3   # seconds between API calls (~3/sec = safe for most APIs)
VERIFY_WORKERS = 10

# Stats
stats = {'api_calls': 0, 'results_collected': 0, 'churches_found': 0,
         'title_verified': 0, 'errors': 0, 'skipped_existing': 0,
         'no_results': 0, 'below_threshold': 0}
stats_lock = __import__('threading').Lock()


# ── Search API ──

def search_church_website(name, city, state):
    """Search for church website. Returns list of (url, title) tuples."""
    query = f'"{name}" {city} {state}'
    
    if SEARCH_API == 'serper' and SERPER_KEY:
        return _search_serper(query)
    elif SEARCH_API == 'google_cse' and GOOGLE_CSE_KEY and GOOGLE_CSE_ID:
        return _search_google_cse(query)
    else:
        print("WARNING: No search API configured. Set SERPER_API_KEY or GOOGLE_CSE_KEY/ID.")
        return []


def _search_serper(query):
    """Call Serper API. Returns list of (url, title)."""
    url = 'https://google.serper.dev/search'
    payload = json.dumps({'q': query, 'num': 5}).encode('utf-8')
    
    req = urllib.request.Request(url, data=payload, headers={
        'X-API-KEY': SERPER_KEY,
        'Content-Type': 'application/json',
    })
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        results = []
        for item in data.get('organic', []):
            link = item.get('link', '')
            title = item.get('title', '')
            if link and _is_church_candidate(link):
                results.append((link, title))
        
        with stats_lock:
            stats['api_calls'] += 1
            stats['results_collected'] += len(results)
        
        return results
    except Exception as e:
        with stats_lock:
            stats['errors'] += 1
        return []


def _search_google_cse(query):
    """Call Google Custom Search API."""
    encoded = urllib.parse.quote(query)
    url = (f'https://www.googleapis.com/customsearch/v1?key={GOOGLE_CSE_KEY}'
           f'&cx={GOOGLE_CSE_ID}&q={encoded}&num=5')
    
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        results = []
        for item in data.get('items', []):
            link = item.get('link', '')
            title = item.get('title', '')
            if link and _is_church_candidate(link):
                results.append((link, title))
        
        with stats_lock:
            stats['api_calls'] += 1
            stats['results_collected'] += len(results)
        
        return results
    except Exception as e:
        with stats_lock:
            stats['errors'] += 1
        return []


def _is_church_candidate(url):
    """Filter out non-church domains from search results."""
    domain = urllib.parse.urlparse(url).netloc.lower()
    domain = re.sub(r'^www\d?\.', '', domain)
    
    if domain in NON_CHURCH_DOMAINS:
        return False
    
    # Skip social media, video, maps
    for skip_pattern in [
        'facebook.com', 'instagram.com', 'youtube.com', 'tiktok.com',
        'twitter.com', 'x.com', 'linkedin.com', 'pinterest.com',
        'maps.google', 'maps.apple',
        'en.wikipedia.org',
    ]:
        if skip_pattern in domain:
            return False
    
    return True


# ── Page Title Verification ──

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/17.2',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0',
]


def verify_page_title(church_name, url):
    """Fetch page and check if church name appears in <title>.
    
    Returns (score_boost, title_text) where score_boost is 0.0-0.15.
    """
    try:
        ua = USER_AGENTS[hash(url) % len(USER_AGENTS)]
        req = urllib.request.Request(url, headers={
            'User-Agent': ua,
            'Accept': 'text/html',
            'Accept-Language': 'en-US,en;q=0.9',
            'Range': 'bytes=0-65536',  # Only fetch first 64KB
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read(65536).decode('utf-8', errors='replace')
        
        # Extract <title> tag
        m = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
        if not m:
            return 0.0, ''
        
        title = m.group(1).strip()
        if not title:
            return 0.0, ''
        
        # Clean church name for comparison
        clean_name = re.sub(r'[^a-z0-9\s]', '', church_name.lower())
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        clean_title = re.sub(r'[^a-z0-9\s]', '', title.lower())
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        
        # Check if church name appears in title (or vice versa)
        sim = jaro_winkler(clean_name, clean_title)
        
        if sim > PAGE_TITLE_MIN_SIMILARITY:
            return PAGE_TITLE_BOOST, title
        
        # Also check if key words overlap
        name_words = set(clean_name.split())
        title_words = set(clean_title.split())
        overlap = len(name_words & title_words) / max(len(name_words), 1)
        
        if overlap > 0.3:
            return PAGE_TITLE_BOOST * 0.5, title
        
        return 0.0, title
    except Exception:
        return 0.0, ''


# ── Main Scoring ──

def score_result(church_name, url, title):
    """Score a (url, title) pair for how well it matches a church name.
    Delegates to gw_filters.web.score_search_result().
    Returns score 0.0-1.0.
    """
    from gw_filters.web import score_search_result
    return score_search_result(church_name, url, title)


def find_best_website(church_id, church_name, city, state):
    """Find best website for a church. Returns (url, confidence, source, title) or None."""
    results = search_church_website(church_name, city, state)
    
    if not results:
        with stats_lock:
            stats['no_results'] += 1
        return None
    
    # Score all results
    scored = []
    for url, title in results:
        s = score_result(church_name, url, title)
        scored.append((s, url, title))
    
    # Sort by score descending
    scored.sort(key=lambda x: -x[0])
    best_score, best_url, best_title = scored[0]
    
    # Title verification for borderline cases
    title_boost = 0.0
    if best_score < MIN_SIMILARITY_SCORE + 0.1:
        title_boost, verified_title = verify_page_title(church_name, best_url)
        if verified_title:
            best_title = verified_title
            with stats_lock:
                stats['title_verified'] += 1
    
    final_score = best_score + title_boost
    
    if final_score >= MIN_SIMILARITY_SCORE:
        # Determine confidence level
        if final_score >= 0.75:
            confidence = 0.70  # Strong match
        elif final_score >= 0.60:
            confidence = 0.55  # Moderate match
        else:
            confidence = 0.40  # Weak match
        
        with stats_lock:
            stats['churches_found'] += 1
        
        return (best_url, confidence, f'search_api_{SEARCH_API}', best_title)
    
    with stats_lock:
        stats['below_threshold'] += 1
    return None


# ── Database ──

def get_churches_needing_websites(db, limit=0):
    """Get churches missing websites, most promising first."""
    query = """
        SELECT id, name, city, state
        FROM churches
        WHERE (website = '' OR website IS NULL)
          AND city != '' AND state != ''
          AND name != ''
        ORDER BY 
            -- Prioritize churches with more distinguishing names
            CASE WHEN denomination != '' THEN 0 ELSE 1 END,
            LENGTH(name) DESC,
            id
    """
    if limit:
        query += f" LIMIT {limit}"
    return db.execute(query).fetchall()


def load_checkpoint():
    """Load processed church IDs from checkpoint."""
    if not os.path.exists(CHECKPOINT):
        return set()
    try:
        with open(CHECKPOINT) as f:
            data = json.load(f)
        return set(data.get('processed_ids', []))
    except Exception:
        return set()


def save_checkpoint(processed_ids):
    """Save checkpoint."""
    os.makedirs(os.path.dirname(CHECKPOINT), exist_ok=True)
    with open(CHECKPOINT, 'w') as f:
        json.dump({
            'processed_ids': list(processed_ids),
            'updated': datetime.now().isoformat()
        }, f)


# ── Main ──

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Search API Website Finder')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--limit', type=int, default=0, help='Limit churches to process')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    parser.add_argument('--api', choices=['serper', 'google_cse'], default=None,
                       help='Override search API')
    parser.add_argument('--workers', type=int, default=VERIFY_WORKERS,
                       help='Title verification workers')
    parser.add_argument('--high-value-only', action='store_true',
                       help='Only process churches with existing contact data priority')
    args = parser.parse_args()
    
    global SEARCH_API
    if args.api:
        SEARCH_API = args.api
    
    # Check API key
    if SEARCH_API == 'serper' and not SERPER_KEY:
        print("ERROR: SERPER_API_KEY not set. Export it or use --api google_cse.")
        print("  set SERPER_API_KEY=your_key_here")
        sys.exit(1)
    elif SEARCH_API == 'google_cse' and (not GOOGLE_CSE_KEY or not GOOGLE_CSE_ID):
        print("ERROR: GOOGLE_CSE_KEY and GOOGLE_CSE_ID must be set.")
        sys.exit(1)
    
    print("=" * 60)
    print(f"Search API Website Finder — API: {SEARCH_API}")
    print("=" * 60)
    
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    
    # Load churches
    churches = get_churches_needing_websites(db, args.limit)
    print(f"\nChurches needing websites: {len(churches):,}")
    
    if args.high_value_only:
        # Filter to high-value targets (churches with EINs or addresses we've invested in)
        churches = [r for r in churches if not r['denomination'] == '' or not r['pastor_name'] == '']
        print(f"  (high-value filter applied: {len(churches):,} remaining)")
    
    if args.dry_run:
        print("\n  [DRY RUN] Would search for:")
        for r in churches[:15]:
            print(f"    {r['id']:>8d} | {r['name'][:45]:45s} | {r['city']:20s} {r['state']}")
        if len(churches) > 15:
            print(f"    ... and {len(churches) - 15:,} more")
        db.close()
        return
    
    # Load checkpoint
    processed_ids = load_checkpoint() if args.resume else set()
    if processed_ids:
        print(f"Resuming: {len(processed_ids):,} already processed")
    
    # Process
    updates = []
    api_delay_tracker = {'last_call': 0.0}
    
    for i, row in enumerate(churches):
        church_id = row['id']
        if church_id in processed_ids:
            stats['skipped_existing'] += 1
            continue
        
        result = find_best_website(
            church_id, row['name'], row['city'], row['state']
        )
        
        if result:
            url, confidence, source, title = result
            updates.append((church_id, url, confidence, source))
        
        # Rate limiting
        now = time.time()
        elapsed = now - api_delay_tracker['last_call']
        if elapsed < API_DELAY:
            time.sleep(API_DELAY - elapsed)
        api_delay_tracker['last_call'] = time.time()
        
        # Progress report
        if (i + 1) % 200 == 0:
            pct = (i + 1) / len(churches) * 100
            found_rate = stats['churches_found'] / max(stats['api_calls'], 1) * 100
            print(f"  Progress: {i+1:,}/{len(churches):,} ({pct:.1f}%) | "
                  f"Found: {stats['churches_found']:,} ({found_rate:.0f}%) | "
                  f"No results: {stats['no_results']:,} | "
                  f"Below threshold: {stats['below_threshold']:,}")
    
    print(f"\n--- Search complete ---")
    print(f"  API calls: {stats['api_calls']:,}")
    print(f"  Results collected: {stats['results_collected']:,}")
    print(f"  Churches found: {stats['churches_found']:,}")
    print(f"  No search results: {stats['no_results']:,}")
    print(f"  Below similarity threshold: {stats['below_threshold']:,}")
    print(f"  Title verified: {stats['title_verified']:,}")
    print(f"  Errors: {stats['errors']:,}")
    
    # Write to database
    print(f"\n--- Writing {len(updates):,} results to database ---")
    
    db_updates = 0
    for church_id, url, confidence, source in updates:
        # Only write if current website is empty or has lower confidence
        cur = db.execute("SELECT website, website_confidence FROM churches WHERE id=?", (church_id,))
        row = cur.fetchone()
        curr_website = row['website'] if row else ''
        curr_conf = row['website_confidence'] if row else 0
        
        if not curr_website or (curr_conf or 0) < confidence:
            db.execute("""
                UPDATE churches SET 
                    website = ?,
                    website_source = ?,
                    website_confidence = ?,
                    website_last_verified = datetime('now'),
                    last_updated = datetime('now')
                WHERE id = ?
            """, (url, source, confidence, church_id))
            db_updates += 1
    
    db.commit()
    print(f"  DB updates: {db_updates:,}")
    
    # Log to provenance
    db.execute("""
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted, fields_populated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, 'completed', ?)
    """, (
        f'search_api_{SEARCH_API}',
        'search_api_finder.py',
        datetime.now().isoformat(),
        datetime.now().isoformat(),
        db_updates,
        'website',
        stats['api_calls'],
        stats['churches_found'],
        f'API: {SEARCH_API} | Found {stats["churches_found"]} websites from {stats["api_calls"]} queries | {stats["title_verified"]} title-verified'
    ))
    db.commit()
    
    # Save checkpoint
    all_processed = processed_ids | {r['id'] for r in churches if r['id'] not in processed_ids}
    save_checkpoint(all_processed)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Churches processed:    {stats['api_calls']:>8,}")
    print(f"  Websites found:        {stats['churches_found']:>8,}")
    print(f"  No results:            {stats['no_results']:>8,}")
    print(f"  Below threshold:       {stats['below_threshold']:>8,}")
    print(f"  Title verified:        {stats['title_verified']:>8,}")
    print(f"  DB updates:            {db_updates:>8,}")
    print(f"  Success rate:          {stats['churches_found']/max(stats['api_calls'],1)*100:.1f}%")
    
    db.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
