"""Download Natural Earth 1:10m populated places with proper headers."""
import requests, zipfile, io, os

url = 'https://naciscdn.org/naturalearth/10m/cultural/ne_10m_populated_places.zip'
dst = 'data/natural_earth/ne_10m_populated_places.zip'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/zip,application/octet-stream,*/*'
}

print(f'Downloading Natural Earth 1:10m populated places...')
r = requests.get(url, headers=headers, timeout=120)
print(f'Status: {r.status_code}, Size: {len(r.content):,} bytes')

with open(dst, 'wb') as f:
    f.write(r.content)

# Extract CSV
z = zipfile.ZipFile(io.BytesIO(r.content))
csv_files = [f for f in z.namelist() if f.endswith('.csv')]
print(f'Files in zip: {z.namelist()[:5]}...')
if csv_files:
    z.extract(csv_files[0], 'data/natural_earth/')
    extracted = os.path.join('data/natural_earth', csv_files[0])
    renamed = 'data/natural_earth/ne_10m_populated_places.csv'
    if extracted != renamed:
        os.replace(extracted, renamed)
    print(f'Extracted to {renamed}')
z.close()
print('Done')
