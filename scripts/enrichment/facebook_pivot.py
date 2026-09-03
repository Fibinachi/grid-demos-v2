#!/usr/bin/env python3
"""
Facebook URL Discovery & Contact Extraction
=============================================
Two-phase pipeline for extracting contact data from church Facebook pages.

Phase 1 — Facebook URL Discovery
  Uses Serper API or Google Custom Search to find Facebook pages for churches
  that lack websites. Queries: `site:facebook.com "[Church Name]" [City] [State]`
  Saves discovered URLs to churches.facebook_url.

Phase 2 — About Page Scraping
  For churches with known Facebook URLs, visits the public "About" page
  (facebook.com/[page]/about) and extracts:
    - Website URL (from the About section portfolio/website field)
    - Phone number
    - Email (if listed publicly in About → Contact Info)
    - Service hours (if listed)

Why this works:
  Small/local congregations that lack a standalone website almost always have
  a Facebook page. The Facebook "About" section frequently publishes:
    - A website URL (often a free site or denominational page)
    - A phone number the church actually answers
    - A contact email
    - Service times

Usage:
    # Phase 1: Find Facebook URLs for church-name-based queries
    python scripts/enrichment/facebook_pivot.py --find --limit 5000

    # Phase 2: Scrape About pages for discovered FB URLs
    python scripts/enrichment/facebook_pivot.py --scrape --limit 1000

    # Full pipeline: find and scrape
    python scripts/enrichment/facebook_pivot.py --pipeline --limit 2000

    # Dry-run preview
    python scripts/enrichment/facebook_pivot.py --find --dry-run --limit 100

Requires:
    pip install serpapi  (or serper SDK — see SEARCH_API docs below)
    pip install requests

Notes:
    - Facebook actively blocks scraping. Use rotating user-agents and delays.
    - The public Facebook "About" page (mbasic.facebook.com variant) is
      more scrapeable than the main facebook.com domain.
"""
import csv, html, json, os, re, sys, time, sqlite3, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from difflib import SequenceMatcher

# ── Config ──
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')

# Search API choice — set to 'serper' or 'google_cse'
SEARCH_API = os.environ.get('FB_SEARCH_API', 'serper')
SERPER_KEY = os.environ.get('SERPER_API_KEY', '')
GOOGLE_CSE_KEY = os.environ.get('GOOGLE_CSE_KEY', '')
GOOGLE_CSE_ID = os.environ.get('GOOGLE_CSE_ID', '')

# Rate limiting
PHASE1_DELAY = 0.5   # seconds between search API calls
PHASE2_DELAY = 2.0   # seconds between Facebook page fetches
PHASE2_WORKERS = 3    # low concurrency to avoid blocking

# Stats
stats = {'searched': 0, 'fb_found': 0, 'fb_error': 0,
         'scraped': 0, 'website_extracted': 0, 'phone_extracted': 0,
         'email_extracted': 0, 'scrape_errors': 0}
stats_lock = __import__('threading').Lock()


# ── Search API (Phase 1) ──

def search_for_facebook(name, city, state):
    """Search for church Facebook page using Serper or Google CSE.
    
    Returns Facebook page URL or None.
    """
    if SEARCH_API == 'serper' and SERPER_KEY:
        return _search_serper_facebook(name, city, state)
    elif SEARCH_API == 'google_cse' and GOOGLE_CSE_KEY and GOOGLE_CSE_ID:
        return _search_google_cse_facebook(name, city, state)
    else:
        # Fallback: name-based Facebook URL guessing
        return _guess_facebook_url(name, city, state)


def _search_serper_facebook(name, city, state):
    """Search for Facebook page via Serper API."""
    query = f'site:facebook.com "{name}" {city} {state} church'
    url = 'https://google.serper.dev/search'
    
    payload = json.dumps({
        'q': query,
        'num': 5,
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=payload,
        headers={
            'X-API-KEY': SERPER_KEY,
            'Content-Type': 'application/json',
        })
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        organic = data.get('organic', [])
        for item in organic:
            link = item.get('link', '')
            if 'facebook.com' in link and '/pages/' in link or '/profile.php' in link:
                return link
            # Filter common false positives
            if 'facebook.com' in link and not any(
                x in link for x in ['facebook.com/groups/', 'facebook.com/events/',
                                    'facebook.com/marketplace', 'facebook.com/login']
            ):
                return link
        
        return None
    except Exception as e:
        return None


def _search_google_cse_facebook(name, city, state):
    """Search for Facebook page via Google Custom Search."""
    query = urllib.parse.quote(f'site:facebook.com "{name}" {city} {state} church')
    url = (f'https://www.googleapis.com/customsearch/v1?key={GOOGLE_CSE_KEY}'
           f'&cx={GOOGLE_CSE_ID}&q={query}&num=5')
    
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        for item in data.get('items', []):
            link = item.get('link', '')
            if 'facebook.com' in link:
                return link
        return None
    except Exception:
        return None


def _guess_facebook_url(name, city, state):
    """Simple name-based Facebook URL guessing when no search API configured."""
    # Extract short name from church name
    short = name.lower()
    short = re.sub(r'\b(?:the\s+)?(?:church|baptist|methodist|presbyterian|lutheran|'
                   r'pentecostal|assembly|cathedral|chapel|ministry|ministries|temple|'
                   r'missionary|fellowship|community|outreach|international)\b', '', short)
    short = re.sub(r'[^a-z0-9\s]', '', short).strip()
    short = re.sub(r'\s+', '.', short)[:50]
    
    patterns = [
        f'https://www.facebook.com/{short}',
        f'https://www.facebook.com/{short}.{city.lower()}',
        f'https://www.facebook.com/pages/{short}/{city}',
    ]
    return patterns[0]  # Return best guess (unverified)


# ── Facebook About Page Scraper (Phase 2) ──

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/17.2',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0',
]


def scrape_facebook_about(facebook_url):
    """Scrape a public Facebook page's About section for contact info.
    
    Uses the mbasic.facebook.com (mobile basic) variant which is much
    more scrapeable than the main site. Falls back to the regular URL.
    
    Returns dict with: website, phone, email, or None for each.
    """
    result = {'website': None, 'phone': None, 'email': None}
    
    # Convert to mbasic URL for easier scraping
    mbasic_url = _to_mbasic_url(facebook_url)
    
    # Try mbasic first, fall back to regular
    for variant_url in [mbasic_url + '/about/', facebook_url + '/about']:
        content = _fetch_page(variant_url)
        if content:
            data = _parse_about_page(content)
            if any(data.values()):
                return data
    
    return result


def _to_mbasic_url(url):
    """Convert facebook.com URL to mbasic.facebook.com version."""
    url = url.replace('www.facebook.com', 'mbasic.facebook.com')
    url = url.replace('facebook.com', 'mbasic.facebook.com')
    # Remove URL parameters
    url = url.split('?')[0]
    return url.rstrip('/')


def _fetch_page(url, max_retries=2):
    """Fetch a page with rotating user agents and retry logic."""
    for attempt in range(max_retries + 1):
        ua = USER_AGENTS[hash(url + str(attempt)) % len(USER_AGENTS)]
        req = urllib.request.Request(url, headers={
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # Page not found
            time.sleep(1.0 * (attempt + 1))
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    return None


def _parse_about_page(html_content):
    """Parse HTML from Facebook mbasic/About page for contact info."""
    result = {'website': None, 'phone': None, 'email': None}
    
    text = html_content.lower()
    
    # ── Website extraction ──
    # Look for "Website" label followed by a link
    # Pattern 1: <a href="..." target="_blank"> in proximity to "Website"
    website_patterns = [
        r'website[:\s]*<a\s+href=["\'](https?://[^"\']+)["\']',
        r'<a\s+href=["\'](https?://[^"\']+)["\'][^>]*>\s*website\s*</a>',
        r'(?:website|site|web)[:\s]*(https?://[a-z0-9][-a-z0-9.]+\.[a-z]{2,}[^\s<]*)',
    ]
    
    for wp in website_patterns:
        m = re.search(wp, html_content, re.IGNORECASE)
        if m:
            url = m.group(1).rstrip('/').rstrip('.').strip()
            if 'facebook.com' not in url and len(url) > 10:
                result['website'] = url
                break
    
    # Also check for explicit link sections
    # On mbasic, website links are often in a "Website" row
    website_section = re.search(
        r'(?:website|site web|site)[:\s]*\n?\s*(https?://[^\s<>"\']+)',
        html_content, re.IGNORECASE
    )
    if website_section and not result['website']:
        url = website_section.group(1).rstrip('/').rstrip('.,')
        if 'facebook.com' not in url:
            result['website'] = url
    
    # ── Phone extraction ──
    # Look for phone numbers near "Phone" label
    phone_section = re.search(
        r'(?:phone|call|tel|mobile)[:\s]*\n?\s*([+]?\d[\d\s\-\.\(\)]{7,20}\d)',
        html_content, re.IGNORECASE
    )
    if phone_section:
        phone = phone_section.group(1).strip()
        # Normalize
        digits = re.sub(r'\D', '', phone)
        if len(digits) == 10:
            result['phone'] = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            result['phone'] = f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    
    # ── Email extraction ──
    # Look for email near "Email" label or generic email regex
    email_section = re.search(
        r'(?:email|e-mail|mail|contact)[:\s]*\n?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        html_content, re.IGNORECASE
    )
    if email_section:
        result['email'] = email_section.group(1).strip().lower()
    
    return result


# ── Database Operations ──

def get_churches_needing_fb(db, limit=0):
    """Get churches without website that could benefit from Facebook discovery."""
    query = """
        SELECT id, name, city, state
        FROM churches
        WHERE (website = '' OR website IS NULL)
          AND (facebook_url = '' OR facebook_url IS NULL)
          AND city != '' AND state != ''
        ORDER BY id
    """
    if limit:
        query += f" LIMIT {limit}"
    return db.execute(query).fetchall()


def get_churches_with_fb_urls(db, limit=0):
    """Get churches with Facebook URLs that need About page scraping."""
    query = """
        SELECT id, name, facebook_url
        FROM churches
        WHERE facebook_url != ''
          AND (website = '' OR phone = '' OR email = '')
        ORDER BY id
    """
    if limit:
        query += f" LIMIT {limit}"
    return db.execute(query).fetchall()


# ── Main ──

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Facebook Pivot — URL discovery + contact extraction')
    parser.add_argument('--find', action='store_true', help='Phase 1: Find Facebook URLs')
    parser.add_argument('--scrape', action='store_true', help='Phase 2: Scrape About pages')
    parser.add_argument('--pipeline', action='store_true', help='Full pipeline (find + scrape)')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--limit', type=int, default=0, help='Limit records to process')
    args = parser.parse_args()
    
    # Default: show help
    if not any([args.find, args.scrape, args.pipeline]):
        parser.print_help()
        sys.exit(0)
    
    db = sqlite3.connect(DB_PATH)
    
    if args.find or args.pipeline:
        print("=" * 60)
        print("PHASE 1: Facebook URL Discovery")
        print("=" * 60)
        
        churches = get_churches_needing_fb(db, args.limit)
        print(f"\nChurches needing Facebook discovery: {len(churches):,}")
        
        if args.dry_run:
            print("\n  [DRY RUN] Would search for these:")
            for r in churches[:10]:
                print(f"    {r['id']:>8d} | {r['name'][:45]:45s} | {r['city']:20s} {r['state']}")
            if len(churches) > 10:
                print(f"    ... and {len(churches) - 10:,} more")
        else:
            fb_updates = 0
            for i, row in enumerate(churches):
                name, city, state = row['name'], row['city'], row['state']
                
                fb_url = search_for_facebook(name, city, state)
                
                with stats_lock:
                    stats['searched'] += 1
                
                if fb_url:
                    db.execute("UPDATE churches SET facebook_url=? WHERE id=?", (fb_url, row['id']))
                    fb_updates += 1
                    with stats_lock:
                        stats['fb_found'] += 1
                    
                    if fb_updates % 50 == 0:
                        db.commit()
                        print(f"    Found {fb_updates:,} Facebook URLs so far...")
                
                # Rate limit
                if SEARCH_API != 'guess':
                    time.sleep(PHASE1_DELAY)
            
            db.commit()
            
            print(f"\n  Search complete:")
            print(f"    Queries: {stats['searched']:,}")
            print(f"    Facebook URLs found: {stats['fb_found']:,}")
            print(f"    Errors: {stats['fb_error']:,}")
    
    if args.scrape or args.pipeline:
        print("\n" + "=" * 60)
        print("PHASE 2: Facebook About Page Scraping")
        print("=" * 60)
        
        churches = get_churches_with_fb_urls(db, args.limit)
        print(f"\nChurches with Facebook URLs needing scraping: {len(churches):,}")
        
        if args.dry_run:
            print("\n  [DRY RUN] Would scrape these:")
            for r in churches[:10]:
                print(f"    {r['id']:>8d} | {r['name'][:45]:45s} | {r['facebook_url']}")
            if len(churches) > 10:
                print(f"    ... and {len(churches) - 10:,} more")
        else:
            def scrape_worker(row):
                church_id, name, fb_url = row['id'], row['name'], row['facebook_url']
                info = scrape_facebook_about(fb_url)
                
                updates = []
                if info['website']:
                    updates.append(('website', info['website']))
                    updates.append(('website_source', 'facebook_about'))
                    updates.append(('website_confidence', '0.60'))
                if info['phone']:
                    updates.append(('phone', info['phone']))
                    updates.append(('phone_source', 'facebook_about'))
                if info['email']:
                    updates.append(('email', info['email']))
                    updates.append(('email_source', 'facebook_about'))
                
                with stats_lock:
                    stats['scraped'] += 1
                    if info['website']:
                        stats['website_extracted'] += 1
                    if info['phone']:
                        stats['phone_extracted'] += 1
                    if info['email']:
                        stats['email_extracted'] += 1
                
                if updates:
                    return (church_id, updates)
                return None
            
            with ThreadPoolExecutor(max_workers=PHASE2_WORKERS) as executor:
                futures = {executor.submit(scrape_worker, r): r for r in churches}
                
                scrape_updates = 0
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        church_id, updates = result
                        parts = [f"{col}={json.dumps(val)}" for col, val in updates]
                        parts.append("last_updated=datetime('now')")
                        sql = f"UPDATE churches SET {', '.join(parts)} WHERE id=?"
                        db.execute(sql, (church_id,))
                        scrape_updates += 1
                    
                    if scrape_updates % 50 == 0 and scrape_updates > 0:
                        db.commit()
                    
                    time.sleep(PHASE2_DELAY)
            
            db.commit()
            
            print(f"\n  Scraping complete:")
            print(f"    Pages scraped: {stats['scraped']:,}")
            print(f"    Websites extracted: {stats['website_extracted']:,}")
            print(f"    Phones extracted: {stats['phone_extracted']:,}")
            print(f"    Emails extracted: {stats['email_extracted']:,}")
            print(f"    Errors: {stats['scrape_errors']:,}")
            
            # Log to provenance
            db.execute("""
                INSERT INTO provenance_log
                    (source, script_name, started_at, completed_at,
                     churches_updated, churches_inserted, fields_populated,
                     records_attempted, records_matched, status, notes)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, 'completed', ?)
            """, (
                'facebook_pivot',
                'facebook_pivot.py',
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                stats['website_extracted'] + stats['phone_extracted'] + stats['email_extracted'],
                'facebook_url,website,phone,email',
                stats['scraped'],
                stats['website_extracted'] + stats['phone_extracted'] + stats['email_extracted'],
                f'Phase 1: {stats["fb_found"]} FB URLs | Phase 2: {stats["website_extracted"]} websites, {stats["phone_extracted"]} phones, {stats["email_extracted"]} emails'
            ))
            db.commit()
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    if stats['searched']:
        print(f"  FB searches:       {stats['searched']:>8,}")
        print(f"  FB URLs found:     {stats['fb_found']:>8,}")
    if stats['scraped']:
        print(f"  Pages scraped:     {stats['scraped']:>8,}")
        print(f"  Websites found:    {stats['website_extracted']:>8,}")
        print(f"  Phones found:      {stats['phone_extracted']:>8,}")
        print(f"  Emails found:      {stats['email_extracted']:>8,}")
    
    db.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
