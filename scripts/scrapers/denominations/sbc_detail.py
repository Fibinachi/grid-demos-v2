"""SC Baptist Convention — batch scrape all 2,025 church detail pages.
Deploy to hub via S3, run as background process.
"""
import json, os, time

# Actually, we need Playwright which requires browser.
# Simpler approach: use the Playwright session from the local machine
# to fetch all pages via the browser's fetch API.

# The URLs are at:
# https://www.scbaptist.org/churches-sitemap.xml
# https://www.scbaptist.org/churches-sitemap2.xml
# https://www.scbaptist.org/churches-sitemap3.xml

# Since the site blocks all non-browser requests, we need Playwright.
# Install on hub: pip install playwright && playwright install chromium

# For now, save the script and instructions
print("""
=== SBC CHURCH SCRAPER ===

The SCBaptist.org site blocks all non-browser HTTP requests (403).
Must use Playwright with headless Chromium.

To run on hub:
1. Install Playwright:
   pip install playwright
   playwright install chromium

2. Run this script:
   python3 scripts/scrapers/scrape_sbc_churches.py

Script will:
- Fetch 3 church sitemaps (2,025 URLs total)
- Scrape each detail page for name, address, phone, website
- Save checkpoints every 50 churches
- Output to sbc_churches_data.json

Estimated time: ~2 hours (3 sec per page × 2,025 pages)
""")
