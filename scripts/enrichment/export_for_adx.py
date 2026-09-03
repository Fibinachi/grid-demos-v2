"""
Export GRID for AWS Data Exchange + create listing + update outreach emails.
"""
import sqlite3, csv, gzip, json, subprocess, time
from pathlib import Path
from datetime import datetime

DB = Path("churches.db")
OUT = Path("outputs/marketplace")
OUT.mkdir(parents=True, exist_ok=True)

db = sqlite3.connect(str(DB))
db.row_factory = sqlite3.Row

def export_csv(query, filename, desc):
    print(f"  {desc}...")
    rows = list(db.execute(query))
    if not rows: print(f"    0 rows!"); return None
    gzpath = OUT / f"{filename}.gz"
    with gzip.open(str(gzpath), 'wt', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(rows[0].keys())
        for r in rows: w.writerow(r)
    print(f"    {len(rows):,} rows -> {gzpath.name} ({gzpath.stat().st_size/1024:.0f} KB)")
    return gzpath

# 1. Vermont sample
print("=== EXPORTING ===")
vt = export_csv("""
    SELECT c.id, c.name, c.faith, c.tradition, c.landmark_type,
           c.city, c.county, c.state, c.country,
           c.latitude, c.longitude, c.address, c.county_fips_5, c.zip5,
           f.RISK_SCORE, f.RISK_RATNG, f.EAL_SCORE, f.SOVI_SCORE, f.RESL_SCORE,
           f.HRCN_RISKS as hurricane_risk, f.TRND_RISKS as tornado_risk,
           f.IFLD_RISKS as inland_flood_risk, f.WFIR_RISKS as wildfire_risk,
           f.ERQK_RISKS as earthquake_risk, f.WNTW_RISKS as winter_weather_risk,
           f.HWAV_RISKS as heat_wave_risk, f.DRGT_RISKS as drought_risk,
           f.POPULATION as tract_population
    FROM churches c
    LEFT JOIN church_districts d ON d.church_id=c.id AND d.layer_code='TRACT'
    LEFT JOIN fema_nri_tract f ON f.TRACTFIPS=d.geo_id
    WHERE c.state='VT' AND c.country='US'
    ORDER BY c.name LIMIT 500
""", "grid_vt_sample.csv", "VT sample")

# 2. US full
us = export_csv("""
    SELECT c.id, c.name, c.faith, c.tradition, c.landmark_type,
           c.city, c.county, c.state, c.country,
           c.latitude, c.longitude, c.address, c.county_fips_5, c.zip5, c.source
    FROM churches c WHERE c.country='US'
    ORDER BY c.state, c.county, c.name
""", "grid_us_full.csv", "US full")

db.close()

# 3. Upload to S3
print("\n=== UPLOADING TO S3 ===")
for f in [vt, us]:
    if f:
        key = f"data/{f.name}"
        subprocess.run(["aws", "s3", "cp", str(f), f"s3://grid-marketplace-data/{key}"], check=True)
        print(f"  {f.name} -> s3://grid-marketplace-data/{key}")

# Upload data dictionary
dict_md = OUT / "data_dictionary.md"
subprocess.run(["aws", "s3", "cp", str(dict_md), "s3://grid-marketplace-data/data/data_dictionary.md"], check=True)

# 4. Create ADX dataset
print("\n=== CREATING ADX DATASET ===")
result = subprocess.run([
    "aws", "dataexchange", "create-data-set",
    "--asset-type", "S3_SNAPSHOT",
    "--description", "GRID maps 3.4M worship sites globally with FLTD taxonomy and FEMA risk scores. Updated quarterly or more often.",
    "--name", "GRID - Global Religious Infrastructure Database",
    "--output", "json"
], capture_output=True, text=True)
ds = json.loads(result.stdout)
ds_id = ds["Id"]
print(f"  Dataset ID: {ds_id}")

# 5. Create revision
print("\n=== CREATING REVISION ===")
result = subprocess.run([
    "aws", "dataexchange", "create-revision",
    "--data-set-id", ds_id,
    "--output", "json"
], capture_output=True, text=True)
rev = json.loads(result.stdout)
rev_id = rev["Id"]
print(f"  Revision ID: {rev_id}")

# 6. Import assets from S3
print("\n=== IMPORTING ASSETS ===")
vt_key = f"data/{vt.name}" if vt else None
us_key = f"data/{us.name}" if us else None

assets = []
if vt_key:
    assets.append({"AssetDetails": {"S3SnapshotAsset": {"Size": vt.stat().st_size}}, "Bucket": "grid-marketplace-data", "Key": vt_key, "Name": "Vermont Sample (500 rows, free)"})
if us_key:
    assets.append({"AssetDetails": {"S3SnapshotAsset": {"Size": us.stat().st_size}}, "Bucket": "grid-marketplace-data", "Key": us_key, "Name": "US Full Dataset (~1M rows, paid)"})

result = subprocess.run([
    "aws", "dataexchange", "import-assets-to-revision",
    "--data-set-id", ds_id,
    "--revision-id", rev_id,
    "--cli-input-json", json.dumps({"Assets": assets}),
    "--output", "json"
], capture_output=True, text=True)
print(f"  Imported {len(assets)} assets")
job_id = json.loads(result.stdout).get("Id", "?")
print(f"  Job: {job_id}")

# 7. Finalize revision
print("\n=== FINALIZING REVISION ===")
time.sleep(5)  # Let import job settle
subprocess.run([
    "aws", "dataexchange", "update-revision",
    "--data-set-id", ds_id,
    "--revision-id", rev_id,
    "--finalized"
], check=True)
print("  Revision finalized")

# 8. ADX listing URL
adx_url = f"https://us-east-1.console.aws.amazon.com/dataexchange/home?region=us-east-1#/data-sets/{ds_id}"
print(f"\n  ADX Listing: {adx_url}")

# 9. Save URL for outreach
(OUT / "adx_listing_url.txt").write_text(adx_url)
print(f"  URL saved to {OUT}/adx_listing_url.txt")
print(f"\nDone! Listing at: {adx_url}")
