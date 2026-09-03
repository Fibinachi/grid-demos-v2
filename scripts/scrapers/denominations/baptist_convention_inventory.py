"""
BAPTIST STATE CONVENTION SCRAPING INVENTORY
============================================
Results from checking ALL Baptist state convention sites for church directories.

ARCHITECTURE NOTE: For Playwright scrapers, place in scripts/scrapers/denominations/
and use the standard pattern: 
  playwright.sync_api for browser automation
  concurrent.futures for parallel processing
  1 browser per thread pattern (not shared)
  urllib.request for simple HTTP fetches
"""

# ===========================================================================
# ✅ COMPLETED / ALREADY SCRAPED
# ===========================================================================
ALREADY_SCRAPED = {
    # SBC State Conventions
    'Kentucky (kybaptist.org)': {
        'script': 'scripts/scrapers/denominations/scrape_ky_baptist.py',
        'records': 1526,
        'status': 'complete',
        'method': 'HTML (FacetWP WordPress)',
        'notes': '46 pages, ~2300 churches, ~30% lost to rate limiting'
    },
    
    # NBC (National Baptist Convention) 
    'Alabama NBC (alabamastatebaptist.org)': {
        'script': 'scripts/scrapers/denominations/scrape_nbc_pdfs.py',
        'records': 169,
        'status': 'complete',
        'method': 'PDF extraction (fitz)',
        'notes': '4 districts: NE(41), NW(37), SE(40), SW(51). District PDFs are scanned images.'
    },
    
    # National SBC directory (already done by other scripts)
    'SBC National Directory (sbc.net)': {
        'script': 'scripts/scrapers/scrape_sbc.py',
        'records': 30329,
        'status': 'complete', 
        'notes': 'National SBC directory'
    },
}

# ===========================================================================
# 📋 PLAYWRIGHT QUEUE - sites needing JS rendering for church directories
# ===========================================================================
PLAYWRIGHT_QUEUE = {
    # ✅ CONFIRMED CHURCH DIRECTORIES (via sitemap)
    'Alabama-SBC (alsbom.org)': {
        'url': 'https://alsbom.org/church-directory/',
        'type': '16 churches-directory sitemaps',
        'priority': 'HIGH - ~3,200 churches confirmed via sitemap',
        'sitemap': 'churches-directory-sitemap1..16.xml'
    },
    'Mississippi-SBC (mbcb.org)': {
        'url': 'https://www.mbcb.org/find-a-church/',
        'type': 'WordPress "church" post type',
        'priority': 'HIGH - 2 church sitemaps confirmed',
        'sitemap': 'church-sitemap.xml + church-sitemap2.xml'
    },
    'Virginia-SBCV (sbcv.org)': {
        'url': 'https://sbcv.org/churches/',
        'type': '888 churches in sitemap',
        'priority': 'HIGH - confirmed via sitemap',
        'sitemap': 'churches-sitemap.xml (888 URLs)'
    },
    'Florida (flbaptist.org)': {
        'url': 'https://flbaptist.org/find-a-church/',
        'type': '14 locations sitemaps',
        'priority': 'HIGH - confirmed via sitemap',
        'sitemap': 'locations-sitemap1..14.xml'
    },
    # 🔍 SEARCH FORMS (unconfirmed data - no church sitemaps)
    'Texas-SBTC (sbtexas.com)': {
        'url': 'https://sbtexas.com/churches/',
        'type': 'Search-based Find a Church - no church sitemap',
        'priority': 'MEDIUM - no churches in sitemap (posts, staff, events only)',
        'data_available': 'unknown'
    },
    'Texas-BGCT (texasbaptists.org)': {
        'url': 'https://texasbaptists.org/churches/',
        'type': 'Search form - no robots.txt or sitemap (404)',
        'priority': 'MEDIUM - site may be non-functional',
        'data_available': 'unknown'
    },
    'Georgia (gabaptist.org)': {
        'url': 'https://gabaptist.org/churches/',
        'type': 'No church sitemap found',
        'priority': 'MEDIUM'
    },
    'Tennessee (tnbaptist.org)': {
        'url': 'https://tnbaptist.org/churches/',
        'type': 'No church sitemap (posts, pages only)',
        'priority': 'MEDIUM'
    },
}

# ===========================================================================
# ❌ NOT AVAILABLE - sites checked, no church directory found
# ===========================================================================
NO_DIRECTORY = [
    'Louisiana (louisianabaptists.org) - /churches is about ministry resources',
    'South Carolina (scbaptist.org) - all dir paths redirect to homepage',
    'North Carolina (ncbaptist.org) - /find-a-church is just info page',
    'Missouri (mobaptist.org) - no directory found',
    'Oklahoma (oklahomabaptists.org) - no directory found',
    'Illinois (ibsa.org) - no directory found',
    'Maryland/DE (bcmd.org) - no directory found',
    'NW Baptist (nwbaptist.org) - no directory found',
    'Colorado (cmosc.org) - no directory found',
    'Montana (mtsbc.org) - no directory found',
    'Hawaii (hpbaptist.org) - no directory found',
    'Michigan (michiganbaptist.org) - no directory found',
    'Arkansas (absc.org) - no directory found',
    'Kansas/Nebraska (ksnbc.org) - unreachable',
    'New England (nebaptist.org) - no directory found',
    'Alaska (alaskasbc.com) - unreachable',
    'Arizona (azsbc.org) - unreachable',
    'California Southern (csbc.com) - unreachable',
    'Indiana (scbi.org) - unreachable',
    'Nevada (nevadabaptist.org) - unreachable',
    'New York (nysbsc.org) - unreachable',
    'West Virginia (wvsbc.org) - unreachable',
    'Wyoming (wyosbc.com) - unreachable',
    'Utah/Idaho (utahidahobaptist.org) - unreachable',
    'Dakotas (dakotasbaptist.org) - unreachable',
    'PA/S Jersey (baptistresource.org) - unreachable',
    'Ohio (scbo.org) - no directory',
]

if __name__ == '__main__':
    print('=== BAPTIST CONVENTION SCRAPING INVENTORY ===\n')
    print(f'Completed: {len(ALREADY_SCRAPED)}')
    print(f'Playwright Queue: {len(PLAYWRIGHT_QUEUE)}')
    print(f'No Directory: {len(NO_DIRECTORY)}')
    
    print('\n--- Playwright Queue (priority order) ---')
    for name, info in PLAYWRIGHT_QUEUE.items():
        print(f'\n{name}:')
        print(f'  URL: {info.get("url","")}')
        print(f'  Priority: {info.get("priority","")[:60]}')
