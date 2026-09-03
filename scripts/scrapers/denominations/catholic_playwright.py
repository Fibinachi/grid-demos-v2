#!/usr/bin/env python3
"""
Playwright Catholic Diocese Scraper
====================================
Uses Playwright to scrape parish lists from Catholic diocese websites.
Handles JS-rendered content that HTTP-only scrapers can't reach.

Patterns handled:
- Select dropdowns with parish options (Bridgeport)
- WordPress parish archive pages
- List items with church names
- Map-based locators (basic)

Usage:
    python scripts/scrapers/denominations/catholic_playwright.py
    python scripts/scrapers/denominations/catholic_playwright.py --limit=10
    python scripts/scrapers/denominations/catholic_playwright.py --resume
"""
import csv, json, os, re, sys, time
from datetime import datetime
from pathlib import Path
from collections import Counter

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_CSV = DATA_DIR / "diocese_parishes_playwright.csv"
DIOCESE_JSON = DATA_DIR / "catholic_dioceses.json"
STATE_FILE = DATA_DIR / "diocese_playwright_state.json"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def main():
    dry_run = '--dry-run' in sys.argv
    resume = '--resume' in sys.argv
    limit = None
    for a in sys.argv:
        if a.startswith('--limit='):
            limit = int(a.split('=')[1])
    
    log('Playwright Catholic Diocese Scraper')
    
    # Load dioceses
    with open(DIOCESE_JSON) as f:
        all_dioceses = json.load(f)
    
    # Load existing results
    existing = []
    existing_urls = set()
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, encoding='utf-8') as f:
            existing = list(csv.DictReader(f))
        existing_urls = {r['parish_url'].lower().rstrip('/') for r in existing}
    log(f'Existing: {len(existing):,} entries')
    
    # Load state
    state = {'done': []}
    if STATE_FILE.exists() and resume:
        with open(STATE_FILE) as f:
            state = json.load(f)
    done_names = set(state.get('done', []))
    
    # Remaining dioceses: not done AND (no sitemap OR has_sitemap=false)
    remaining = [d for d in all_dioceses
                 if d['name'] not in done_names
                 and not d.get('has_sitemap')
                 and d.get('reachable')]
    
    # Sort by ease
    def sort_key(d):
        dir_score = 0 if d.get('has_dir_page') else 5
        cms = {'WordPress': 0, 'Drupal': 1, 'Joomla': 2, 'unknown': 3, 'React/Next.js': 4, 'Angular': 5}
        cms_score = cms.get(d.get('cms', 'unknown'), 3)
        return dir_score + cms_score
    
    remaining.sort(key=sort_key)
    
    if limit:
        remaining = remaining[:limit]
    
    log(f'Remaining to scrape: {len(remaining)}')
    
    # Import Playwright inside the function (after limit check, for speed)
    from playwright.sync_api import sync_playwright
    
    # Common parish directory URL paths to try
    DIR_PATHS = [
        '/parishes', '/parish', '/parish-locator', '/find-a-parish',
        '/parish-directory', '/our-parishes', '/churches',
        '/locations', '/find-a-church', '/church-directory',
        '/parish-finder', '/parish-search',
    ]
    
    all_new = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            locale='en-US',
        )
        
        for i, target in enumerate(remaining):
            diocese_name = target['name']
            website = target.get('website', '').strip()
            state = target.get('state', '')
            
            if not website:
                done_names.add(diocese_name)
                continue
            
            if not website.startswith('http'):
                website = 'https://' + website
            
            log(f'[{i+1}/{len(remaining)}] {diocese_name[:50]} ({state})')
            
            parishes = []
            page = None
            
            try:
                # Strategy 1: Try known directory paths
                base_domain = website.rstrip('/')
                found_dir = False
                
                for path in DIR_PATHS:
                    dir_url = base_domain + path
                    try:
                        page = context.new_page()
                        page.goto(dir_url, wait_until='domcontentloaded', timeout=15000)
                        page.wait_for_load_state('networkidle', timeout=5000).wait()
                        
                        # Check if page is valid (not 404)
                        title = page.title()
                        body_text = page.evaluate('() => document.body.innerText')
                        
                        if '404' in title or 'Not Found' in title or (body_text and 'not found' in body_text.lower()[:200]):
                            page.close()
                            page = None
                            continue
                        
                        found_dir = True
                        
                        # Pattern 1: <select> dropdown (Bridgeport style)
                        select_opts = page.evaluate('''() => {
                            const sel = document.querySelector('select');
                            if (!sel) return null;
                            const opts = [];
                            sel.querySelectorAll('option').forEach(o => {
                                const t = o.textContent.trim();
                                if (t && !t.includes('Select') && !t.includes('choose') && !t.includes('I am not'))
                                    opts.push(t);
                            });
                            return opts.length > 3 ? opts : null;
                        }''')
                        
                        if select_opts:
                            for opt in select_opts:
                                parts = opt.split(', ')
                                pname = parts[0]
                                pcity = parts[1] if len(parts) > 1 else ''
                                parishes.append({
                                    'diocese': diocese_name,
                                    'state': state,
                                    'parish_name': pname,
                                    'parish_url': dir_url,
                                    'diocese_url': website,
                                    'city': pcity,
                                    'source': 'playwright_select',
                                })
                            page.close()
                            page = None
                            break
                        
                        # Pattern 2: <article> or parish cards
                        cards = page.evaluate('''() => {
                            const results = [];
                            // Look for parish-like links in articles, list items, or divs
                            const items = document.querySelectorAll(
                                'article, [class*="parish"], [class*="location"], ' +
                                'li a, .entry-title a, h2 a, h3 a'
                            );
                            const seen = new Set();
                            items.forEach(el => {
                                const text = (el.textContent || '').trim();
                                const href = el.getAttribute && el.getAttribute('href') || '';
                                // Skip nav/menu links, short text
                                if (text.length > 10 && !text.includes('Home') && !text.includes('About') &&
                                    !text.includes('Contact') && !seen.has(text) &&
                                    (text.includes('Church') || text.includes('Parish') || 
                                     text.includes('St.') || text.includes('Our Lady') ||
                                     text.includes('Sacred Heart') || text.includes('Holy'))) {
                                    seen.add(text);
                                    results.push({name: text, url: href});
                                }
                            });
                            return results.length > 0 ? results : null;
                        }''')
                        
                        if cards and len(cards) < 200:  # Sanity check
                            for card in cards:
                                parishes.append({
                                    'diocese': diocese_name,
                                    'state': state,
                                    'parish_name': card['name'],
                                    'parish_url': card['url'] if card.get('url') else dir_url,
                                    'diocese_url': website,
                                    'city': '',
                                    'source': 'playwright_cards',
                                })
                            page.close()
                            page = None
                            break
                        
                        # Pattern 3: List items with church names in full body
                        list_items = page.evaluate('''() => {
                            const results = [];
                            const links = document.querySelectorAll('a[href]');
                            const seen = new Set();
                            links.forEach(a => {
                                const text = (a.textContent || '').trim();
                                const href = a.getAttribute('href') || '';
                                if (text.length > 10 && text.length < 100 &&
                                    !seen.has(text) &&
                                    (text.includes('Church') || text.includes('Parish') ||
                                     text.includes('St. ') || text.startsWith('Our Lady') ||
                                     text.startsWith('Sacred Heart') || text.startsWith('Holy')) &&
                                    !href.includes('#') && !href.includes('javascript') &&
                                    !text.includes('|') && !text.includes('»')) {
                                    seen.add(text);
                                    results.push({name: text, url: href});
                                }
                            });
                            return results.length > 0 && results.length < 300 ? results : null;
                        }''')
                        
                        if list_items:
                            for item in list_items:
                                parishes.append({
                                    'diocese': diocese_name,
                                    'state': state,
                                    'parish_name': item['name'],
                                    'parish_url': item['url'] if item['url'].startswith('http') else base_domain + item['url'],
                                    'diocese_url': website,
                                    'city': '',
                                    'source': 'playwright_links',
                                })
                            page.close()
                            page = None
                            break
                        
                        page.close()
                        page = None
                        
                    except Exception:
                        if page:
                            try: page.close()
                            except: pass
                            page = None
                        continue
                
                if not found_dir:
                    log(f'  No directory page found')
                
            except Exception as e:
                log(f'  Error: {str(e)[:80]}')
            
            # Deduplicate by parish name
            seen_names = set()
            unique = []
            for p in parishes:
                key = p['parish_name'].lower().strip()
                if key and key not in seen_names and len(key) > 5:
                    seen_names.add(key)
                    unique.append(p)
            
            # Filter new entries
            new_entries = []
            for p in unique:
                key = p['parish_url'].lower().rstrip('/')
                if key not in existing_urls:
                    existing_urls.add(key)
                    new_entries.append(p)
            
            log(f'  Found: {len(unique)}, New: {len(new_entries)}')
            all_new.extend(new_entries)
            
            # Save incrementally
            if not dry_run:
                combined = existing + all_new
                with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
                    w = csv.DictWriter(f, fieldnames=['diocese','state','parish_name','parish_url','diocese_url','city','source'])
                    w.writeheader()
                    w.writerows(combined)
                
                done_names.add(diocese_name)
                with open(STATE_FILE, 'w') as f:
                    json.dump({'done': list(done_names), 'total': len(combined),
                               'updated': datetime.now().isoformat()}, f, indent=2)
            
            time.sleep(1)  # Be respectful between sites
        
        browser.close()
    
    log(f'\n{"="*60}')
    log(f'New entries: {len(all_new):,}')
    log(f'Total in CSV: {len(existing) + len(all_new):,}')
    log(f'Dioceses done: {len(done_names)}')
    
    # Summary
    if all_new:
        by_diocese = Counter(p['diocese'] for p in all_new)
        log('\nBy diocese:')
        for d, n in by_diocese.most_common():
            log(f'  {n:>4} {d[:55]}')

if __name__ == '__main__':
    main()
