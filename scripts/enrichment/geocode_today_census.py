"""
Geocode today's scrapes using Census batch geocoder (FREE, fast).
Uses the addressbatch endpoint with multipart CSV upload — up to 10,000 addresses per request.

Today's sources:
  pb_directory_import  1,076 ungeocoded (US, all with addresses)
  bma_directory        1,033 ungeocoded (US, all with addresses)
  clc_directory           71 ungeocoded (US, all with addresses)
  emc_scrape              74 ungeocoded (US, all with addresses)
  smc_playwright          64 ungeocoded (US, all with addresses)
  TOTAL: 2,318
"""
import csv
import io
import os
import sys
import time
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, Provenance

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BENCHMARK = "Public_AR_Current"
BATCH_SIZE = 5000  # Census allows up to 10,000 per call
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
    """Clean a value for CSV — strip commas, newlines."""
    if not val:
        return ""
    return str(val).replace(',', ' ').replace('\n', ' ').replace('\r', ' ').strip()


def build_csv_body(records):
    """Build CSV body for the Census addressbatch API.
    Format: id,street,city,state,zip (one per line, no header)
    """
    lines = []
    for rec in records:
        ch_id, address, city, state, zip5 = rec
        street = clean_csv(address)
        city_s = clean_csv(city)
        state_s = clean_csv(state)
        zip_s = clean_csv(zip5).split('-')[0].zfill(5) if zip5 else ""
        lines.append(f'{ch_id},"{street}","{city_s}","{state_s}",{zip_s}')
    return '\n'.join(lines)


def main():
    conn = connect()
    c = conn.cursor()

    # Gather all ungeocoded records from today's sources
    placeholders = ','.join('?' * len(SOURCES))
    c.execute(f"""
        SELECT id, address, city, state, zip5
        FROM churches
        WHERE source IN ({placeholders})
          AND (latitude IS NULL OR longitude IS NULL)
    """, SOURCES)
    rows = c.fetchall()
    print(f"Total ungeocoded from today's scrapes: {len(rows):,}")

    if not rows:
        print("Nothing to geocode.")
        conn.close()
        return

    total_batches = (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"  Batches: {total_batches} (batch size: {BATCH_SIZE})")

    geocoded = 0
    no_match = 0
    errors = 0
    updates = []

    for batch_num in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_num:batch_num + BATCH_SIZE]
        batch_idx = batch_num // BATCH_SIZE + 1

        csv_body = build_csv_body(batch)

        # Build multipart body
        mp_body = (
            f'--{BOUNDARY}\r\n'
            f'Content-Disposition: form-data; name="addressFile"; filename="batch_{batch_idx}.csv"\r\n'
            f'Content-Type: text/csv\r\n\r\n'
            f'{csv_body}\r\n'
            f'--{BOUNDARY}\r\n'
            f'Content-Disposition: form-data; name="benchmark"\r\n\r\n'
            f'{BENCHMARK}\r\n'
            f'--{BOUNDARY}--\r\n'
        ).encode('utf-8')

        try:
            req = urllib.request.Request(
                CENSUS_URL, data=mp_body,
                headers={'Content-Type': f'multipart/form-data; boundary={BOUNDARY}'}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                content = resp.read().decode('utf-8')
        except Exception as e:
            print(f"\n  Batch {batch_idx}/{total_batches}: API error: {e}")
            errors += len(batch)
            time.sleep(5)
            continue

        # Parse CSV response
        # Format: "id","address","match_type","matched_address","lon,lat","tiger_id","tiger_side"
        reader = csv.reader(io.StringIO(content))
        batch_ok = 0
        batch_fail = 0
        for line in reader:
            if len(line) >= 5:
                church_id = line[0].strip('"')
                match_type = line[2] if len(line) > 2 else ''
                coord_str = line[5] if len(line) > 5 else ''  # Index 5: "lon,lat"

                # Coordinates come as "lon,lat" in a single field
                if match_type in ('Match', 'Exact') and coord_str and ',' in coord_str:
                    try:
                        parts = coord_str.split(',')
                        lon = float(parts[0])
                        lat = float(parts[1])
                        if lat != 0 and lon != 0 and -90 <= lat <= 90 and -180 <= lon <= 180:
                            updates.append((lat, lon, int(church_id)))
                            geocoded += 1
                            batch_ok += 1
                        else:
                            no_match += 1
                            batch_fail += 1
                    except (ValueError, IndexError):
                        no_match += 1
                        batch_fail += 1
                else:
                    no_match += 1
                    batch_fail += 1

        print(f"\r  Batch {batch_idx}/{total_batches}: {batch_ok} matched, {batch_fail} no match | "
              f"Running: {geocoded:,} geocoded, {no_match:,} unmatched, {errors:,} errors", end="", flush=True)

        # Commit periodically
        if len(updates) >= DB_COMMIT_EVERY:
            with Provenance(conn, "geocode_today_census.py", source="census_batch",
                            action="enriched", fields="latitude,longitude"):
                c.executemany("""
                    UPDATE churches SET latitude=?, longitude=?
                    WHERE id=?
                """, updates)
                conn.commit()
            print(f"\n  [Committed {len(updates):,} updates]")
            updates = []

        # Rate limit
        time.sleep(2)

    # Final commit
    if updates:
        with Provenance(conn, "geocode_today_census.py", source="census_batch",
                        action="enriched", fields="latitude,longitude"):
            c.executemany("""
                UPDATE churches SET latitude=?, longitude=?
                WHERE id=?
            """, updates)
            conn.commit()
        print(f"\n  [Final commit: {len(updates):,} updates]")

    # Summary
    print(f"\n\n{'='*60}")
    print(f"RESULTS")
    print(f"  Geocoded:  {geocoded:,}")
    print(f"  No match:  {no_match:,}")
    print(f"  API errors:{errors:,}")

    # Check remaining
    c.execute(f"""
        SELECT COUNT(*) FROM churches
        WHERE source IN ({placeholders})
          AND (latitude IS NULL OR longitude IS NULL)
    """, SOURCES)
    remaining = c.fetchone()[0]
    print(f"  Remaining: {remaining:,} / {len(rows):,} ungeocoded")

    conn.close()


if __name__ == '__main__':
    main()


if __name__ == '__main__':
    main()
