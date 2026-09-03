"""Deeper look at the page HTML for coordinates and structure."""
import requests, re, json
from bs4 import BeautifulSoup

r = requests.get('https://religiana.com/node/88', allow_redirects=True, timeout=10)
soup = BeautifulSoup(r.text, 'html.parser')

# Dump all img tags
print("=== IMG TAGS ===")
for i, img in enumerate(soup.find_all('img')):
    alt = img.get('alt', '')
    src = img.get('src', '')[:80]
    cls = img.get('class', [])
    print(f'  [{i}] alt="{alt}" class={cls} src={src}')

# Dump iframe tags
print("\n=== IFRAME TAGS ===")
for iframe in soup.find_all('iframe'):
    src = iframe.get('src', '')[:200]
    print(f'  src="{src}"')

# Check for script tags with lat/lng
print("\n=== SCRIPTS with coordinates ===")
for script in soup.find_all('script'):
    text = script.string or ''
    if 'lat' in text.lower() and ('lng' in text.lower() or 'lon' in text.lower()):
        # Extract lat/lng
        lat_match = re.search(r'lat["\']?\s*[:=]\s*([0-9.-]+)', text)
        lng_match = re.search(r'lng["\']?\s*[:=]\s*([0-9.-]+)', text)
        lng_match2 = re.search(r'lon["\']?\s*[:=]\s*([0-9.-]+)', text)
        print(f'  script with lat/lng found')
        if lat_match: print(f'    lat: {lat_match.group(1)}')
        if lng_match: print(f'    lng: {lng_match.group(1)}')
        if lng_match2: print(f'    lon: {lng_match2.group(1)}')

# Check for google_maps related divs
print("\n=== Google Maps divs ===")
for div in soup.find_all('div', class_=lambda c: c and ('google' in str(c).lower() or 'map' in str(c).lower() or 'marker' in str(c).lower())):
    print(f'  class={div.get("class")} id={div.get("id", "")}')
    data_attrs = {k: v for k, v in div.attrs.items() if k.startswith('data-')}
    if data_attrs:
        print(f'  data attrs: {data_attrs}')

# Check for hidden fields or form inputs with coordinates
print("\n=== Hidden inputs ===")
for inp in soup.find_all('input', type='hidden'):
    name = inp.get('name', '')
    val = inp.get('value', '')[:100]
    if 'lat' in name.lower() or 'lng' in name.lower() or 'lon' in name.lower() or 'coord' in name.lower():
        print(f'  {name} = {val}')
