#!/usr/bin/env python3
"""
Progressive Catholic Diocese Scraper
=====================================
Scrapes remaining Catholic dioceses (no sitemap available) from smallest/easiest first.
Uses concurrent HTTP to find directory pages and extract parish listings.

Ranking by ease:
1. Reachable + has directory page (54 dioceses) — HTTP scrape first
2. Reachable, no directory page (36) — need Playwright
3. Unreachable (14) — Common Crawl / Wayback

Usage:
    python scripts/scrapers/denominations/catholic_progressive.py --resume
    python scripts/scrapers/denominations/catholic_progressive.py --limit=10
    python scripts/scrapers/denominations/catholic_progressive.py --dry-run
"""
import csv, json, os, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from collections import Counter

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
STATE_FILE = DATA_DIR / "diocese_scrape_state.json"
OUTPUT_CSV = DATA_DIR / "diocese_parishes.csv"
DIOCESE_JSON = DATA_DIR / "catholic_dioceses.json"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
MAX_WORKERS = 10

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ─── Fetching ─────────────────────────────────────────────────

def fetch(url, timeout=15):
    for attempt in range(2):
        try:
            r = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })
            with urllib.request.urlopen(r, timeout=timeout) as f:
                return f.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return None
            time.sleep(1)
        except:
            time.sleep(1)
    return None

# ─── Directory discovery ──────────────────────────────────────

def find_dir_links(html, base_url):
    if not html:
        return []
    links = []
    base_domain = urlparse(base_url).netloc.lower()
    dir_keywords = [
        (r'find[-\s]*(?:a\s+)?church', 'find-a-church'),
        (r'parish[-\s]*(?:locator|finder|directory|search)', 'parish-directory'),
        (r'(?:our\s+)?parishes', 'parishes'),
        (r'church\s+(?:directory|locator|finder|search)', 'church-directory'),
        (r'mass[-\s]*(?:times|finder|locator|schedule)', 'mass-times'),
        (r'location', 'locations'),
    ]
    for pat, label in dir_keywords:
        matches = re.findall(
            r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>.*?' + pat + r'.*?</a>',
            html, re.IGNORECASE | re.DOTALL
        )
        for href in matches:
            full_url = urljoin(base_url, href)
            if base_domain in urlparse(full_url).netloc.lower():
                links.append((full_url, label))
    # Also check nav
    nav_matches = re.findall(
        r'<nav[^>]*>.*?(?:<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>.*?(?:parish|directory|find|church|location).*?</a>).*?</nav>',
        html, re.IGNORECASE | re.DOTALL
    )
    for href in nav_matches:
        full_url = urljoin(base_url, href)
        if base_domain in urlparse(full_url).netloc.lower():
            links.append((full_url, 'nav'))
    return list(set(links))

# ─── Parish extraction ────────────────────────────────────────

def extract_parishes(html, base_url):
    if not html:
        return []
    parishes = []
    base_domain = urlparse(base_url).netloc.lower()
    seen = set()
    
    # JSON-LD
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get('@type') in ('CatholicChurch', 'Church', 'Place'):
                    name = item.get('name', '')
                    url = item.get('url', '')
                    if name:
                        parishes.append({'name': name, 'url': url})
        except:
            pass
    
    # Church name patterns
    patterns = [
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(St\.?\s+[A-Z][^<]{3,80}?)\s*</a>',
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Our\s+(?:Lady|Mother|Lord)\s+[^<]{3,80}?)\s*</a>',
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Holy\s+(?:Cross|Family|Trinity|Spirit|Name|Innocents|Rosary|Ghost|Redeemer)[^<]{3,80}?)\s*</a>',
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Sacred\s+Heart[^<]{0,50}?)\s*</a>',
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Immaculate\s+(?:Conception|Heart)[^<]{0,50}?)\s*</a>',
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Blessed\s+(?:Sacrament|Virgin)[^<]{0,50}?)\s*</a>',
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Christ\s+(?:the\s+)?King[^<]{0,50}?)\s*</a>',
    ]
    for pat in patterns:
        for m in re.finditer(pat, html, re.IGNORECASE):
            href, name = m.groups()
            full_url = urljoin(base_url, href.strip())
            name = re.sub(r'\s+', ' ', name.strip())
            key = (name.lower(), full_url.lower().rstrip('/'))
            if key not in seen and base_domain in urlparse(full_url).netloc.lower():
                seen.add(key)
                parishes.append({'name': name, 'url': full_url})
    
    # List items
    list_items = re.findall(
        r'<(?:li|div|tr)[^>]*class="[^"]*(?:parish|church|location)[^"]*"[^>]*>(.*?)</(?:li|div|tr)>',
        html, re.IGNORECASE | re.DOTALL
    )
    for item in list_items:
        link = re.search(r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>(.*?)</a>', item, re.DOTALL)
        if link:
            href, text = link.groups()
            text = re.sub(r'<[^>]+>', '', text).strip()
            full_url = urljoin(base_url, href)
            name = re.sub(r'\s+', ' ', text)[:100]
            key = (name.lower(), full_url.lower().rstrip('/'))
            if key not in seen and name and len(name) > 5 and base_domain in urlparse(full_url).netloc.lower():
                seen.add(key)
                parishes.append({'name': name, 'url': full_url})
    
    return parishes

# ─── Per-diocese scrape ───────────────────────────────────────

def scrape_one(target):
    url = target.get('website', '').strip()
    name = target.get('name', '')
    state = target.get('state', '')
    if not url:
        return {'target': name, 'state': state, 'status': 'no_url', 'parishes': 0, 'entries': []}
    if not url.startswith('http'):
        url = 'https://' + url
    
    html = fetch(url)
    if not html:
        return {'target': name, 'state': state, 'status': 'blocked', 'parishes': 0, 'entries': []}
    
    dir_links = find_dir_links(html, url)
    all_parishes = extract_parishes(html, url)
    
    for dir_url, label in dir_links[:3]:
        dir_html = fetch(dir_url)
        if dir_html:
            all_parishes.extend(extract_parishes(dir_html, dir_url))
        time.sleep(0.3)
    
    # Deduplicate
    seen = set()
    unique = []
    for p in all_parishes:
        key = p['url'].lower().rstrip('/')
        if key not in seen:
            seen.add(key)
            unique.append(p)
    
    # Build CSV rows
    entries = []
    for p in unique:
        entries.append({
            'diocese': name,
            'state': state,
            'parish_name': p['name'],
            'parish_url': p['url'],
            'diocese_url': url,
            'source': 'diocese_scrape',
        })
    
    return {
        'target': name,
        'state': state,
        'status': 'ok',
        'parishes': len(unique),
        'entries': entries,
    }

# ─── Main ─────────────────────────────────────────────────────

def main():
    dry_run = '--dry-run' in sys.argv
    resume = '--resume' in sys.argv
    limit = None
    for a in sys.argv:
        if a.startswith('--limit='):
            limit = int(a.split('=')[1])
    
    log(f'Catholic Diocese Progressive Scraper')
    
    # Load diocese data
    with open(DIOCESE_JSON) as f:
        all_dioceses = json.load(f)
    
    # Load state
    state = {'done': []}
    if STATE_FILE.exists() and resume:
        with open(STATE_FILE) as f:
            state = json.load(f)
    done_names = set(state.get('done', []))
    
    # Load existing results
    existing = []
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, encoding='utf-8') as f:
            existing = list(csv.DictReader(f))
    existing_urls = {r['parish_url'].lower().rstrip('/') for r in existing}
    
    # Remaining dioceses: not in scraped list AND no sitemap AND reachable
    remaining = [d for d in all_dioceses
                 if d['name'] not in done_names
                 and not d.get('has_sitemap')
                 and d.get('reachable')]
    
    # Sort: has directory page first, then by CMS simplicity
    def sort_key(d):
        dir_score = 0 if d.get('has_dir_page') else 5
        cms = {'WordPress': 0, 'Drupal': 1, 'Joomla': 2, 'unknown': 3, 'React/Next.js': 4, 'Angular': 5}
        cms_score = cms.get(d.get('cms', 'unknown'), 3)
        return dir_score + cms_score
    
    remaining.sort(key=sort_key)
    
    if limit:
        remaining = remaining[:limit]
    
    log(f'Remaining to scrape: {len(remaining)}')
    if remaining:
        log(f'First up: {remaining[0]["name"][:50]} ({remaining[0].get("state","")})')
    
    all_new = []
    for i, target in enumerate(remaining):
        log(f'\n[{i+1}/{len(remaining)}] {target["name"]} ({target.get("state","")}) CMS:{target.get("cms","?")}')
        
        result = scrape_one(target)
        log(f'  Status: {result["status"]}, Parishes: {result["parishes"]}')
        
        # Filter new entries
        new_entries = []
        for e in result.get('entries', []):
            key = e['parish_url'].lower().rstrip('/')
            if key not in existing_urls:
                existing_urls.add(key)
                new_entries.append(e)
        
        all_new.extend(new_entries)
        log(f'  New entries: {len(new_entries)}')
        
        # Save incrementally
        if not dry_run and result['entries']:
            combined = existing + all_new
            with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['diocese','state','parish_name','parish_url','diocese_url','source'])
                w.writeheader()
                w.writerows(combined)
            
            done_names.add(target['name'])
            with open(STATE_FILE, 'w') as f:
                json.dump({'done': list(done_names), 'total': len(combined),
                           'updated': datetime.now().isoformat()}, f, indent=2)
    
    log(f'\n{"="*60}')
    log(f'Complete! New entries this run: {len(all_new):,}')
    log(f'Total in CSV: {len(existing) + len(all_new):,}')
    log(f'Total dioceses done: {len(done_names)}')

if __name__ == '__main__':
    main()
