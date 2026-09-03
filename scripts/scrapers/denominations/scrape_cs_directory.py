"""
Scrape the Christian Science Directory (https://directory.christianscience.com/)
via its JSON API to get all Churches, Societies, Groups, and Reading Rooms
in the United States and Canada.

API: GET https://directory.christianscience.com/search_ads?country=X&page=N
Returns JSON: { total, pages, current_page, per_page, hits: [...] }

Output: CSV file suitable for import via import_scraper_outputs.py
"""

import json
import csv
import time
import sys
import urllib.request
import urllib.parse
import urllib.error
import ssl
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data', 'denom')
CSV_FILE = os.path.join(OUTPUT_DIR, 'christian_science_directory.csv')

API_BASE = 'https://directory.christianscience.com/search_ads'

# We want physical church locations: Churches/Societies and Reading Rooms
WANTED_TYPES = {'Churches/Societies', 'Reading Rooms'}

# Country filter — include Canada for future expansion
COUNTRIES = ['United States', 'Canada']

# SSL context for older Python
ctx = ssl.create_default_context()


def fetch_page(country: str, page: int) -> dict | None:
    """Fetch one page of results from the CS directory API."""
    url = f'{API_BASE}?country={urllib.parse.quote(country)}&page={page}&sort=relevance'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; GrantWizard/1.0)',
        'Accept': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f'  Error fetching page {page} for {country}: {e}')
        return None


def fetch_all(country: str) -> list[dict]:
    """Fetch all pages for a given country. Returns list of wanted hits."""
    all_hits = []
    page = 1

    data = fetch_page(country, page)
    if not data:
        return all_hits

    total = data.get('total', 0)
    pages = data.get('pages', 1)
    print(f'  Found {total} total results across {pages} pages for "{country}"')

    while True:
        if data and data.get('hits'):
            for hit in data['hits']:
                rtype = hit.get('journal_ad_type__c', '')
                if rtype in WANTED_TYPES:
                    all_hits.append(hit)
            kept = len([h for h in data['hits'] if h.get('journal_ad_type__c') in WANTED_TYPES])
            print(f'  Page {page}/{pages}: {len(data["hits"])} results, kept {kept} (total kept: {len(all_hits)})')
        else:
            print(f'  Page {page}/{pages}: no data')

        if page >= pages:
            break
        page += 1
        data = fetch_page(country, page)
        if not data:
            break

    return all_hits


def extract_row(hit: dict, country: str) -> dict:
    """Extract a flat dict from a hit for CSV output."""
    org_name = hit.get('ad_organization_name__c', '') or ''
    display_name = hit.get('ad_display_name', '') or ''
    rtype = hit.get('journal_ad_type__c', '') or ''

    # Build church name
    if rtype == 'Reading Rooms':
        # Reading Room entries: derive church name from city+state
        city = hit.get('primary_city__c', '') or ''
        state = hit.get('primary_state_province__c', '') or ''
        name = display_name if display_name else f'Reading Room, {city}'
        church_name = name
    else:
        # Churches/Societies
        city = hit.get('primary_city__c', '') or ''
        state = hit.get('primary_state_province__c', '') or ''
        if org_name:
            church_name = f'{org_name}, {city}' if org_name not in ('First Church', 'Society') else display_name
        else:
            church_name = display_name

    return {
        'name': church_name,
        'organization_name': org_name,
        'display_name': display_name,
        'type': rtype,
        'address': hit.get('primary_address_district__c', '') or '',
        'city': hit.get('primary_city__c', '') or '',
        'state': hit.get('primary_state_province__c', '') or '',
        'country': country,
        'phone': hit.get('primary_phone__c', '') or '',
        'email': hit.get('primary_email__c', '') or '',
        'latitude': hit.get('latitude', '') or '',
        'longitude': hit.get('longitude', '') or '',
        'path': hit.get('path', '') or '',
        'journal_ad_number': hit.get('journal_ad_number__c', '') or '',
    }


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_rows = []

    for country in COUNTRIES:
        print(f'\nFetching {country}...')
        hits = fetch_all(country)
        print(f'  Total kept for {country}: {len(hits)}')
        for hit in hits:
            all_rows.append(extract_row(hit, country))

    if not all_rows:
        print('\nNo results found!')
        sys.exit(1)

    # Write CSV
    fieldnames = [
        'name', 'organization_name', 'display_name', 'type',
        'address', 'city', 'state', 'country',
        'phone', 'email', 'latitude', 'longitude',
        'path', 'journal_ad_number',
    ]

    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    # Also write a summary
    types_count = {}
    for row in all_rows:
        t = row['type']
        types_count[t] = types_count.get(t, 0) + 1

    print(f'\n{"="*60}')
    print(f'CSV written to: {CSV_FILE}')
    print(f'Total records: {len(all_rows)}')
    for t, c in sorted(types_count.items()):
        print(f'  {t}: {c}')
    print(f'  US: {sum(1 for r in all_rows if r["country"] == "United States")}')
    print(f'  Canada: {sum(1 for r in all_rows if r["country"] == "Canada")}')


if __name__ == '__main__':
    main()
