#!/usr/bin/env python3
"""Scrape Michigan Churches of Christ directory from umich.edu/~sic.

Site blocks urllib — uses Playwright for fetching.
"""
import re, os, sys, json, urllib.parse, time
from playwright.sync_api import sync_playwright

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
URL = "https://websites.umich.edu/~sic/locate-mich.html"


def fetch_html():
    """Fetch page HTML using Playwright (umich blocks urllib)."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = ctx.new_page()
        page.goto(URL, wait_until='domcontentloaded', timeout=15000)
        page.wait_for_timeout(3000)
        html = page.content()
        ctx.close()
        browser.close()
    return html


def parse_churches(html):
    """Parse church entries from the Michigan locator page."""
    churches = []
    
    for m in re.finditer(
        r'<li[^>]*>\s*<a\s+href=[\'"]([^\'"]*map\.adp[^\'"]*)[\'"][^>]*>\s*([^<]+?)\s*</a>',
        html, re.I
    ):
        href = m.group(1)
        name = m.group(2).strip()
        
        # Parse address from MapQuest URL params (use html.unescape for &amp;)
        href = href.replace('&amp;', '&')
        parsed = urllib.parse.urlparse(href)
        params = urllib.parse.parse_qs(parsed.query)
        
        address = params.get('address', [''])[0].replace('+', ' ').strip()
        city = params.get('city', [''])[0].replace('+', ' ').strip()
        zipcode = params.get('zip', [''])[0].strip()
        state = 'MI'
        
        # Check for "More Info" link after this entry
        li_end = html.find('</li>', m.end())
        context = html[m.end():li_end] if li_end > 0 else ''
        website = ''
        more_m = re.search(r'<a\s+href=[\'"](https?://[^\'"]+)[\'"][^>]*>More\s+Info', context, re.I)
        if more_m:
            website = more_m.group(1)
        
        churches.append({
            'name': name,
            'address': address,
            'city': city,
            'state': state,
            'zip': zipcode,
            'website': website,
        })
    
    return churches


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('-o', '--output', default='')
    parser.add_argument('--import', dest='do_import', action='store_true')
    args = parser.parse_args()
    
    print(f'=== Michigan Churches of Christ Scraper ===')
    
    html = fetch_html()
    print(f'  Fetched {len(html):,} bytes')
    
    churches = parse_churches(html)
    print(f'\nTotal churches: {len(churches):,}')
    
    with_addr = sum(1 for c in churches if c.get('address'))
    with_web = sum(1 for c in churches if c.get('website'))
    print(f'With address: {with_addr:,}')
    print(f'With website: {with_web:,}')
    
    if churches:
        print(f'\nSamples:')
        for c in churches[:5]:
            print(f'  {c["name"][:50]:50s} | {c.get("address",""):30s} | {c["city"]:20s}')
    
    if args.output and churches:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(churches, f, indent=2)
        print(f'\nSaved to {args.output}')
    
    print('\nDone!')


if __name__ == '__main__':
    main()
