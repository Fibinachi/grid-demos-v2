"""
Website Email Searcher
======================
For each org with a website, visits the site and searches ALL pages
for email addresses. More thorough than the existing scraper:

1. Visits homepage, extracts all internal links
2. Follows contact/about/team/staff/board/leadership pages
3. Searches every page HTML for ANY email pattern
4. Also catches obfuscated emails (name [at] domain [dot] com)
5. Scores/filters results to avoid junk

Usage:
  python website_email_searcher.py --input churches.csv --website-col website --name-col church_name --output church_emails.csv --workers 20
  python website_email_searcher.py --input foundations_tier1_10m_plus.csv --website-col DOMAIN --name-col NAME --output tier1_emails.csv --workers 30
"""
import csv
import os
import re
import sys
import time
import random
import json
import hashlib
import threading
import urllib.request
import urllib.parse
import urllib.error
import socket
import ssl
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Config ──
TIMEOUT = 15           # seconds per page request
MAX_PAGES = 15         # max pages to crawl per site
MAX_WORKERS = 10       # concurrent sites (keep low to avoid overwhelming servers)
SKIP_IMG = True        # skip image/js/css URLs

# Common pages to try (in priority order)
COMMON_PATHS = [
    '/', '/contact', '/contact-us', '/about', '/about-us',
    '/team', '/staff', '/leadership', '/board', '/board-of-directors',
    '/our-team', '/our-staff', '/meet-our-team', '/meet-the-team',
    '/people', '/who-we-are', '/ministry', '/pastor', '/pastors',
    '/staff-directory', '/church-staff', '/leadership-team',
    '/donate', '/give', '/support', '/get-involved', '/connect',
    '/grants', '/grant-seekers', '/apply', '/how-to-apply',
    '/news', '/events', '/blog', '/resources', '/faq',
]

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
]

SKIP_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico',
                   '.css', '.js', '.json', '.xml', '.pdf', '.doc', '.docx',
                   '.xls', '.xlsx', '.zip', '.tar', '.gz', '.mp4', '.mp3',
                   '.avi', '.mov', '.woff', '.woff2', '.ttf', '.eot'}

SKIP_PATHS = {'/cdn-cgi/', '/wp-content/', '/wp-includes/', '/wp-json/',
              '/wp-admin/', '/wp-login.php', '/css/', '/js/', '/images/',
              '/img/', '/assets/', '/static/', '/dist/', '/build/',
              '/uploads/', '/fonts/', '/node_modules/', '/api/', '/feed/',
              '/xmlrpc.php', '/trackback/', '/comment/', '/comments/'}

PERSONAL_DOMAINS = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
                    'aol.com', 'icloud.com', 'protonmail.com', 'mail.com',
                    'msn.com', 'live.com', 'ymail.com', 'zoho.com', 'yandex.com',
                    'gmx.com', 'fastmail.com', 'mail.ru', 'comcast.net',
                    'att.net', 'verizon.net', 'sbcglobal.net', 'bellsouth.net',
                    'earthlink.net', 'charter.net'}

# ── Email extraction ──
EMAIL_REGEX = re.compile(r'[\w.+-]+@[\w-]+\.\w{2,6}', re.IGNORECASE)

# Obfuscated email patterns: name [at] domain [dot] com
OBFUSCATED_RE = re.compile(
    r'([\w.+-]+)\s*\[?\s*(?:@|at|\[at\]|&#64;|%40)\s*\]?\s*([\w-]+)\s*\[?\s*(?:\.|dot|\[dot\]|&#46;)\s*\]?\s*(\w{2,4})',
    re.IGNORECASE
)

STATS_LOCK = threading_lock = None

def get_lock():
    global STATS_LOCK
    if STATS_LOCK is None:
        import threading
        STATS_LOCK = threading.Lock()
    return STATS_LOCK

stats = {'visited': 0, 'emails_found': 0, 'errors': 0, 'total': 0}

SKIP_DOMAIN_WORDS = {'href', 'location', 'prototype', 'replace', 'string',
                     'function', 'typeof', 'return', 'false', 'true', 'null',
                     'undefined', 'object', 'array', 'length', 'indexof',
                     'charat', 'substring', 'slice', 'split', 'join',
                     'button', 'class', 'style', 'display', 'inline',
                     'block', 'width', 'height', 'margin', 'padding',
                     'color', 'background', 'border', 'content', 'center',
                     'justify', 'align', 'flex', 'grid', 'column'}

def is_junk_email(email):
    """Filter out clearly junk/automated emails."""
    e = email.lower().strip()
    
    # Must have exactly one @
    if e.count('@') != 1: return True
    
    local, domain = e.split('@')
    
    # Local part must be at least 2 chars and start with a letter/digit
    if len(local) < 2: return True
    if not local[0].isalnum(): return True
    if not local[-1].isalnum(): return True
    
    # Domain must look like a real domain
    if len(domain) < 4: return True
    if domain.count('.') == 0: return True
    if domain.startswith('.') or domain.endswith('.'): return True
    
    # TLD must be a common valid TLD
    tld = domain.split('.')[-1]
    VALID_TLDS = {'com', 'org', 'net', 'edu', 'gov', 'mil', 'io', 'co', 'uk',
                  'ca', 'us', 'au', 'de', 'fr', 'jp', 'cn', 'ru', 'br', 'in',
                  'info', 'biz', 'tv', 'me', 'cc', 'ws', 'xyz', 'online',
                  'site', 'web', 'app', 'dev', 'cloud', 'ai', 'agency',
                  'foundation', 'church', 'org', 'ngo', 'charity',
                  'give', 'faith', 'ministry', 'today', 'team', 'live',
                  'life', 'care', 'help', 'world', 'global', 'international'}
    if tld not in VALID_TLDS:
        return True
    
    # Skip if local part is clearly not a real email (CSS classes, JS code)
    alpha_count = sum(c.isalnum() for c in local)
    if alpha_count < 2: return True
    
    # Skip if domain contains JS/CSS keywords
    domain_parts = re.split(r'[.\-]', domain)
    if any(w in domain_parts for w in SKIP_DOMAIN_WORDS):
        return True
    
    # Skip known junk patterns
    if any(x in e for x in ['.png', '.jpg', '.svg', '.css', '.js', '.json',
                             'sentry.', 'rspack@', 'react@', 'lodash@', 'webpack@',
                             'bundle@', 'chunk@', 'hot-update', 'sourcemap',
                             'example@', 'yourname', 'user@', 'domain.com',
                             'wordpress@', 'noreply@', 'no-reply@', 'donotreply@',
                             'unsubscribe@', 'bounce@', 'mailer-daemon@',
                             '.is-', '.has-', '.wp-', '.button']):
        return True
    
    return False

def extract_emails_from_html(html, base_domain):
    """Extract all emails from HTML content."""
    emails = set()
    
    # Plain email regex
    for m in EMAIL_REGEX.finditer(html):
        e = m.group(0).strip('.,;:()[]{}<>"\'/\\ \t\n\r').lower()
        if not is_junk_email(e) and '@' in e:
            edomain = e.split('@')[1]
            if edomain not in PERSONAL_DOMAINS:
                emails.add(e)
    
    # Mailto links
    for m in re.finditer(r'mailto:([^"\'<>\s]+)', html, re.IGNORECASE):
        e = m.group(1).strip().lower()
        if '@' in e and not is_junk_email(e):
            edomain = e.split('@')[1]
            if edomain not in PERSONAL_DOMAINS:
                emails.add(e)
    
    # Obfuscated: name [at] domain [dot] com
    for m in OBFUSCATED_RE.finditer(html):
        local = m.group(1).strip().lower()
        dom = m.group(2).strip().lower()
        tld = m.group(3).strip().lower()
        e = f"{local}@{dom}.{tld}"
        if not is_junk_email(e):
            edomain = e.split('@')[1]
            if edomain not in PERSONAL_DOMAINS:
                emails.add(e)
    
    return emails

def fetch_url(url):
    """Fetch a URL and return (html, error)."""
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            content = resp.read().decode('utf-8', errors='replace')
            return content, None
    except Exception as ex:
        return None, str(ex)

def extract_links(html, base_url, base_domain):
    """Extract internal links from HTML."""
    links = set()
    for m in re.finditer(r'href="([^"]+)"', html, re.IGNORECASE):
        href = m.group(1).strip()
        if not href or href.startswith('#') or href.startswith('javascript:'):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        
        # Must be same domain (or www. variant)
        host = parsed.netloc.lower().replace('www.', '')
        bd = base_domain.lower().replace('www.', '')
        if host != bd:
            continue
        
        path = parsed.path.lower()
        
        # Skip file extensions
        ext = os.path.splitext(path)[1].lower()
        if ext in SKIP_EXTENSIONS:
            continue
        
        # Skip known non-content paths
        skip = any(p in path for p in SKIP_PATHS)
        if skip:
            continue
        
        # Skip long paths (> 3 levels deep)
        depth = len([p for p in path.split('/') if p])
        if depth > 3:
            continue
        
        # Remove fragments, normalize
        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query and '=' in parsed.query:
            clean += '?' + parsed.query
        
        links.add(clean)
    
    return links

def score_email(email):
    """Score an email by quality (higher = better for outreach)."""
    e = email.lower()
    local = e.split('@')[0]
    
    score = 1
    
    # Staff/direct emails get higher scores
    if any(p in local for p in ['pastor', 'minister', 'reverend', 'fr.', 'father']):
        score = 10
    elif any(p in local for p in ['director', 'executive', 'president', 'ceo',
                                    'dean', 'chair', 'manager', 'admin']):
        score = 9
    elif any(p in local for p in ['grants', 'apply', 'proposals', 'program',
                                    'giving', 'donate', 'development']):
        score = 8
    elif any(p in local for p in ['contact', 'office', 'hello', 'welcome']):
        score = 5
    elif any(p in local for p in ['info', 'mail', 'webmaster', 'support']):
        score = 3
    elif '_' in local or '.' in local:
        # Probably a person's name (firstname.lastname)
        score = 7
    
    return score

def crawl_website(website_url, name):
    """Crawl a website and find all email addresses."""
    try:
        return _crawl(website_url, name)
    except Exception as ex:
        return [], str(ex)

def _crawl(website_url, name):
    """Internal crawl implementation."""
    # Normalize URL
    if not website_url.startswith('http'):
        website_url = 'https://' + website_url
    
    parsed = urlparse(website_url)
    base_domain = parsed.netloc.lower().replace('www.', '')
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    visited = set()
    all_emails = set()
    to_visit = [website_url]
    
    # Also add common paths
    for path in COMMON_PATHS:
        to_visit.append(base_url + path)
    
    pages_visited = 0
    
    while to_visit and pages_visited < MAX_PAGES:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)
        
        html, error = fetch_url(url)
        if not html:
            continue
        
        pages_visited += 1
        
        # Extract emails
        emails = extract_emails_from_html(html, base_domain)
        all_emails.update(emails)
        
        # Extract links for further crawling
        if pages_visited < MAX_PAGES:
            links = extract_links(html, url, base_domain)
            for link in links:
                if link not in visited and link not in to_visit:
                    to_visit.append(link)
    
    # Score and sort
    scored = [(score_email(e), e) for e in all_emails]
    scored.sort(key=lambda x: (-x[0], x[1]))
    
    return scored, None

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Website Email Searcher')
    parser.add_argument('--input', required=True, help='Input CSV')
    parser.add_argument('--website-col', default='website', help='Column with website URL')
    parser.add_argument('--name-col', default='name', help='Column with org name')
    parser.add_argument('--output', default='website_emails.csv', help='Output CSV')
    parser.add_argument('--workers', type=int, default=MAX_WORKERS, help='Concurrent workers')
    parser.add_argument('--start', type=int, default=0, help='Start row')
    parser.add_argument('--limit', type=int, default=0, help='Max rows to process')
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"❌ Input not found: {args.input}")
        return
    
    with open(args.input, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    if args.limit > 0:
        rows = rows[args.start:args.start + args.limit]
    elif args.start > 0:
        rows = rows[args.start:]
    
    print(f"📂 Loaded {len(rows)} rows from {args.input}")
    print(f"🌐 Searching websites for email addresses...")
    print()
    
    results = []
    processed = 0
    found_count = 0
    start = datetime.now()
    lock = threading.Lock()
    
    def process_one(r):
        nonlocal processed, found_count
        website = r.get(args.website_col, '').strip()
        name = r.get(args.name_col, '').strip()
        
        if not website:
            return None
        
        if not website.startswith('http'):
            website = 'https://' + website
        
        parsed = urlparse(website)
        domain = parsed.netloc.lower().replace('www.', '')
        
        scored_emails, error = crawl_website(website, name)
        
        with lock:
            processed += 1
            elapsed = (datetime.now() - start).total_seconds()
            rate = processed / elapsed * 3600 if elapsed > 0 else 0
            pct = processed / total * 100
            
            if scored_emails:
                found_count += 1
                best_score, best_email = scored_emails[0]
                sys.stdout.write(f"\r  [{processed}/{total}] {pct:4.0f}% {rate:.0f}/hr  {name[:35]:35s} ✅ {best_email}{' '*20}\n")
                sys.stdout.flush()
                return {
                    'name': name,
                    'website': website,
                    'domain': domain,
                    'best_email': best_email,
                    'best_score': best_score,
                    'all_emails': '; '.join([e for _, e in scored_emails[:10]]),
                }
            else:
                sys.stdout.write(f"\r  [{processed}/{total}] {pct:4.0f}% {rate:.0f}/hr  {name[:35]:35s} ❌{' '*20}\n")
                sys.stdout.flush()
                return None
    
    total = len(rows)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_one, r): r for r in rows if r.get(args.website_col, '').strip()}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    print()
    print(f"{'='*60}")
    print(f"  COMPLETE")
    print(f"{'='*60}")
    print(f"  Processed: {processed}")
    print(f"  Found emails: {found_count}")
    print(f"  Time: {datetime.now() - start}")
    
    # Save results (incrementally - append as they come)
    fieldnames = ['name', 'website', 'domain', 'best_email', 'best_score', 'all_emails']
    file_exists = os.path.exists(args.output)
    
    with open(args.output, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            w.writeheader()
        for result in results:
            w.writerow(result)
    
    print(f"  Saved: {args.output} ({len(results)} emails found)")
    
    # Also save a checkpoint for crash recovery
    ckpt = args.output + ".ckpt"
    with open(ckpt, 'w') as f:
        f.write(f"{total},{len(results)},{datetime.now().isoformat()}\n")

if __name__ == '__main__':
    main()
