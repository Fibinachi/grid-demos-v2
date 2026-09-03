"""Download INEGI Marco Geoestadístico 2020 (Censo de Población y Vivienda)"""
import os
import sys
import requests
import zipfile
import io
import time

OUT_DIR = r'E:\grid\data\inegi_mg2020'
os.makedirs(OUT_DIR, exist_ok=True)

# Direct download URL for 2020 Census Geostatistical Framework
# From: https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/marcogeo/889463807469/889463807469_s.zip
URL = (
    'https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/'
    'bvinegi/productos/geografia/marcogeo/889463807469/889463807469_s.zip'
)
ZIP_PATH = os.path.join(OUT_DIR, 'mg2020.zip')
EXTRACT_DIR = os.path.join(OUT_DIR, 'extracted')

# Check if already downloaded
if os.path.exists(ZIP_PATH) and os.path.getsize(ZIP_PATH) > 2_000_000_000:
    print(f'ZIP already exists: {ZIP_PATH} ({os.path.getsize(ZIP_PATH)/1024/1024/1024:.2f} GB)')
    skip_download = True
elif os.path.exists(ZIP_PATH):
    print(f'Partial ZIP exists ({os.path.getsize(ZIP_PATH)/1024/1024:.0f} MB), will attempt resume')
    skip_download = False
else:
    skip_download = False

if not skip_download:
    print(f'Downloading INEGI Marco Geoestadístico 2020...')
    print(f'URL: {URL}')
    print(f'Output: {ZIP_PATH}')
    print(f'Estimated size: ~2.89 GB')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    # Try with resume support
    existing_size = os.path.getsize(ZIP_PATH) if os.path.exists(ZIP_PATH) else 0
    mode = 'ab' if existing_size > 0 else 'wb'
    if existing_size > 0:
        headers['Range'] = f'bytes={existing_size}-'
        print(f'  Resuming from byte {existing_size} ({existing_size/1024/1024:.0f} MB)')
    
    try:
        resp = requests.get(URL, headers=headers, stream=True, timeout=30)
        final_url = resp.url
        total = int(resp.headers.get('Content-Length', 0)) + existing_size
        print(f'  Final URL: {final_url}')
        print(f'  Total size: {total/1024/1024/1024:.2f} GB')
        
        if resp.status_code == 416:  # Range not satisfiable (already complete)
            print('  Range not satisfiable - file may already be complete')
        elif resp.status_code in (200, 206):
            downloaded = existing_size
            start = time.time()
            last_log = 0
            
            with open(ZIP_PATH, mode) as f:
                for chunk in resp.iter_content(chunk_size=1024*1024):  # 1 MB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        elapsed = time.time() - start
                        speed = downloaded / elapsed / 1024 / 1024 if elapsed > 0 else 0
                        
                        # Log progress every 10 seconds
                        if time.time() - last_log > 10:
                            pct = downloaded / total * 100 if total > 0 else 0
                            print(f'  Downloaded: {downloaded/1024/1024/1024:.2f} GB ({pct:.1f}%) @ {speed:.1f} MB/s')
                            last_log = time.time()
            
            elapsed = time.time() - start
            print(f'  Download complete: {downloaded/1024/1024/1024:.2f} GB in {elapsed/60:.1f} min')
        else:
            print(f'  HTTP {resp.status_code}: {resp.reason}')
            sys.exit(1)
    except Exception as e:
        print(f'  Download failed: {e}')
        sys.exit(1)
else:
    print('Using existing download.')

# Extract the ZIP
print(f'\nExtracting ZIP...')
os.makedirs(EXTRACT_DIR, exist_ok=True)

try:
    with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
        file_list = zf.namelist()
        print(f'  Files in ZIP: {len(file_list)}')
        
        # List top-level contents
        dirs = set()
        for name in file_list:
            parts = name.split('/')
            if len(parts) >= 2:
                dirs.add(parts[0])
        print(f'  Directories: {sorted(dirs)}')
        
        # Find AGEB-related files
        ageb_files = [f for f in file_list if 'ageb' in f.lower()]
        print(f'  AGEB-related files: {len(ageb_files)}')
        for f in sorted(ageb_files):
            print(f'    {f}')
        
        # Find shapefiles
        shp_files = [f for f in file_list if f.endswith('.shp')]
        print(f'\n  Shapefiles: {len(shp_files)}')
        for f in sorted(shp_files):
            print(f'    {f}')
        
        # Extract all
        print(f'\n  Extracting all files...')
        zf.extractall(EXTRACT_DIR)
        print(f'  Extracted to {EXTRACT_DIR}')
        
        # Show space used
        total_size = sum(os.path.getsize(os.path.join(EXTRACT_DIR, f)) 
                        for f in file_list 
                        if os.path.exists(os.path.join(EXTRACT_DIR, f)))
        print(f'  Total extracted size: {total_size/1024/1024/1024:.2f} GB')

except Exception as e:
    print(f'  Extraction failed: {e}')
    # If ZIP is broken, try listing
    if os.path.exists(ZIP_PATH):
        size = os.path.getsize(ZIP_PATH)
        print(f'  ZIP file size: {size/1024/1024/1024:.2f} GB')
        if size < 2_000_000_000:
            print('  ZIP is less than expected 2.89 GB - might be incomplete')
