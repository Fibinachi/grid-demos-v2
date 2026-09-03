"""
Scrape South Korea's data.go.kr for all "Status of Religious Facilities" datasets
and import into churches.db.

Approach: Search the public data portal for "종교시설 현황" datasets,
download the CSV files, standardize, and import.

No API key needed — uses public download links.
"""
import sys, os, csv, io, re, time, json, urllib.request, urllib.parse
from pathlib import Path
from collections import Counter

sys.path.insert(0, r'E:\grid')
from gw_db import connect, Provenance

DATA_DIR = Path(r"E:\grid\data\korea_religious")
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHUNK_SIZE = 500

# Known dataset IDs on data.go.kr (will auto-discover, but seeding with known ones)
# These are the "Status of Religious Facilities" datasets published by municipalities
SEED_DATASETS = [
    # Format: (description, known_rows)
    # Yeosu-si (709 rows), Gimje-si (330 rows)
    # Will auto-discover more via search
]

# Korean province/city name mapping
PROVINCE_MAP = {
    '서울특별시': 'Seoul', '서울': 'Seoul',
    '부산광역시': 'Busan', '부산': 'Busan',
    '대구광역시': 'Daegu', '대구': 'Daegu',
    '인천광역시': 'Incheon', '인천': 'Incheon',
    '광주광역시': 'Gwangju', '광주': 'Gwangju',
    '대전광역시': 'Daejeon', '대전': 'Daejeon',
    '울산광역시': 'Ulsan', '울산': 'Ulsan',
    '세종특별자치시': 'Sejong', '세종': 'Sejong',
    '경기도': 'Gyeonggi-do', '경기': 'Gyeonggi-do',
    '강원도': 'Gangwon-do', '강원': 'Gangwon-do',
    '충청북도': 'Chungcheongbuk-do', '충북': 'Chungcheongbuk-do',
    '충청남도': 'Chungcheongnam-do', '충남': 'Chungcheongnam-do',
    '전라북도': 'Jeollabuk-do', '전북': 'Jeollabuk-do',
    '전라남도': 'Jeollanam-do', '전남': 'Jeollanam-do',
    '경상북도': 'Gyeongsangbuk-do', '경북': 'Gyeongsangbuk-do',
    '경상남도': 'Gyeongsangnam-do', '경남': 'Gyeongsangnam-do',
    '제주특별자치도': 'Jeju-do', '제주': 'Jeju-do',
}

# Religion classification mapping (Korean -> English)
RELIGION_MAP = {
    '개신교': 'Christian', '기독교': 'Christian', '基督敎': 'Christian',
    '천주교': 'Catholic', '카톨릭': 'Catholic', '가톨릭': 'Catholic',
    '불교': 'Buddhist', '佛敎': 'Buddhist',
    '원불교': 'Buddhist', '圓佛敎': 'Buddhist',
    '유교': 'Confucian', '儒敎': 'Confucian',
    '천도교': 'Other',
    '대순진리회': 'Other',
    '이슬람': 'Islam',
    '증산도': 'Other',
    '기타': 'Other',
}

LANDMARK_MAP = {
    '개신교': 'church', '기독교': 'church', '基督敎': 'church',
    '천주교': 'church', '카톨릭': 'church', '가톨릭': 'church',
    '불교': 'temple', '佛敎': 'temple',
    '원불교': 'temple', '圓佛敎': 'temple',
    '유교': 'shrine', '儒敎': 'shrine',
    '이슬람': 'mosque',
    '기타': 'other',
}

# Common address patterns to detect columns
ADDR_KW = ['address', 'addr', 'adres', '주소', '소재지', '위치', 'loc', 'location']
NAME_KW = ['name', 'nm', '시설명', '시설', 'facility', '명칭', '기관명', 'organization', 'org']
RELIGION_KW = ['religion', '종교', 'classification', '구분', '분류', '종별', 'relig']
PHONE_KW = ['phone', 'tel', '전화', '연락처', 'contact']
CITY_KW = ['city', 'city', '시군구', 'sgg', '지역', 'region', 'area']


def clean_korean_text(text):
    """Normalize Korean text encoding."""
    if not text:
        return ''
    text = text.strip()
    # Remove BOM and odd whitespace
    text = text.replace('\ufeff', '').replace('\u3000', ' ')
    return text


def detect_columns(headers):
    """Map CSV column names to standard field names."""
    mapping = {}
    
    for h in headers:
        h_lower = h.lower().strip()
        
        # Name
        if any(kw in h_lower for kw in ['시설명', '시설', '명칭', 'facility', '기관명']):
            if 'name' not in mapping:
                mapping['name'] = h
        if any(kw in h_lower for kw in ['name', 'nm']) and 'name' not in mapping:
            mapping['name'] = h
        
        # Religion
        if any(kw in h_lower for kw in ['종교', '종별', '구분', 'classification', '종류']):
            if 'religion' not in mapping:
                mapping['religion'] = h
        if h_lower in ('religion', 'relig') and 'religion' not in mapping:
            mapping['religion'] = h
        
        # Address
        if any(kw in h_lower for kw in ['주소', '소재지', '위치']):
            if 'address' not in mapping:
                mapping['address'] = h
        if any(kw in h_lower for kw in ['address', 'addr']) and 'address' not in mapping:
            mapping['address'] = h
        
        # Phone
        if any(kw in h_lower for kw in ['phone', 'tel', '전화', '연락처']):
            if 'phone' not in mapping:
                mapping['phone'] = h
        
        # City
        if any(kw in h_lower for kw in ['시군구', 'sgg', 'city']):
            if 'city' not in mapping:
                mapping['city'] = h
    
    return mapping


def search_datasets():
    """Search data.go.kr for '종교시설 현황' datasets."""
    print("Searching data.go.kr for religious facility datasets...")
    # This uses the public search page
    datasets = []
    
    search_urls = [
        f"https://www.data.go.kr/search/index.do?searchKeyword=종교시설+현황",
    ]
    
    print(f"  Manual search needed. Known datasets:")
    print(f"  - data.go.kr search for '종교시설 현황'")
    print(f"  - Look for 'Status of Religious Facilities' datasets")
    
    return datasets


def download_dataset(dataset_id, file_idx=0):
    """Download a CSV from data.go.kr by dataset file ID."""
    # Direct download URLs typically follow this pattern:
    # https://www.data.go.kr/data/{dataset_id}/fileData.do
    # Then scrape the file download link from the page
    
    info_url = f"https://www.data.go.kr/data/{dataset_id}/fileData.do"
    try:
        req = urllib.request.Request(info_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        
        # Look for CSV download links
        # Pattern: /download/{some_id}
        csv_links = re.findall(r'/download/(\d+)\.csv', html, re.I)
        if csv_links:
            dl_url = f"https://www.data.go.kr/download/{csv_links[0]}.csv"
            # Actually, need to follow redirect
            return dl_url
    except Exception as e:
        print(f"    Error fetching dataset {dataset_id}: {e}")
    
    return None


def parse_and_import(filepath, source_name):
    """Parse a Korean religious facility CSV and import to DB."""
    db = connect()
    
    # Detect encoding
    with open(filepath, 'rb') as f:
        raw = f.read(4096)
    
    encodings = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr', 'latin-1']
    rows = None
    
    for enc in encodings:
        try:
            f = io.StringIO(raw.decode(enc))
            # Try reading with different delimiters
            for delim in [',', ';', '\t']:
                f.seek(0)
                try:
                    reader = csv.DictReader(f, delimiter=delim)
                    sample = [r for _, r in zip(range(5), reader)]
                    if sample and len(sample[0]) >= 3:
                        rows = list(csv.DictReader(io.StringIO(raw.decode(enc)), delimiter=delim))
                        break
                except:
                    continue
            if rows:
                break
        except:
            continue
    
    if not rows or len(rows) == 0:
        print(f"    Could not parse CSV: {filepath.name}")
        return 0
    
    headers = list(rows[0].keys())
    col_map = detect_columns(headers)
    
    print(f"    Columns: {headers}")
    print(f"    Mapped: name={col_map.get('name','?')}, religion={col_map.get('religion','?')}, address={col_map.get('address','?')}")
    
    if not col_map.get('name'):
        print(f"    Skipping - cannot find name column")
        return 0
    
    # Get existing KR entries for dedup
    existing = set()
    cur = db.execute("SELECT name FROM churches WHERE country='KR'")
    for row in cur.fetchall():
        existing.add(row[0][:60])
    
    # Get max ID
    cur = db.execute("SELECT MAX(id) FROM churches")
    next_id = (cur.fetchone()[0] or 0) + 1
    
    new_entries = []
    skipped = 0
    for row in rows:
        name = clean_korean_text(row.get(col_map.get('name', ''), ''))
        if not name:
            skipped += 1
            continue
        
        # Dedup by name prefix
        if name[:60] in existing:
            skipped += 1
            continue
        
        religion_kr = clean_korean_text(row.get(col_map.get('religion', ''), ''))
        faith = RELIGION_MAP.get(religion_kr, 'Other')
        landmark = LANDMARK_MAP.get(religion_kr, 'other')
        
        address = clean_korean_text(row.get(col_map.get('address', ''), ''))
        city_kr = clean_korean_text(row.get(col_map.get('city', ''), ''))
        
        # Extract city from address if not separate column
        city_en = ''
        if city_kr:
            # Could be Korean city name
            pass
        
        new_entries.append({
            'name': name,
            'faith': faith,
            'landmark_type': landmark,
            'tradition': faith,
            'address': address,
            'city': city_kr,
            'country': 'KR',
            'source': source_name,
        })
    
    if not new_entries:
        print(f"    No new entries to import ({skipped} skipped)")
        return 0
    
    print(f"    Importing {len(new_entries)} entries ({skipped} skipped)...")
    
    with Provenance(db, source=source_name, action="inserted",
                    fields="name,faith,tradition,landmark_type,city,country,source",
                    records_attempted=len(new_entries)) as prov:
        
        for i in range(0, len(new_entries), CHUNK_SIZE):
            batch = new_entries[i:i+CHUNK_SIZE]
            for e in batch:
                try:
                    db.execute("""
                        INSERT INTO churches
                            (id, name, faith, tradition, landmark_type, 
                             city, country, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        next_id, e['name'], e['faith'], e['tradition'],
                        e['landmark_type'], e['city'], e['country'], e['source']
                    ))
                    next_id += 1
                    prov.churches_inserted += 1
                except Exception as ex:
                    print(f"    Error: {e['name'][:30]} - {ex}")
            db.commit()
    
    return len(new_entries)


def main():
    print("=" * 60)
    print("KOREA RELIGIOUS FACILITIES IMPORTER")
    print("=" * 60)
    print()
    
    # Check for CSV files in data directory
    csv_files = sorted(DATA_DIR.glob("*.csv"))
    
    if not csv_files:
        print("No CSV files found in data/korea_religious/")
        print()
        print("To use this scraper:")
        print("1. Go to https://www.data.go.kr")
        print("2. Search for '종교시설 현황' (Status of Religious Facilities)")
        print("3. Download CSVs for each municipality")
        print("4. Place them in data/korea_religious/")
        print("5. Run this script again")
        print()
        print("Or download manually from these known datasets:")
        print("  - Yeosu-si: data.go.kr/data/15117487/fileData.do (709 rows)")
        print("  - Gimje-si: data.go.kr/data/15112898/fileData.do (330 rows)")
        print()
        print("Trying automated download from known dataset IDs...")
        
        # Try known dataset file IDs
        known_ids = [
            ("15117487", "korea_gov_yeosu"),  # Yeosu-si
            ("15112898", "korea_gov_gimje"),  # Gimje-si
        ]
        
        for ds_id, source in known_ids:
            print(f"\n  Downloading dataset {ds_id}...")
            dl_url = f"https://www.data.go.kr/data/{ds_id}/fileData.do"
            try:
                # First get the page to find the download link
                req = urllib.request.Request(dl_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    html = resp.read().decode('utf-8', errors='replace')
                
                # Look for download link patterns
                # Common pattern: href="/download/{number}/{filename}.csv"
                csv_links = re.findall(r'href="(/download/\d+/[^"]+\.csv)"', html, re.I)
                if csv_links:
                    full_url = f"https://www.data.go.kr{csv_links[0]}"
                    print(f"    Found CSV link: {csv_links[0]}")
                    
                    local_path = DATA_DIR / f"{source}.csv"
                    urllib.request.urlretrieve(full_url, local_path)
                    print(f"    Downloaded to {local_path}")
                    csv_files.append(local_path)
                else:
                    print(f"    No CSV download link found on page")
            except Exception as e:
                print(f"    Error: {e}")
    
    if not csv_files:
        print("\nNo data to import. Please download CSVs manually.")
        return
    
    total_imported = 0
    for csv_file in csv_files:
        print(f"\nProcessing: {csv_file.name}")
        source_name = f"korea_gov_{csv_file.stem[:20]}"
        imported = parse_and_import(csv_file, source_name)
        total_imported += imported
    
    print(f"\n{'='*60}")
    print(f"Total imported: {total_imported}")
    
    # Final count
    db = connect()
    kr_total = db.execute("SELECT COUNT(*) FROM churches WHERE country='KR'").fetchone()[0]
    print(f"Total KR entries: {kr_total:,}")
    db.close()


if __name__ == '__main__':
    main()
