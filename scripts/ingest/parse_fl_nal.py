"""
FL DOR NAL Parse + Filter + Geocode Pipeline
Phase 2: Extracts religious parcels from all 67 county NAL files,
         geocodes addresses via Census batch API, saves to CSV.
No DB import — output goes to E:\grid\data\fl_dor\fl_religious_parcels_2025.csv
"""
import csv, zipfile, os, sys, time, json, requests, io
from pathlib import Path
from urllib.parse import quote

# === Config ===
NAL_DIR = Path("E:/grid/data/fl_dor/nal/2025")
OUT_CSV = Path("E:/grid/data/fl_dor/fl_religious_parcels_2025.csv")
GEOCODE_BATCH_SIZE = 10000  # Census batch geocoder limit

# DOR Use Codes for religious (with category tags)
RELIGIOUS_USE_CODES = {
    "070": "church",
    "071": "parsonage",
    "072": "religious_auxiliary",
    "076": "cemetery",
}

def get_religious_category(row):
    """Return (category, True) if religious, else (None, False)."""
    duc = row.get("DOR_UC", "").strip()
    if duc in RELIGIOUS_USE_CODES:
        return RELIGIOUS_USE_CODES[duc]
    # Secondary: EXMPT_09 > 0
    ex09 = row.get("EXMPT_09", "").strip()
    if ex09 and ex09 != "0":
        return "other_exempt"
    return None

# Columns to extract
KEEP_COLS = [
    "CO_NO", "PARCEL_ID", "STATE_PAR_ID", "DOR_UC", "PA_UC",
    "JV", "AV_SD", "AV_NSD", "TV_SD", "TV_NSD",
    "LND_VAL", "TOT_LVG_AREA", "EFF_YR_BLT", "ACT_YR_BLT",
    "OWN_NAME", "PHY_ADDR1", "PHY_ADDR2", "PHY_CITY", "PHY_ZIPCD",
    "S_LEGAL", "NBRHD_CD", "MKT_AR", "NO_BULDNG", "NO_RES_UNTS",
    "EXMPT_01", "EXMPT_02", "EXMPT_03", "EXMPT_04", "EXMPT_05",
    "EXMPT_06", "EXMPT_07", "EXMPT_08", "EXMPT_09", "EXMPT_10",
]

# County FIPS mapping
COUNTY_FIPS = {
    "01": "12001", "11": "12001", "12": "12003", "13": "12005", "14": "12007",
    "15": "12009", "16": "12011", "17": "12013", "18": "12015", "19": "12017",
    "20": "12019", "21": "12021", "22": "12023", "23": "12086", "24": "12027",
    "25": "12029", "26": "12031", "27": "12033", "28": "12035", "29": "12037",
    "30": "12039", "31": "12041", "32": "12043", "33": "12045", "34": "12047",
    "35": "12049", "36": "12051", "37": "12053", "38": "12055", "39": "12057",
    "40": "12059", "41": "12061", "42": "12063", "43": "12065", "44": "12067",
    "45": "12069", "46": "12071", "47": "12073", "48": "12075", "49": "12077",
    "50": "12079", "51": "12081", "52": "12083", "53": "12085", "54": "12087",
    "55": "12089", "56": "12091", "57": "12093", "58": "12095", "59": "12097",
    "60": "12099", "61": "12101", "62": "12103", "63": "12105", "64": "12107",
    "65": "12109", "66": "12111", "67": "12113", "68": "12115", "69": "12117",
    "70": "12119", "71": "12121", "72": "12123", "73": "12125", "74": "12127",
    "75": "12129", "76": "12131", "77": "12133",
}

HEADERS_HTTP = {"User-Agent": "Mozilla/5.0"}

def progress_bar(current, total, width=40):
    pct = current / total if total else 0
    filled = int(width * pct)
    return f"[{'█'*filled}{'░'*(width-filled)}] {current}/{total} ({pct*100:.0f}%)"

def is_religious(row):
    """Check if this parcel is religious-use."""
    # Check DOR Use Code
    if row.get("DOR_UC", "").strip() in RELIGIOUS_USE_CODES:
        return True
    # Check exemption codes
    for code in RELIGIOUS_EXMPT_CODES:
        col = f"EXMPT_{code}"
        val = row.get(col, "").strip()
        if val and val != "0":
            return True
    return False

def build_address(row):
    """Build full situs address string for geocoding."""
    addr1 = (row.get("PHY_ADDR1") or "").strip()
    addr2 = (row.get("PHY_ADDR2") or "").strip()
    city = (row.get("PHY_CITY") or "").strip()
    zipcd = (row.get("PHY_ZIPCD") or "").strip()
    
    if not addr1:
        return ""
    
    parts = [addr1]
    if addr2:
        parts.append(addr2)
    
    city_state_zip = f"{city}, FL {zipcd}".strip()
    if city:
        parts.append(city_state_zip)
    
    return ", ".join(parts)

def batch_geocode(rows, batch_size=GEOCODE_BATCH_SIZE):
    """Batch geocode addresses via Census API. rows = list of dicts with PHY_ADDR1, PHY_CITY, PHY_ZIPCD."""
    results = {}  # full_address -> (lon, lat)
    total = len(rows)
    
    # Build Census format: uid, street, city, state, zip
    # Deduplicate by full address
    addr_to_rows = {}
    for i, row in enumerate(rows):
        addr = row.get("full_address", "")
        if addr:
            addr_to_rows.setdefault(addr, []).append(i)
    
    unique_addrs = list(addr_to_rows.keys())
    
    for batch_start in range(0, len(unique_addrs), batch_size):
        batch_addrs = unique_addrs[batch_start:batch_start + batch_size]
        
        # Build CSV payload in Census format
        lines = []
        addr_to_uid = {}
        for uid, addr in enumerate(batch_addrs, start=batch_start + 1):
            # Parse components from full_address: "123 MAIN ST, MIAMI, FL 33101"
            row_idx = addr_to_rows[addr][0]
            row = rows[row_idx]
            street = (row.get("PHY_ADDR1") or "").strip().replace(",", " ")
            city = (row.get("PHY_CITY") or "").strip()
            zipcd = (row.get("PHY_ZIPCD") or "").strip()[:5]
            
            if not street:
                continue
            
            # Census format: uid, street, city, state, zip
            lines.append(f'{uid},"{street}",{city},FL,{zipcd}')
            addr_to_uid[uid] = addr
        
        if not lines:
            continue
        
        payload = "\n".join(lines)
        
        url = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
        files = {
            "addressFile": ("addresses.csv", io.BytesIO(payload.encode("utf-8")), "text/csv")
        }
        params = {
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
        }
        
        try:
            r = requests.post(url, data=params, files=files, timeout=300)
            if r.status_code == 200:
                for line in r.text.strip().split("\n"):
                    parts = line.split(",")
                    if len(parts) >= 5:
                        uid_str = parts[0].strip('"')
                        match_type = parts[1].strip('"')
                        lat = parts[-2].strip('"')
                        lon = parts[-1].strip('"')
                        
                        if match_type in ("Match", "Exact", "Non_Exact"):
                            try:
                                uid = int(uid_str)
                                if uid in addr_to_uid:
                                    results[addr_to_uid[uid]] = (float(lon), float(lat))
                            except (ValueError, KeyError):
                                pass
            else:
                print(f"  ⚠ Geo batch HTTP {r.status_code} at {batch_start}")
        except Exception as e:
            print(f"  ⚠ Geo batch error at {batch_start}: {e}")
        
        time.sleep(1)
    
    return results

# === STEP 1: Parse all ZIPs and filter ===
print("=== Step 1: Parse NAL Files & Filter Religious ===")
zip_files = sorted(NAL_DIR.glob("*.zip"))
print(f"Found {len(zip_files)} ZIP files")

all_rows = []
total_parcels = 0
coverage = {}

for zi, zippath in enumerate(zip_files):
    county_name = zippath.stem.split()[0]
    
    try:
        with zipfile.ZipFile(zippath) as z:
            csv_names = [n for n in z.namelist() if n.endswith('.csv')]
            if not csv_names:
                continue
            
            with z.open(csv_names[0]) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8', errors='replace'))
                county_rows = 0
                religious_count = 0
                
                for row in reader:
                    county_rows += 1
                    total_parcels += 1
                    
                    if category := get_religious_category(row):
                        # Add county FIPS
                        co_no = row.get("CO_NO", "").strip()
                        row["COUNTY_FIPS"] = COUNTY_FIPS.get(co_no, "")
                        row["source_county"] = county_name
                        row["religious_category"] = category
                        
                        # Build address
                        row["full_address"] = build_address(row)
                        
                        all_rows.append(row)
                        religious_count += 1
                
                coverage[county_name] = (county_rows, religious_count)
    except Exception as e:
        print(f"  ⚠ {county_name}: {e}")
    
    bar = progress_bar(zi + 1, len(zip_files), 30)
    rc = coverage.get(county_name, (0, 0))
    print(f"  {bar} {county_name:20s} → {rc[1]:4d} religious / {rc[0]:6d} total", flush=True)

print(f"\nTotal: {len(all_rows):,} religious parcels from {total_parcels:,} total parcels")

# === STEP 2: Geocode ===
print(f"\n=== Step 2: Geocode {len(all_rows):,} Addresses ===")
unique_addrs = len(set(r["full_address"] for r in all_rows if r.get("full_address")))
print(f"  {unique_addrs:,} unique addresses to geocode")

geocode_results = batch_geocode(all_rows)
geocoded = len(geocode_results)
unique_addrs = len(set(r["full_address"] for r in all_rows if r.get("full_address")))
print(f"  Geocoded: {geocoded:,} / {unique_addrs:,} ({geocoded/max(1,unique_addrs)*100:.1f}%)")

# === STEP 3: Merge geocodes + Save ===
print(f"\n=== Step 3: Save Results ===")
# Build output with geocodes merged back
output_cols = KEEP_COLS + ["COUNTY_FIPS", "source_county", "religious_category", "full_address", "longitude", "latitude"]

with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=output_cols, extrasaction="ignore")
    writer.writeheader()
    
    count = 0
    for row in all_rows:
        addr = row.get("full_address", "")
        if addr in geocode_results:
            row["longitude"] = geocode_results[addr][0]
            row["latitude"] = geocode_results[addr][1]
        else:
            row["longitude"] = ""
            row["latitude"] = ""
        writer.writerow(row)
        count += 1

geo_hit = sum(1 for r in all_rows if r.get("longitude"))
print(f"  Saved: {count:,} rows to {OUT_CSV}")
print(f"  With lat/lon: {geo_hit:,} ({geo_hit/max(1,count)*100:.1f}%)")

# Summary
total_market_value = sum(float(r.get("JV", 0) or 0) for r in all_rows)
print(f"\n=== Summary ===")
print(f"  Counties:       {len(coverage)}")
print(f"  Religious parcels: {count:,}")
print(f"  Geocoded:       {geo_hit:,}")
print(f"  Total JV:       ${total_market_value:,.0f}")
print(f"  Output:         {OUT_CSV}")
print(f"  File size:      {OUT_CSV.stat().st_size / (1024*1024):.1f} MB")
