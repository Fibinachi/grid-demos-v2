"""
Download GeoNames postal code files for key countries and integrate
into the centroid geocoder as Phase 1b (global postal code lookup).
"""
import urllib.request, os, sys, zipfile, io

BASE_URL = "https://download.geonames.org/export/zip/"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'geonames_postal')
os.makedirs(DATA_DIR, exist_ok=True)

# Countries we have records for, prioritized by count
COUNTRIES = [
    'CA',  # Canada — 6,941 remaining
    'IN',  # India — 4,915
    'IE',  # Ireland — 595
    'SG',  # Singapore — 70
    'MX',  # Mexico — 21
    'GB',  # UK
    'DE',  # Germany
    'FR',  # France
    'JP',  # Japan
    'AU',  # Australia
    'BR',  # Brazil
    'ES',  # Spain
    'IT',  # Italy
    'NL',  # Netherlands
    'CH',  # Switzerland
    'BE',  # Belgium
    'AT',  # Austria
    'SE',  # Sweden
    'NO',  # Norway
    'DK',  # Denmark
    'FI',  # Finland
    'PT',  # Portugal
    'PL',  # Poland
    'CZ',  # Czech Republic
    'NZ',  # New Zealand
    'ZA',  # South Africa
    'PH',  # Philippines
    'ID',  # Indonesia
    'TH',  # Thailand
    'MY',  # Malaysia
    'KR',  # South Korea
    'TR',  # Turkey
    'AR',  # Argentina
    'CL',  # Chile
    'CO',  # Colombia
    'PE',  # Peru
]

downloaded = 0
for cc in COUNTRIES:
    url = f"{BASE_URL}{cc}.zip"
    out_path = os.path.join(DATA_DIR, f"{cc}.zip")
    if os.path.exists(out_path):
        # Check if valid
        try:
            with zipfile.ZipFile(out_path) as zf:
                name = zf.namelist()[0]
                with zf.open(name) as f:
                    first = f.readline().decode('utf-8', errors='replace')
            print(f"  {cc}: already downloaded ({name})")
            downloaded += 1
            continue
        except:
            print(f"  {cc}: corrupt, re-downloading...")
            os.remove(out_path)
    
    try:
        print(f"  {cc}: downloading...", end=' ', flush=True)
        urllib.request.urlretrieve(url, out_path)
        # Verify
        with zipfile.ZipFile(out_path) as zf:
            name = zf.namelist()[0]
            with zf.open(name) as f:
                first = f.readline().decode('utf-8', errors='replace')
        size_kb = os.path.getsize(out_path) // 1024
        print(f"OK ({size_kb}KB, {name})")
        downloaded += 1
    except Exception as e:
        print(f"FAILED: {e}")
        if os.path.exists(out_path):
            os.remove(out_path)

print(f"\nDownloaded/verified: {downloaded}/{len(COUNTRIES)}")
