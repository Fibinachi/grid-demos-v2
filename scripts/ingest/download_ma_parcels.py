"""Download MA MassGIS statewide parcel data."""
import urllib.request, os, sys

DEST = r'E:\grid\data\sources\MA_parcels'
os.makedirs(DEST, exist_ok=True)

# Try FGDB first (7.9 GB, has full assessment data with USE_CODE)
url = 'https://s3.dualstack.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/gdbs/l3parcels/L3_AGGREGATE_FGDB_20260702.zip'
out = os.path.join(DEST, 'L3_AGGREGATE_FGDB_20260702.zip')

if os.path.exists(out):
    sz_gb = os.path.getsize(out) / (1024**3)
    print(f'ALREADY EXISTS: {sz_gb:.1f} GB')
    sys.exit(0)

print(f'Downloading MA MassGIS FGDB (~7.9 GB)...')
print(f'URL: {url}')
print(f'To: {out}')
print()

try:
    urllib.request.urlretrieve(url, out, reporthook=lambda n, bs, ts: 
        print(f'\r  {n*bs/(1024**3):.1f} / {ts/(1024**3):.1f} GB', end='', flush=True) if ts > 0 else None
    )
    print()
    sz_gb = os.path.getsize(out) / (1024**3)
    print(f'DONE: {sz_gb:.1f} GB')
except Exception as e:
    print(f'\nFAILED: {e}')
    # Try shapefile alternative
    url2 = 'https://s3.dualstack.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/l3parcels/L3_AGGREGATE_SHP_20260702.zip'
    out2 = os.path.join(DEST, 'L3_AGGREGATE_SHP_20260702.zip')
    print(f'Trying shapefile instead: {url2}')
    try:
        urllib.request.urlretrieve(url2, out2)
        sz_gb = os.path.getsize(out2) / (1024**3)
        print(f'DONE (shapefile): {sz_gb:.1f} GB')
    except Exception as e2:
        print(f'FAILED: {e2}')
