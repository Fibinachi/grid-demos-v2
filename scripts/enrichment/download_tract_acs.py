#!/usr/bin/env python3
"""
Download ACS 5-Year Data at Census Tract Level
=================================================
Downloads ACS 5-year 2023 estimates at the census tract level for all
50 states + DC. This is the data that will be merged onto churches via
their 11-digit tract FIPS codes.

Why tract-level matters:
  County-level ACS treats entire counties uniformly. A church in a wealthy
  neighborhood of an otherwise poor county gets county-average poverty data.
  Tracts are ~4,000 people — hyper-local economic reality.

Data source: Census Bureau API (https://api.census.gov/data/2023/acs/acs5)
Variables: Same as county-level but at tract geography

API format for tracts:
    GET /data/2023/acs/acs5?get=NAME,B01001_001E,B19013_001E&for=tract:*&in=state:{fips}

This queries ALL tracts in a given state. For CA (30K churches) this returns
~8,000 tracts. Total US: ~74,000 tracts.

Usage:
    # Download all states
    python scripts/enrichment/download_tract_acs.py

    # Download specific states only
    python scripts/enrichment/download_tract_acs.py --states CA,TX,FL

    # Use Census API key (optional but faster for large queries)
    python scripts/enrichment/download_tract_acs.py --key YOUR_KEY

Output:
    data/census/acs_tract_2023.json — JSON array of tract records
    ~15MB file for all ~74K tracts

Requires: Nothing beyond stdlib
"""
import json, os, sys, time, urllib.request, ssl

# ── Config ──
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_DIR, 'data', 'census')
os.makedirs(DATA_DIR, exist_ok=True)

OUTPUT = os.path.join(DATA_DIR, 'acs_tract_2023.json')

ctx = ssl.create_default_context()

# ACS 5-year 2023 variables at tract level
# Same concept tables as county-level but queried per-tract
VARS = [
    "NAME",                    # Geographic name (e.g., "Census Tract 101, Los Angeles County, CA")
    "B01001_001E",             # Total population
    "B19013_001E",             # Median household income ($)
    "B17001_001E",             # Total poverty universe
    "B17001_002E",             # Income below poverty level
    "B15003_001E",             # Total pop 25+ (education universe)
    "B15003_022E",             # Bachelor's degree
    "B15003_023E",             # Master's degree
    "B15003_024E",             # Professional degree
    "B15003_025E",             # Doctorate degree
    "B23025_001E",             # Total employment universe
    "B23025_003E",             # Employed
    "B23025_005E",             # Unemployed
    "B25077_001E",             # Median home value ($)
    "B01002_001E",             # Median age
    "B02001_001E",             # Total race population
    "B02001_002E",             # White alone
    "B02001_003E",             # Black or African American alone
    "B02001_004E",             # American Indian / Alaska Native
    "B02001_005E",             # Asian alone
    "B02001_006E",             # Native Hawaiian / Pacific Islander
    "B03003_001E",             # Total Hispanic universe
    "B03003_003E",             # Hispanic or Latino
    "B25001_001E",             # Total housing units
    "B25002_001E",             # Total occupied/vacant universe
    "B25002_003E",             # Vacant housing units
    "B25003_001E",             # Total tenure universe
    "B25003_002E",             # Owner-occupied
    "B25003_003E",             # Renter-occupied
    "B19083_001E",             # Gini index (income inequality)
    "B17021_001E",             # Poverty by family type (universe)
    "B17021_002E",             # Families below poverty
]

# US state FIPS codes
STATES = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55",
    "WY": "56",
}

API_BASE = "https://api.census.gov/data/2023/acs/acs5"
CENSUS_KEY = os.environ.get('CENSUS_API_KEY', '')

stats = {'states_done': 0, 'tracts_total': 0, 'errors': 0}


def download_tracts_state(state_code, state_fips, api_key=''):
    """Download ACS tract data for a single state. Returns list of rows."""
    params = f"get=" + ",".join(VARS)
    params += f"&for=tract:*&in=state:{state_fips}"
    if api_key:
        params += f"&key={api_key}"
    
    url = f"{API_BASE}?{params}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GrantWizard/1.0'})
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        if len(data) < 2:
            print(f"    WARNING: Only {len(data)} rows returned (header + 0 data)")
            return []
        
        # Extract header and rows
        header = data[0]
        rows = data[1:]
        
        # Attach state/stusab for convenience
        for row in rows:
            row_dict = dict(zip(header, row))
            row_dict['state_abbr'] = state_code
            row_dict['state_fips'] = state_fips
            # Build 11-digit tract GEOID: state(2) + county(3) + tract(6)
            county = row_dict.get('county', '')
            tract = row_dict.get('tract', '')
            row_dict['geoid'] = f"{state_fips}{county}{tract}"
            all_results.append(row_dict)
        
        stats['tracts_total'] += len(rows)
        print(f"  {state_code:2s} ({state_fips}): {len(rows):,} tracts")
        return rows
    except urllib.error.HTTPError as e:
        print(f"  {state_code:2s} ({state_fips}): HTTP {e.code} — {e.reason}")
        stats['errors'] += 1
        return []
    except Exception as e:
        print(f"  {state_code:2s} ({state_fips}): ERROR — {e}")
        stats['errors'] += 1
        return []


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Download ACS tract-level data')
    parser.add_argument('--states', help='Comma-separated state abbreviations (default: all)')
    parser.add_argument('--key', help='Census API key (or set CENSUS_API_KEY env var)')
    parser.add_argument('--force', action='store_true', help='Re-download if cached')
    args = parser.parse_args()
    
    api_key = args.key or CENSUS_KEY
    if api_key:
        print(f"Using Census API key: {api_key[:8]}...{api_key[-4:]}")
    else:
        print("No API key — using public endpoint (still works, may be slower)")
    
    # Determine which states
    if args.states:
        state_list = [s.strip().upper() for s in args.states.split(',')]
    else:
        state_list = sorted(STATES.keys())
    
    print(f"\nDownloading ACS tract data for {len(state_list)} states...")
    print(f"Variables: {len(VARS)}")
    print(f"Output: {OUTPUT}")
    
    global all_results
    all_results = []
    
    for state_code in state_list:
        state_fips = STATES.get(state_code)
        if not state_fips:
            print(f"  {state_code}: Unknown state code, skipping")
            continue
        
        download_tracts_state(state_code, state_fips, api_key)
        
        # Rate limiting — Census API allows ~500 calls per key per sec
        # Without key, ~5 calls per second
        time.sleep(0.1 if api_key else 0.5)
    
    print(f"\nTotal tracts downloaded: {stats['tracts_total']:,}")
    print(f"Errors: {stats['errors']}")
    
    if all_results:
        # Write normalized JSON
        output = []
        for row in all_results:
            output.append(row)
        
        with open(OUTPUT, 'w') as f:
            json.dump(output, f, indent=2)
        
        size = os.path.getsize(OUTPUT)
        print(f"\nWritten to {OUTPUT}")
        print(f"Size: {size:,} bytes ({size/1024/1024:.1f} MB)")
        print(f"Records: {len(output):,}")
    
    print("\nDone!")


if __name__ == '__main__':
    all_results = []
    main()
