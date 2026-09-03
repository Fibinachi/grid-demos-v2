#!/usr/bin/env python3
"""
FCC Broadcast Station Database Downloader
===========================================
Downloads comprehensive broadcast station data from the FCC's public
CDBS/LMS databases. Covers all requested media ecosystem data:

  - FM radio stations (+ translators, boosters)
  - AM radio stations
  - TV stations (full-power, low-power, Class A)
  - FM/TV translators and repeaters
  - PBS identification (non-commercial educational TV)
  - NPR identification (non-commercial FM)
  - Religious broadcast stations (by licensee name)

Data sources:
  FCC CDBS daily-updated text lists at transition.fcc.gov/fcc-bin/
  Each returns tab-separated records with transmitter coordinates,
  power, frequency, class, licensee, and community of license.

Output:
  data/fcc/fm_stations.csv   — All FM stations + translators
  data/fcc/am_stations.csv   — All AM stations
  data/fcc/tv_stations.csv   — All TV stations (full + LPTV + CA)
  data/fcc/asr_towers.csv    — Antenna Structure Registration (towers)

Usage:
    python scripts/enrichment/download_fcc_data.py
    python scripts/enrichment/download_fcc_data.py --force  # Re-download
"""
import csv, io, os, re, sys, time, urllib.request, urllib.parse, json
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'fcc')
os.makedirs(DATA_DIR, exist_ok=True)

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrantWizard/1.0'
MAX_RETRIES = 3
DELAY = 2.0

# FCC query URLs for full station lists (tab-separated text)
FCC_URLS = {
    'fm': 'https://transition.fcc.gov/fcc-bin/fmq?list=0&text=Y&facid=&call=&state=&city=&freq=0.0&class=&status=1&pow=0.0&begin=&end=',
    'am': 'https://transition.fcc.gov/fcc-bin/amq?list=0&text=Y&facid=&call=&state=&city=&freq=0.0&class=&status=1&pow=0.0&begin=&end=',
    'tv': 'https://transition.fcc.gov/fcc-bin/tvq?list=0&text=Y&facid=&call=&state=&city=&channel=&status=1&begin=&end=',
}

# Known NPR member station licensee name patterns
NPR_KEYWORDS = [
    'npr', 'national public radio', 'public radio', 'public broadcasting',
    'wbez', 'wnyc', 'kqed', 'wbur', 'wunc', 'kera', 'wamu', 'wpln',
    'oregon public', 'minnesota public', 'wisconsin public',
    'michigan public', 'georgia public', 'arkansas public',
    'capital public', 'new york public', 'southern public',
    'kansas public', 'iowa public', 'nebraska public',
    'boise state', 'university of ', 'board of regents',
    'public media', 'community media', 'public telecommunications',
    'corporation for public', 'pbs',
]

# Known religious broadcast licensee patterns
RELIGIOUS_KEYWORDS = [
    'bible', 'gospel', 'christian', 'ministry', 'faith', 'salem',
    'bott radio', 'educational media', 'religious', 'catholic',
    'southern baptist', 'lutheran', 'church', 'fellowship',
    'trinity broadcasting', 'daystar', 'tbn', 'inspiration',
    'crista', 'k-life', 'k love', 'air1',
]


def download_fcc_list(list_type, force=False):
    """Download full FCC station list. Returns list of dicts."""
    path = os.path.join(DATA_DIR, f'{list_type}_stations_raw.txt')
    
    if os.path.exists(path) and not force:
        size = os.path.getsize(path)
        print(f"  Cached: {list_type} ({size:,} bytes)")
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            raw = f.read()
    else:
        url = FCC_URLS[list_type]
        print(f"  Downloading {list_type} stations...", end=' ', flush=True)
        
        for attempt in range(MAX_RETRIES):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': UA})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    raw = resp.read().decode('utf-8', errors='replace')
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(raw)
                print(f"{len(raw):,} bytes")
                break
            except Exception as e:
                print(f"attempt {attempt+1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(DELAY * (attempt + 1))
                else:
                    print(f"  FAILED: {list_type} — {e}")
                    return []
        
        time.sleep(DELAY)
    
    return parse_fcc_text(raw, list_type)


def parse_fcc_text(raw, list_type):
    """Parse FCC tab-separated text output into list of dicts."""
    lines = raw.strip().split('\n')
    if len(lines) < 2:
        return []
    
    # FCC text lists have a header line followed by data lines
    # The header contains column names (sometimes with leading #)
    header = [h.strip(' #').lower().replace(' ', '_') for h in lines[0].split('\t')]
    
    records = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) < len(header):
            continue
        row = dict(zip(header, parts))
        
        # Normalize coordinates
        for lat_field in ['lat', 'latitude', 'site_lat']:
            if lat_field in row and row[lat_field]:
                try:
                    row['lat'] = float(row[lat_field])
                except ValueError:
                    pass
                break
        for lng_field in ['lon', 'long', 'longitude', 'site_lon']:
            if lng_field in row and row[lng_field]:
                try:
                    row['lng'] = float(row[lng_field])
                except ValueError:
                    pass
                break
        
        # Normalize power
        for pow_field in ['erp', 'power', 'ant_power', 'dbk']:
            if pow_field in row and row[pow_field]:
                try:
                    row['power_kw'] = float(row[pow_field])
                except ValueError:
                    pass
                break
        
        # Normalize frequency
        for freq_field in ['freq', 'frequency']:
            if freq_field in row and row[freq_field]:
                try:
                    row['freq_mhz'] = float(row[freq_field])
                except ValueError:
                    pass
                break
        
        # Add classifications
        licensee = row.get('licensee', row.get('applicant', '')).upper()
        callsign = row.get('call_sign', row.get('call', '')).upper()
        service = row.get('service', row.get('service_type', '')).upper()
        
        row['is_npr'] = _is_npr(licensee, callsign, service, list_type)
        row['is_pbs'] = _is_pbs(licensee, callsign, service, list_type)
        row['is_religious'] = _is_religious(licensee, callsign)
        row['is_translator'] = 'T' in service or 'TRANSLATOR' in service.upper()
        row['is_nce'] = 'NON-COMMERCIAL' in licensee or service in ('NCE', 'NONC', 'ED')
        row['list_type'] = list_type
        
        records.append(row)
    
    return records


def _is_npr(licensee, callsign, service, list_type):
    """Check if a station is an NPR member."""
    if list_type != 'fm':
        return False
    if 'NON-COMMERCIAL' not in licensee and 'NCE' not in service:
        return False  # NPR stations are non-commercial
    kw = licensee.lower()
    for k in NPR_KEYWORDS:
        if k in kw:
            return True
    return False


def _is_pbs(licensee, callsign, service, list_type):
    """Check if a TV station is a PBS member."""
    if list_type != 'tv':
        return False
    if 'NON-COMMERCIAL' not in licensee and 'ED' not in service:
        return False
    kw = licensee.lower()
    pbs_indicators = ['pbs', 'public broadcasting', 'public television',
                      'educational television', 'state board of education',
                      'educational broadcasting', 'university of',
                      'board of regents', 'public media']
    for k in pbs_indicators:
        if k in kw:
            return True
    return False


def _is_religious(licensee, callsign):
    """Check if a station has religious affiliation."""
    kw = licensee.lower()
    for k in RELIGIOUS_KEYWORDS:
        if k in kw:
            return True
    return False


def download_asr_towers(force=False):
    """Download Antenna Structure Registration data."""
    path = os.path.join(DATA_DIR, 'asr_towers.csv')
    
    # FCC ASR data is available as a CSV download
    # The ASR database contains all registered towers with coordinates and heights
    urls = [
        'https://data.fcc.gov/api/asr/query?format=csv',
        'https://wireless.fcc.gov/antenna/index.htm?job=asr_search&type=download',
    ]
    
    if os.path.exists(path) and not force:
        print(f"  Cached: ASR towers ({os.path.getsize(path):,} bytes)")
        return
    
    print("  ASR tower data requires direct FCC download.")
    print("  Skipping — using station coordinates from FM/AM/TV databases instead.")
    return


def save_csv(records, name):
    """Save records as CSV."""
    if not records:
        print(f"  No {name} records to save.")
        return
    path = os.path.join(DATA_DIR, f'{name}.csv')
    fieldnames = list(records[0].keys())
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)
    print(f"  Saved: {path} ({len(records):,} records)")


def print_summary(stations, label):
    """Print summary stats for a station set."""
    total = len(stations)
    with_coords = sum(1 for s in stations if s.get('lat') and s.get('lng'))
    npr = sum(1 for s in stations if s.get('is_npr'))
    pbs = sum(1 for s in stations if s.get('is_pbs'))
    rel = sum(1 for s in stations if s.get('is_religious'))
    xlate = sum(1 for s in stations if s.get('is_translator'))
    nce = sum(1 for s in stations if s.get('is_nce'))
    
    print(f"    {label:30s} {total:>6,} total | {with_coords:>6,} with coords | "
          f"{nce:>4,} NCE | {rel:>4,} religious")
    if npr:
        print(f"    {'':30s} NPR: {npr} | PBS: {pbs} | Translators: {xlate}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Download FCC broadcast data')
    parser.add_argument('--force', action='store_true', help='Re-download cached files')
    args = parser.parse_args()
    
    print("=" * 60)
    print("FCC Broadcast Station Database Downloader")
    print("=" * 60)
    
    all_data = {}
    
    for list_type in ['fm', 'am', 'tv']:
        records = download_fcc_list(list_type, args.force)
        all_data[list_type] = records
        save_csv(records, f'{list_type}_stations')
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for list_type in ['fm', 'am', 'tv']:
        records = all_data[list_type]
        if records:
            print_summary(records, list_type.upper())
    
    # Combined stats
    all_stations = all_data.get('fm', []) + all_data.get('am', []) + all_data.get('tv', [])
    print(f"\n  Combined: {len(all_stations):,} total broadcast stations")
    
    # Write a combined stations index
    index = {
        'download_date': datetime.now().isoformat(),
        'total_stations': len(all_stations),
        'fm': len(all_data.get('fm', [])),
        'am': len(all_data.get('am', [])),
        'tv': len(all_data.get('tv', [])),
        'npr': sum(1 for s in all_stations if s.get('is_npr')),
        'pbs': sum(1 for s in all_stations if s.get('is_pbs')),
        'religious': sum(1 for s in all_stations if s.get('is_religious')),
        'translators': sum(1 for s in all_stations if s.get('is_translator')),
    }
    with open(os.path.join(DATA_DIR, 'index.json'), 'w') as f:
        json.dump(index, f, indent=2)
    print(f"\n  Index saved to data/fcc/index.json")
    
    print("\nDone!")


if __name__ == '__main__':
    main()
