
"""Playwright scraper for ChurchStaffing.com, JustChurchJobs, MinistryJobs.
Extracts job listings: title, church name, city, state, URL, description.
Usage: python scripts/scrapers/scrape_church_jobs.py
"""
import json, os, re, sqlite3, sys, time
from datetime import datetime

# Will be imported if Playwright is available
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT, 'churches.db')

HEADLESS = '--headed' not in sys.argv

BOARDS = {
    'ChurchStaffing': {
        'url': 'https://www.churchstaffing.com/jobs',
        'selectors': {
            'container': '.job-listing, .job-card, article.job',
            'title': '.job-title, h2, h3 a',
            'church': '.church-name, .organization, .company',
            'location': '.location, .job-location',
            'link': '.job-title a, h2 a, h3 a',
            'description': '.job-description, .description, .summary',
        },
        'pagination': '.pagination a.next, .pagination .next-page, a[rel=next]',
    },
    'JustChurchJobs': {
        'url': 'https://www.justchurchjobs.com/jobs',
        'selectors': {
            'container': '.job-listing, .job-item, .listing',
            'title': '.job-title, h2, .title',
            'church': '.company, .organization, .church',
            'location': '.location, .job-location',
            'link': '.job-title a, h2 a',
            'description': '.description, .summary',
        },
        'pagination': '.pagination .next, a[rel=next]',
    },
    'MinistryJobs': {
        'url': 'https://www.ministryjobs.com/jobs',
        'selectors': {
            'container': '.job-listing, .job-item, .listing-card',
            'title': '.job-title, h2, .title',
            'church': '.company, .organization, .ministry',
            'location': '.location, .job-location',
            'link': '.job-title a, h2 a, .apply-link',
            'description': '.description, .summary, .excerpt',
        },
        'pagination': '.pagination .next, a[rel=next]',
    },
    'SBC': {
        'url': 'https://jobs.sbc.net/',
        'selectors': {
            'container': '.job_listing, .job-listing, article',
            'title': '.job_listing-title, h2, .title a, h3 a',
            'church': '.job_listing-company, .organization, .company',
            'location': '.job_listing-location, .location',
            'link': '.job_listing-title a, h2 a, h3 a',
            'description': '.job_listing-description, .description',
        },
        'pagination': '.pagination .next, a.next, .next-page a',
    },
    'GospelCoalition': {
        'url': 'https://www.thegospelcoalition.org/jobs/',
        'selectors': {
            'container': '.job-listing, .job-card, .listing-item, article',
            'title': '.job-title, h2, h3 a, .entry-title',
            'church': '.organization, .church-name, .company',
            'location': '.location, .job-location, .job-meta',
            'link': '.job-title a, h2 a, h3 a, .entry-title a',
            'description': '.description, .excerpt, .entry-content',
        },
        'pagination': '.pagination .next, a.next, .nav-next a',
    },
    'Vanderbloemen': {
        'url': 'https://www.vanderbloemen.com/jobs',
        'selectors': {
            'container': '.job-card, .position-listing, .search-result',
            'title': '.job-title, h2, h3, .position-title',
            'church': '.client-name, .organization, .church',
            'location': '.location, .job-location, .position-location',
            'link': 'a.job-link, .job-title a, h3 a',
            'description': '.description, .summary, .position-summary',
        },
        'pagination': '.pagination .next, a[rel=next], .load-more',
    },
    'SlingshotGroup': {
        'url': 'https://www.slingshotgroup.com/jobs',
        'selectors': {
            'container': '.job-card, .position, .listing-item',
            'title': '.position-title, h2, h3, .job-title',
            'church': '.church-name, .organization, .client',
            'location': '.location, .position-location',
            'link': '.position-title a, h2 a, h3 a, a.apply',
            'description': '.description, .summary, .position-details',
        },
        'pagination': '.pagination .next, a.next, .show-more',
    },
    'UMC': {
        'url': 'https://www.umc.org/en/content/church-careers',
        'selectors': {
            'container': '.job-item, .career-listing, article',
            'title': '.job-title, h2, h3, .title',
            'church': '.organization, .church, .conference',
            'location': '.location, .job-location',
            'link': '.job-title a, h2 a, h3 a',
            'description': '.description, .summary',
        },
        'pagination': '.pagination .next, a[rel=next]',
    },
    'PCA': {
        'url': 'https://pcaac.org/jobs/',
        'selectors': {
            'container': '.job-listing, .job-item, article',
            'title': '.job-title, h2, h3, .entry-title',
            'church': '.church-name, .organization',
            'location': '.location, .job-location',
            'link': '.job-title a, h2 a, .entry-title a',
            'description': '.description, .entry-content',
        },
        'pagination': '.pagination .next, a.next',
    },
    'LCMS': {
        'url': 'https://jobs.lcms.org/',
        'selectors': {
            'container': '.job-listing, .position, article',
            'title': '.job-title, h2, h3, .position-title',
            'church': '.organization, .church, .ministry',
            'location': '.location, .job-location',
            'link': '.job-title a, h2 a, h3 a',
            'description': '.description, .summary',
        },
        'pagination': '.pagination .next, a.next',
    },
    'CatholicJobs': {
        'url': 'https://www.catholicjobs.com/',
        'selectors': {
            'container': '.job-listing, .job-item, .listing',
            'title': '.job-title, h2, h3, .position-title',
            'church': '.diocese, .parish, .organization',
            'location': '.location, .job-location',
            'link': '.job-title a, h2 a, h3 a',
            'description': '.description, .summary',
        },
        'pagination': '.pagination .next, a.next',
    },
}

def log(msg):
    print(f"  {msg}", flush=True)

def scrape_board(page, board_name, config):
    """Scrape a single job board. Returns list of vacancy dicts."""
    log(f"\n  {board_name}: {config['url']}")
    page.goto(config['url'], wait_until='domcontentloaded', timeout=20000)
    page.wait_for_timeout(3000)
    
    all_jobs = []
    page_num = 1
    seen_titles = set()  # dedupe
    
    while True:
        # Extract jobs from page text as fallback
        page_text = page.inner_text('body')
        
        # Find job-like text blocks by looking for salary, pastor, church keywords
        # Split into paragraphs and find ones with job indicators
        paragraphs = [p.strip() for p in page_text.split('\n') if len(p.strip()) > 20]
        job_blocks = [p for p in paragraphs if any(
            kw in p.lower() for kw in ['pastor', 'minister', 'director', 'rector', 'priest',
                                         'worship leader', 'youth', 'children', 'church',
                                         'senior pastor', 'associate pastor'])
        ]
        
        # Try containers from selectors
        containers = []
        for sel in ['.job-listing', '.job_listing', 'article', '.card', '.listing-item',
                     '.row', '.job-card', '[class*=job]', '[class*=listing]', 'li']:
            try:
                found = page.query_selector_all(sel)
                if found and len(found) >= 3:
                    containers = found
                    break
            except: pass
        
        log(f"    Page {page_num}: {len(containers)} containers, {len(job_blocks)} text blocks")
        
        if containers:
            for container in containers:
                try:
                    text = container.inner_text()
                    title, church, location, link = '', '', '', ''
                    
                    # Extract title from first heading or strong text
                    for sel in ['h2', 'h3', 'h4', 'strong', '.title', '[class*=title]']:
                        el = container.query_selector(sel)
                        if el:
                            title = el.inner_text().strip()
                            link_el = el.query_selector('a')
                            if link_el: link = link_el.get_attribute('href') or ''
                            break
                    
                    if not title:
                        title = text.split('\n')[0].strip()[:100]
                    
                    # Extract church name
                    for sel in ['.company', '.organization', '.church-name', '[class*=church]',
                                '[class*=company]', '[class*=organization]']:
                        el = container.query_selector(sel)
                        if el:
                            church = el.inner_text().strip()
                            break
                    
                    # Extract location
                    for sel in ['.location', '.job-location', '[class*=location]']:
                        el = container.query_selector(sel)
                        if el:
                            location = el.inner_text().strip()
                            break
                    
                    # Get link
                    if not link:
                        a = container.query_selector('a')
                        if a: link = a.get_attribute('href') or ''
                    
                    # Parse city/state
                    city, state = '', ''
                    if location:
                        parts = [p.strip() for p in location.split(',')]
                        if len(parts) >= 2:
                            city = parts[0][:50]
                            state = parts[1].split()[0] if parts[1].split() else parts[1][:2]
                    
                    # Accept if has useful content
                    if title and len(title) > 5 and title not in seen_titles:
                        seen_titles.add(title)
                        # Fallback extraction if selectors didn't find church/city
                        if not church or not city:
                            fb_church, fb_city, fb_state = extract_church_from_text(title, text)
                            church = church or fb_church
                            city = city or fb_city
                            state = state or fb_state
                        addr, email, phone = extract_contact(text)
                        all_jobs.append({
                            'source': board_name, 'listing_url': link,
                            'job_title': title, 'church_name': church or '',
                            'city': city, 'state': state,
                            'details': text,
                            'contact_email': email,
                            'contact_phone': phone,
                            'extracted_address': addr,
                        })
                except: continue
        
        # If no containers found, use text blocks
        if not containers and job_blocks:
            for block in job_blocks[:50]:
                if block not in seen_titles:
                    seen_titles.add(block)
                    addr, email, phone = extract_contact(block)
                    all_jobs.append({
                        'source': board_name, 'listing_url': '',
                        'job_title': block[:200], 'church_name': '',
                        'city': '', 'state': '',
                        'details': block,
                        'contact_email': email,
                        'contact_phone': phone,
                        'extracted_address': addr,
                    })
        
        # Pagination
        next_link = None
        for sel in ([config['pagination']] if isinstance(config['pagination'], str) else config['pagination']):
            el = page.query_selector(sel)
            if el:
                try:
                    next_link = el
                    break
                except:
                    pass
        
        if not next_link or page_num >= 20:
            break
        
        try:
            next_link.click()
            page.wait_for_timeout(2000)
            page_num += 1
        except:
            break
    
    return all_jobs

# Address, email, phone extraction patterns
ADDR_RE = re.compile(
    r'(\d+\s+\w+(?:\s+\w+)*)\s+(?:Road|Rd|Street|St|Avenue|Ave|Blvd|Drive|Dr|Lane|Ln|Way|Ct|Court|Cir|Circle|Pl|Place|Hwy|Pkwy)'
    r'|(?:address|location|church\s+address)[:\s]*([^,.\n]{10,80})',
    re.IGNORECASE
)
EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE_RE = re.compile(r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}')

def extract_contact(text):
    """Extract address, email, phone from listing text."""
    addr, email, phone = '', '', ''
    m = ADDR_RE.search(text)
    if m:
        addr = (m.group(1) or m.group(2) or '').strip()
        if len(addr) < 10: addr = ''
    emails = EMAIL_RE.findall(text)
    for e in emails:
        if any(kw in e.lower() for kw in ['search', 'pastor', 'apply', 'job', 'hr', 'committee']):
            email = e; break
    if not email and emails: email = emails[0]
    phones = PHONE_RE.findall(text)
    phone = phones[0] if phones else ''
    return addr, email, phone

def extract_church_from_text(title, text):
    """Fallback: extract church name/location from title and text using patterns."""
    church, city, state = '', '', ''
    combined = f"{title} {text}"
    
    # Pattern: "Role – Church Name" or "Role at Church Name"
    m = re.search(r'(?:–|-|at|with)\s+([A-Z][\w\s\'.&(),-]{5,60}?)(?:,|\.|\s+in\s+|\s*$|\s+is\s+)', combined)
    if m:
        church = m.group(1).strip()
    
    # Pattern: church name followed by city/state
    if church:
        m2 = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}),\s*([A-Z]{2})\b', 
                       combined[combined.find(church):])
        if m2:
            city = m2.group(1)
            state = m2.group(2)[:2]
    
    # Pattern: standalone city, ST in text
    if not city:
        m3 = re.search(r'\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*([A-Z]{2})\b', combined)
        if m3:
            city = m3.group(1)
            state = m3.group(2)[:2]
    
    return church, city, state

def save_to_db(jobs, conn):
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    inserted = 0
    for job in jobs:
        try:
            c.execute("""INSERT OR IGNORE INTO church_vacancies 
                (source, listing_url, job_title, church_name, city, state,
                 details, contact_email, contact_phone, detected_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (job['source'], job.get('listing_url',''), job['job_title'],
                 job['church_name'], job.get('city',''), job.get('state',''),
                 job.get('details',''), job.get('contact_email',''),
                 job.get('contact_phone',''), now))
            if c.rowcount > 0:
                inserted += 1
                # Backfill church address if we got one
                addr = job.get('extracted_address','')
                if addr and job.get('church_name'):
                    c.execute("""UPDATE churches SET address=?, address_source='vacancy_listing'
                        WHERE name LIKE ? AND (address IS NULL OR address='') LIMIT 1""",
                        (addr, '%' + job['church_name'] + '%'))
        except: pass
    conn.commit()
    return inserted

def main():
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (job['source'], job['listing_url'], job['job_title'],
                  job['church_name'], job['city'], job['state'],
                  job['details'], now))
            if c.rowcount > 0:
                inserted += 1
        except:
            pass
    
    conn.commit()
    return inserted

def main():
    if not HAS_PLAYWRIGHT:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return
    
    log("=== Church Job Board Scraper ===")
    
    conn = sqlite3.connect(DB_PATH, timeout=60)
    
    # Ensure table exists
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS church_vacancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            church_id INTEGER REFERENCES churches(id),
            source TEXT NOT NULL,
            listing_url TEXT,
            source_url TEXT,
            job_title TEXT,
            church_name TEXT NOT NULL,
            city TEXT,
            state TEXT,
            confidence REAL DEFAULT 0.5,
            signal_type TEXT,
            details TEXT,
            contact_name TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            is_new_church INTEGER DEFAULT 0,
            detected_at TEXT NOT NULL,
            verified_at TEXT,
            UNIQUE(source, church_name, city, job_title)
        )
    """)
    conn.commit()
    
    total = 0
    
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)
        
        for board_name, config in BOARDS.items():
            page = browser.new_page()  # Fresh page per board
            page.set_default_timeout(20000)
            try:
                jobs = scrape_board(page, board_name, config)
                if jobs:
                    inserted = save_to_db(jobs, conn)
                    total += inserted
                    log(f"    Saved {inserted} new listings")
            except Exception as e:
                log(f"    Failed: {type(e).__name__}: {str(e)[:100]}")
            finally:
                page.close()
        
        browser.close()
    
    log(f"\nTotal new listings: {total}")
    
    # Now run the detection/classification on what we just scraped
    if total > 0:
        log("\nRunning classification on new listings...")
        # Try to match to existing churches
        c.execute("""
            UPDATE church_vacancies SET church_id = (
                SELECT c.id FROM churches c
                WHERE c.name LIKE '%' || church_vacancies.church_name || '%'
                  AND c.city = church_vacancies.city
                  AND c.state = church_vacancies.state
                LIMIT 1
            )
            WHERE church_id IS NULL AND church_name != ''
        """)
        matched = c.rowcount
        conn.commit()
        log(f"  Matched {matched} to existing churches")
        
        unmatched = c.execute("SELECT COUNT(1) FROM church_vacancies WHERE church_id IS NULL").fetchone()[0]
        log(f"  {unmatched} unmatched (potential new churches)")
    
    conn.close()
    log("Done.")

if __name__ == '__main__':
    main()
