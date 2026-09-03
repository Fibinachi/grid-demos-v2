"""
Clean addresses and geocode remaining ungeocoded records from today's scrapes.
Phase 2: Address cleanup + Census batch geocode.
"""
import csv
import io
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, Provenance

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BENCHMARK = "Public_AR_Current"
BATCH_SIZE = 5000
BOUNDARY = "----CensusGeocoderBoundary98765"
DB_COMMIT_EVERY = 500

SOURCES = [
    'pb_directory_import',
    'bma_directory',
    'clc_directory',
    'emc_scrape',
    'smc_playwright',
]


def clean_csv(val):
    if not val:
        return ""
    return str(val).replace(',', ' ').replace('\n', ' ').replace('\r', ' ').strip()


def clean_address(addr):
    """Clean garbage from address field."""
    if not addr:
        return ""
    # Remove 🟡Fix GPS and similar markers
    addr = re.sub(r'[🟡🔴🟢🔵🟠🟣]\s*Fix\s*GPS', '', addr, flags=re.IGNORECASE)
    # Remove trailing garbage
    addr = re.sub(r'\s*\(?\s*Fix\s*GPS\s*\)?\s*$', '', addr, flags=re.IGNORECASE)
    # Clean up
    addr = addr.strip().strip(',').strip()
    # Collapse multiple spaces
    addr = re.sub(r'\s+', ' ', addr)
    return addr


def main():
    conn = connect()
    c = conn.cursor()

    # Phase 1: Clean addresses in DB
    placeholders = ','.join('?' * len(SOURCES))
    c.execute(f"""
        SELECT id, address FROM churches
        WHERE source IN ({placeholders})
          AND (latitude IS NULL OR longitude IS NULL)
          AND address IS NOT NULL
    """, SOURCES)
    dirty_rows = c.fetchall()
    
    cleaned = 0
    for ch_id, addr in dirty_rows:
        cleaned_addr = clean_address(addr)
        if cleaned_addr != addr:
            c.execute("UPDATE churches SET address=? WHERE id=?", (cleaned_addr, ch_id))
            cleaned += 1
    
    if cleaned:
        conn.commit()
        print(f"Cleaned {cleaned} addresses (removed 🟡Fix GPS etc.)")

    # Phase 2: Get remaining ungeocoded
    c.execute(f"""
        SELECT id, address, city, state, zip5
        FROM churches
        WHERE source IN ({placeholders})
          AND (latitude IS NULL OR longitude IS NULL)
    """, SOURCES)
    rows = c.fetchall()
    print(f"Remaining ungeocoded: {len(rows):,}")

    if not rows:
        conn.close()
        return

    # Build CSV body
    lines = []
    for rec in rows:
        ch_id, address, city, state, zip5 = rec
        street = clean_csv(clean_address(address))
        city_s = clean_csv(city)
        state_s = clean_csv(state)
        zip_s = clean_csv(zip5).split('-')[0].zfill(5) if zip5 else ""
        lines.append(f'{ch_id},"{street}","{city_s}","{state_s}",{zip_s}')

    csv_body = '\n'.join(lines)

    # Send to Census
    mp_body = (
        f'--{BOUNDARY}\r\n'
        f'Content-Disposition: form-data; name="addressFile"; filename="batch_clean.csv"\r\n'
        f'Content-Type: text/csv\r\n\r\n'
        f'{csv_body}\r\n'
        f'--{BOUNDARY}\r\n'
        f'Content-Disposition: form-data; name="benchmark"\r\n\r\n'
        f'{BENCHMARK}\r\n'
        f'--{BOUNDARY}--\r\n'
    ).encode('utf-8')

    print(f"Sending {len(rows)} records to Census batch geocoder...")
    
    try:
        req = urllib.request.Request(
            CENSUS_URL, data=mp_body,
            headers={'Content-Type': f'multipart/form-data; boundary={BOUNDARY}'}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            content = resp.read().decode('utf-8')
    except Exception as e:
        print(f"API error: {e}")
        conn.close()
        return

    # Parse response
    reader = csv.reader(io.StringIO(content))
    geocoded = 0
    no_match = 0
    updates = []

    for line in reader:
        if len(line) >= 6:
            church_id = line[0].strip('"')
            match_type = line[2] if len(line) > 2 else ''
            coord_str = line[5] if len(line) > 5 else ''

            if match_type in ('Match', 'Exact') and coord_str and ',' in coord_str:
                try:
                    parts = coord_str.split(',')
                    lon = float(parts[0])
                    lat = float(parts[1])
                    if lat != 0 and lon != 0 and -90 <= lat <= 90 and -180 <= lon <= 180:
                        updates.append((lat, lon, int(church_id)))
                        geocoded += 1
                    else:
                        no_match += 1
                except (ValueError, IndexError):
                    no_match += 1
            else:
                no_match += 1

    print(f"  Matched: {geocoded:,}")
    print(f"  No match: {no_match:,}")

    # Apply updates
    if updates:
        with Provenance(conn, "geocode_today_census.py", source="census_batch",
                        action="enriched", fields="latitude,longitude"):
            c.executemany("""
                UPDATE churches SET latitude=?, longitude=?
                WHERE id=?
            """, updates)
            conn.commit()
        print(f"  Applied {len(updates):,} coordinate updates")

    # Final check
    c.execute(f"""
        SELECT COUNT(*) FROM churches
        WHERE source IN ({placeholders})
          AND (latitude IS NULL OR longitude IS NULL)
    """, SOURCES)
    remaining = c.fetchone()[0]
    print(f"\n  Final remaining: {remaining:,} / {len(rows):,} ungeocoded")

    conn.close()


if __name__ == '__main__':
    main()
