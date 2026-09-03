"""
FL Religious Parcels — Geocode via Census Batch API
Reads the existing CSV, skips bad addresses, batch geocodes, saves progress after each batch.
Resume-safe: skips rows that already have lat/lon.
"""
import csv, time, requests, io
from pathlib import Path

CSV_PATH = Path("E:/grid/data/fl_dor/fl_religious_parcels_2025.csv")
GEOCODE_BATCH_SIZE = 1000  # Smaller batches for reliability
BAD_ADDR_PATTERNS = ["UNASSIGNED LOCATION", "UNKNOWN", "NO ADDRESS", "P.O. BOX", "PO BOX"]

def progress_bar(current, total, width=40):
    if total == 0:
        return f"[{'█'*width}] {current}/{current} (100%)"
    pct = current / total
    filled = int(width * pct)
    return f"[{'█'*filled}{'░'*(width-filled)}] {current}/{total} ({pct*100:.0f}%)"

def is_bad_address(street):
    """Return True if address is ungeocodeable."""
    if not street or not street.strip():
        return True
    upper = street.strip().upper()
    for pat in BAD_ADDR_PATTERNS:
        if pat in upper:
            return True
    return False

# Read all rows
print("Reading CSV...")
with open(CSV_PATH, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)
print(f"  {len(rows):,} rows")

# Build address -> row indices map (only ungeocoded, valid addresses)
addr_map = {}
bad_count = 0
already_geo = 0
for i, row in enumerate(rows):
    if row.get("longitude", "").strip() and row.get("latitude", "").strip():
        already_geo += 1
        continue
    street = (row.get("PHY_ADDR1") or "").strip()
    city = (row.get("PHY_CITY") or "").strip()
    if is_bad_address(street) or not city:
        bad_count += 1
        continue
    # Key: street + city (Census API needs these separately, but we dedup on combo)
    key = f"{street}|{city}"
    addr_map.setdefault(key, []).append(i)

unique_addrs = list(addr_map.keys())
print(f"  Already geocoded: {already_geo:,}")
print(f"  Bad/skipped: {bad_count:,}")
print(f"  {len(unique_addrs):,} unique addresses to geocode")

if not unique_addrs:
    print("Nothing to geocode!")
    exit(0)

# Batch geocode with progress saving after each batch
geocoded = 0
batches = list(range(0, len(unique_addrs), GEOCODE_BATCH_SIZE))
print(f"\nGeocoding in {len(batches)} batches of up to {GEOCODE_BATCH_SIZE:,}...")

for batch_num, batch_start in enumerate(batches):
    batch_addrs = unique_addrs[batch_start:batch_start + GEOCODE_BATCH_SIZE]

    # Build Census CSV payload: uid, street, city, state, zip
    lines = []
    uid_to_key = {}
    for uid_offset, key in enumerate(batch_addrs):
        uid = batch_start + uid_offset + 1  # 1-indexed for Census API
        street_raw, city = key.split("|", 1)
        row_idx = addr_map[key][0]
        row = rows[row_idx]
        zipcd = (row.get("PHY_ZIPCD") or "").strip()[:5]

        # Clean street for CSV (no commas, no quotes)
        street = street_raw.replace(",", " ").replace('"', "").strip()
        if not street or not city:
            continue

        lines.append(f'{uid},{street},{city},FL,{zipcd}')
        uid_to_key[uid] = key

    if not lines:
        continue

    payload = "\n".join(lines)
    url = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
    files = {"addressFile": ("a.csv", payload.encode(), "text/csv")}
    params = {"benchmark": "Public_AR_Current", "vintage": "Current_Current"}

    batch_hits = 0
    try:
        r = requests.post(url, data=params, files=files, timeout=300)
        if r.status_code == 200:
            # Use csv.reader to properly handle quoted fields with commas
            reader = csv.reader(io.StringIO(r.text))
            for row in reader:
                if len(row) < 6:
                    continue
                try:
                    uid = int(row[0])
                    match_type = row[2]
                    # Census API returns coords as "lon,lat" in field 5
                    lon, lat = row[5].split(",", 1)
                    lon = float(lon)
                    lat = float(lat)

                    if match_type in ("Match", "Exact", "Non_Exact") and uid in uid_to_key:
                        key = uid_to_key[uid]
                        for ri in addr_map[key]:
                            rows[ri]["longitude"] = str(lon)
                            rows[ri]["latitude"] = str(lat)
                        batch_hits += 1
                except (ValueError, KeyError, IndexError):
                    pass
            geocoded += batch_hits
        else:
            print(f"  ⚠ HTTP {r.status_code} batch {batch_num+1}/{len(batches)}")
    except Exception as e:
        print(f"  ⚠ Error batch {batch_num+1}/{len(batches)}: {e}")

    # Save progress after each batch
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    bar = progress_bar(batch_start + len(batch_addrs), len(unique_addrs))
    print(f"  {bar}  hits: {batch_hits} | total: {geocoded:,}", flush=True)
    time.sleep(0.5)  # Be polite to Census API

# Final summary
has_geo = sum(1 for r in rows if r.get("longitude", "").strip())
print(f"\n{'='*60}")
print(f"Done! {has_geo:,} / {len(rows):,} geocoded ({has_geo/max(1,len(rows))*100:.1f}%)")
print(f"Output: {CSV_PATH} ({CSV_PATH.stat().st_size / (1024*1024):.1f} MB)")
