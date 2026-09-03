#!/usr/bin/env python3
"""
Download Canada 2021 Census boundary files (Census Tracts + Dissemination Areas)
and later do spatial join with our ~79.5K Canadian church records.

Strategy:
1. Try the StatCan interactive form to get direct download URL
2. Fall back to Esri REST API queries
3. Or use the GeoJSON approach via WFS
"""

import requests
import zipfile
import os
import io
import time
import sys

OUT_DIR = r'E:\grid\data\canada_census'
os.makedirs(OUT_DIR, exist_ok=True)

# === Approach 1: Try to find direct download URLs ===
# The 2021 Census boundary naming convention:
# Cartographic: lct_000b21a_e (CT), lda_000b21a_e (DA)
# Digital: lct_000b21a_e (same pattern)

# Let's try various base URLs
base_urls = [
    'https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers',
    'https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites',
    'https://www12.statcan.gc.ca/census-recensement/2021/geo/ref',
    'https://www12.statcan.gc.ca/census-recensement/2021/geo/extdata',
]

# Well-known filenames from previous census years
filenames = [
    'lct_000b21a_e.zip',   # Census Tracts cartographic
    'lct_000b21a_f.zip',
    'lda_000b21a_e.zip',   # Dissemination Areas cartographic
    'lda_000b21a_f.zip',
    'lct_000a21a_e.zip',   # Alternative patterns
    'lda_000a21a_e.zip',
    'lct_000c21a_e.zip',
    'lda_000c21a_e.zip',
    'lct_000b21a_e.shp.zip',
    'lda_000b21a_e.shp.zip',
    'lct_021_a.zip',
    'lda_021_a.zip',
]

print("=== Trying direct URL patterns ===")
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

for base in base_urls:
    for fname in filenames:
        url = f"{base}/{fname}"
        try:
            r = session.head(url, allow_redirects=True, timeout=10)
            if r.status_code == 200:
                # Check if it's a zip by content-type or content-length > 1MB
                cl = int(r.headers.get('Content-Length', 0))
                ct = r.headers.get('Content-Type', '')
                if cl > 1000000 or 'zip' in ct or 'octet' in ct:
                    print(f'  ✅ FOUND: {url} ({cl:,} bytes)')
                else:
                    print(f'  ⚠️  Possible: {url} ({cl:,} bytes, {ct})')
            else:
                pass  # Silent on 404s
        except requests.RequestException as e:
            pass

# === Approach 2: Use the interactive form ===
print("\n=== Trying form submission ===")
form_url = 'https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/index2021-eng.cfm?year=21'

# First get the form to find hidden fields
r = session.get(form_url, timeout=30)
print(f'Form page status: {r.status_code}')
print(f'Form page size: {len(r.text):,} bytes')

# Look for the form action URL and fields
import re
# Find all form tags
form_pattern = re.compile(r'<form[^>]*action=["\']([^"\']+)["\']', re.IGNORECASE)
actions = form_pattern.findall(r.text)
print(f'Form actions found: {actions[:5]}')

# Look for input fields
input_pattern = re.compile(r'<input[^>]+name=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
inputs = input_pattern.findall(r.text)
print(f'Input fields: {inputs[:20]}')

# Look for select options
select_pattern = re.compile(r'<select[^>]+name=["\']([^"\']+)["\']', re.IGNORECASE)
selects = select_pattern.findall(r.text)
print(f'Select fields: {selects[:10]}')

# Look for download links in the page
download_pattern = re.compile(r'href=["\']([^"\']*\.zip[^"\']*|.*download[^"\']*)["\']', re.IGNORECASE)
downloads = download_pattern.findall(r.text)
print(f'Download links found: {downloads}')

# === Approach 3: Try GeoGratis / FTP ===
print("\n=== Trying FTP/GeoGratis ===")
ftp_urls = [
    'https://ftp.maps.canada.ca/pub/statcan_census/2021/boundary_files/lct_000b21a_e.zip',
    'https://ftp.maps.canada.ca/pub/statcan_census/2021/boundary_files/lda_000b21a_e.zip',
    'https://ftp.maps.canada.ca/pub/statcan_census/2021/geo/boundary_files/lct_000b21a_e.zip',
    'https://ftp.maps.canada.ca/pub/statcan/2021/boundary/lct_000b21a_e.zip',
]

for url in ftp_urls:
    try:
        r = session.head(url, allow_redirects=True, timeout=10)
        if r.status_code == 200:
            cl = int(r.headers.get('Content-Length', 0))
            print(f'  ✅ FOUND: {url} ({cl:,} bytes)')
        else:
            print(f'  ❌ {r.status_code}: {url}')
    except requests.RequestException as e:
        print(f'  ❌ Error: {url} - {e}')

# === Approach 4: Use the ArcGIS REST API ===
# We can query features from the MapServer
print("\n=== ArcGIS REST API endpoints ===")
rest_urls = [
    'https://geo.statcan.gc.ca/geo_wa/rest/services/2021/Cartographic_boundary_files/MapServer',
    'https://geo.statcan.gc.ca/geo_wa/rest/services/2021/Digital_boundary_files/MapServer',
]
for url in rest_urls:
    try:
        r = session.get(f'{url}?f=json', timeout=10)
        if r.status_code == 200:
            data = r.json()
            layers = data.get('layers', [])
            print(f'\n{url}:')
            for lyr in layers:
                print(f'  Layer {lyr["id"]}: {lyr["name"]} ({lyr["type"]})')
    except Exception as e:
        print(f'  ❌ {url}: {e}')

# === Approach 5: Try the WFS/WMS ===
print("\n=== WFS/WMS services ===")
wfs_url = 'https://geo.statcan.gc.ca/geo_wa/services/2021/Cartographic_boundary_files/MapServer/WMSServer'
try:
    r = session.get(f'{wfs_url}?request=GetCapabilities&service=WMS', timeout=15)
    if r.status_code == 200:
        # Look for layer names
        layers = re.findall(r'<Name>([^<]+)</Name>', r.text)
        print(f'WMS layers (first 20): {layers[:20]}')
except Exception as e:
    print(f'WMS error: {e}')

print("\nDone.")
