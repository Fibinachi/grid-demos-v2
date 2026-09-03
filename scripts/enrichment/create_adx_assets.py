"""Create ADX assets from S3 and finalize revision."""
import json, subprocess, time, os
from pathlib import Path

DSID = "993cef8f87cacadaee6e20e52d939084"
REVID = "506452e32ecd12c9cc4e99204f1b47e5"
BUCKET = "grid-marketplace-data"

# Get file sizes
def s3_size(key):
    result = subprocess.run(["aws", "s3", "head-object", "--bucket", BUCKET, "--key", key, "--output", "json"],
                          capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout).get("ContentLength", 0)
    return 0

files = [
    ("data/grid_vt_sample.csv.gz", "Vermont Sample (500 rows with FEMA scores, free)"),
    ("data/grid_us_full.csv.gz", "US Full Dataset (~1M worship sites, paid)"),
    ("data/data_dictionary.md", "Data Dictionary & FTLM Taxonomy Guide"),
]

assets = []
for key, name in files:
    size = s3_size(key)
    assets.append({
        "AssetDetails": {"S3SnapshotAsset": {"Size": size}},
        "Bucket": BUCKET,
        "Key": key,
        "Name": name
    })
    print(f"  {name}: {size:,} bytes")

# Create job payload
job = {
    "Type": "IMPORT_ASSETS_FROM_S3",
    "Details": {
        "ImportAssetsFromS3": {
            "AssetSources": [
                {"Bucket": a["Bucket"], "Key": a["Key"]} for a in assets
            ],
            "DataSetId": DSID,
            "RevisionId": REVID
        }
    }
}

# Write payload to file (avoids PowerShell JSON escaping issues)
payload_file = "outputs/marketplace/adx_job_payload.json"
Path(payload_file).write_text(json.dumps(job))

print(f"\nCreating import job...")
result = subprocess.run(["aws", "dataexchange", "create-job",
    "--cli-input-json", f"file://{payload_file}",
    "--output", "json"],
    capture_output=True, text=True)
print(result.stdout[:500])
job_data = json.loads(result.stdout)
job_id = job_data.get("Id")

if job_id:
    print(f"\nStarting job {job_id}...")
    subprocess.run(["aws", "dataexchange", "start-job", "--job-id", job_id], check=True)
    
    # Wait for job to complete
    print("Waiting for job...")
    for i in range(30):
        time.sleep(2)
        status = subprocess.run(["aws", "dataexchange", "get-job", "--job-id", job_id, "--output", "json"],
                              capture_output=True, text=True)
        state = json.loads(status.stdout).get("State", "?")
        if state == "COMPLETED":
            print(f"Job completed!")
            break
        elif state == "ERROR":
            print(f"Job error: {status.stdout[:500]}")
            break
        print(f"  {state}...", end="", flush=True)
    
    # Finalize revision
    print(f"\nFinalizing revision...")
    subprocess.run(["aws", "dataexchange", "update-revision",
        "--data-set-id", DSID, "--revision-id", REVID, "--finalized"], check=True)
    print("Revision finalized!")

    adx_url = f"https://us-east-1.console.aws.amazon.com/dataexchange/home?region=us-east-1#/data-sets/{DSID}"
    print(f"\nADX Listing: {adx_url}")
    Path("outputs/marketplace/adx_listing_url.txt").write_text(adx_url)
else:
    print(f"Job creation failed: {result.stderr}")
