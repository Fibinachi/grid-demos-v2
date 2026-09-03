"""
FL DOR Religious Property Tax Exemption Pipeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Downloads all 67 FL county NAL files from DOR,
extracts religious tax-exempt parcels, exports to CSV.

Religious: DOR_UC in ('070','071') or EXMPT_09 > 0 with church-like owner.

Run: python scripts/enrichment/import_fl_dor.py
Output: data/fl_dor/fl_religious_parcels.csv
"""

import requests, zipfile, io, csv, time, sys
from pathlib import Path
from datetime import datetime

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; GRID/1.0)'}
OUT_DIR = Path('data/fl_dor')
OUT_DIR.mkdir(parents=True, exist_ok=True)

RELIGIOUS_DOR_UC = {'070', '071'}

RELIGIOUS_KW = [
    'CHURCH', 'TEMPLE', 'MOSQUE', 'SYNAGOG', 'MINISTR', 'DIOCESE',
    'PARISH', 'FELLOWSH', 'WORSHIP', 'CHAPEL', 'CONGREGAT', 'GOSPEL',
    'TABERNACL', 'MONASTERY', 'CATHEDRAL', 'BAPTIST', 'METHODIST',
    'PRESBYTER', 'LUTHERAN', 'PENTECOST', 'CATHOLIC', 'EPISCOPAL',
    'RELIGIOUS', 'HOLINESS', 'EVANGEL', 'GURDWARA', 'JEHOVAH',
    'KINGDOM HALL', 'ASSEMBLY OF GOD', 'SEVENTH DAY', 'COVENANT',
    'CALVARY', 'ZION', 'BETHEL', 'EMMANUEL', 'TRINITY',
    'OUR LADY', 'SACRED HEART', 'HOLY CROSS', 'HOLY FAMILY',
    'HOLY SPIRIT', 'HOLY TRINITY',
]

def discover_files():
    """Get all county NAL file URLs from SharePoint API."""
    api_url = (
        "https://floridarevenue.com/property/dataportal/_api/web/"
        "GetFolderByServerRelativeUrl("
        "'/property/dataportal/Documents/PTO Data Portal/"
        "Tax Roll Data Files/NAL/2025F'"
        ")/Files"
    )
    r = requests.get(api_url, headers={
        'Accept': 'application/json;odata=verbose', **HEADERS
    })
    r.raise_for_status()
    data = r.json()
    files = []
    for f in data['d']['results']:
        name = f['Name']
        if name.endswith('.zip') and 'Final NAL 2025' in name:
            url = f"https://floridarevenue.com{f['ServerRelativeUrl']}"
            county_name = name.replace(' Final NAL 2025.zip', '').strip()
            files.append((county_name, url))
    return files


def is_religious_owner(owner):
    return any(kw in owner.upper() for kw in RELIGIOUS_KW)


def process_county(county_name, url, writer):
    """Download and extract religious parcels from one county NAL file."""
    t0 = time.time()
    try:
        r = requests.get(url, headers=HEADERS, timeout=120)
        if r.status_code != 200:
            return 0, f"HTTP {r.status_code}"

        z = zipfile.ZipFile(io.BytesIO(r.content))
        csv_files = [n for n in z.namelist() if n.endswith('.csv')]
        if not csv_files:
            return 0, "No CSV in zip"

        data = z.read(csv_files[0]).decode('utf-8', errors='replace')
        reader = csv.reader(data.splitlines())
        header = next(reader)

        needed = {
            'parcel_id': 'PARCEL_ID', 'owner': 'OWN_NAME',
            'addr1': 'PHY_ADDR1', 'city': 'PHY_CITY', 'zip': 'PHY_ZIPCD',
            'just_value': 'JV', 'taxable_sd': 'TV_SD',
            'dor_uc': 'DOR_UC', 'ex09': 'EXMPT_09',
            'land_val': 'LND_VAL', 'living_area': 'TOT_LVG_AREA',
            'year_built': 'EFF_YR_BLT', 'buildings': 'NO_BULDNG',
        }
        col = {}
        for key, hdr in needed.items():
            if hdr in header:
                col[key] = header.index(hdr)

        religious = 0
        for row in reader:
            try:
                dor_uc = row[col['dor_uc']].strip() if 'dor_uc' in col else ''
                ex09_val = row[col['ex09']].strip() if 'ex09' in col else '0'
                owner = row[col['owner']].strip() if 'owner' in col else ''

                is_relig = (dor_uc in RELIGIOUS_DOR_UC)
                if not is_relig and ex09_val and ex09_val not in ('0', '0.0', ''):
                    is_relig = is_religious_owner(owner)

                if is_relig:
                    religious += 1
                    writer.writerow([
                        county_name,
                        row[col['parcel_id']].strip() if 'parcel_id' in col else '',
                        owner,
                        row[col['addr1']].strip() if 'addr1' in col else '',
                        row[col['city']].strip() if 'city' in col else '',
                        row[col['zip']].strip() if 'zip' in col else '',
                        row[col['just_value']].strip() if 'just_value' in col else '',
                        row[col['taxable_sd']].strip() if 'taxable_sd' in col else '',
                        dor_uc, ex09_val,
                        row[col['land_val']].strip() if 'land_val' in col else '',
                        row[col['living_area']].strip() if 'living_area' in col else '',
                        row[col['year_built']].strip() if 'year_built' in col else '',
                        row[col['buildings']].strip() if 'buildings' in col else '',
                    ])
            except (IndexError, ValueError):
                pass

        dt = time.time() - t0
        return religious, f"{religious:,} rel ({dt:.1f}s)"

    except Exception as e:
        return 0, f"ERROR: {e}"


def main():
    print("=" * 70)
    print("  FL DOR Religious Property Tax Exemption Pipeline")
    print("=" * 70)

    print("\n[1/3] Discovering county files...")
    files = discover_files()
    print(f"  Found {len(files)} county NAL files")

    csv_path = OUT_DIR / 'fl_religious_parcels.csv'
    f = open(csv_path, 'w', newline='', encoding='utf-8')
    writer = csv.writer(f)
    writer.writerow([
        'county', 'parcel_id', 'owner_name', 'phys_addr', 'phys_city',
        'phys_zip', 'just_value', 'taxable_value', 'dor_uc', 'exempt_09',
        'land_value', 'living_area_sqft', 'year_built', 'num_buildings'
    ])

    print(f"\n[2/3] Processing {len(files)} counties...")
    total = 0
    errors = []
    county_stats = []

    for i, (county_name, url) in enumerate(files):
        n, status = process_county(county_name, url, writer)
        total += n
        county_stats.append((county_name, n))
        if n == 0 and 'ERROR' in status:
            errors.append((county_name, status))

        pct = (i + 1) / len(files) * 100
        print(f"  [{i+1:2d}/{len(files)}] {county_name:25s} {n:>5,}  ({pct:.0f}%)")

        if i % 10 == 0:
            f.flush()

    f.close()

    print(f"\n[3/3] Summary")
    print(f"  {'='*50}")
    print(f"  Total religious parcels: {total:,}")
    print(f"  Output: {csv_path} ({csv_path.stat().st_size/1024/1024:.1f} MB)")

    if errors:
        print(f"\n  Errors ({len(errors)}):")
        for name, err in errors:
            print(f"    {name}: {err}")

    county_stats.sort(key=lambda x: x[1], reverse=True)
    print(f"\n  Top 15 counties:")
    for name, count in county_stats[:15]:
        print(f"    {name:25s} {count:>5,}")

    print(f"\n  Done at {datetime.now().strftime('%H:%M:%S')}")


if __name__ == '__main__':
    main()
