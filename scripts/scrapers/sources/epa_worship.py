"""
Download EPA/HIFLD All Places of Worship dataset from ArcGIS Feature Service.
Queries in batches of 2000, saves to CSV, uploads to S3.
Fields: EIN, NAME, STREET, CITY, STATE, ZIP, NTEE_CD,
        X, Y (coordinates), SCORE, MATCH_TYPE (geocode quality)
"""
import csv, json, os, time, urllib.request, urllib.parse

BASE_URL = "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/All_Places_Of_Worship__HiFLD_Open_/FeatureServer/42/query"

def fetch_batch(offset=0, batch_size=2000):
    """Fetch one batch of records."""
    params = {
        "where": "1=1",
        "outFields": "EIN,NAME,STREET,CITY,STATE,ZIP,NTEE_CD,X,Y,SCORE,MATCH_TYPE",
        "returnGeometry": "false",
        "resultOffset": offset,
        "resultRecordCount": batch_size,
        "f": "json"
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        features = data.get("features", [])
        count = len(features)
        records = []
        for f in features:
            attrs = f.get("attributes", {})
            records.append({
                "ein": attrs.get("EIN", ""),
                "name": attrs.get("NAME", ""),
                "street": attrs.get("STREET", ""),
                "city": attrs.get("CITY", ""),
                "state": attrs.get("STATE", ""),
                "zip": attrs.get("ZIP", ""),
                "ntee_cd": attrs.get("NTEE_CD", ""),
                "latitude": attrs.get("Y"),
                "longitude": attrs.get("X"),
                "geocode_score": attrs.get("SCORE"),
                "match_type": attrs.get("MATCH_TYPE", ""),
            })
        return records
    except Exception as e:
        print(f"  Error at offset {offset}: {e}")
        return []

def main():
    out_dir = "/home/ec2-user/data/epa_worship"
    os.makedirs(out_dir, exist_ok=True)
    
    all_records = []
    offset = 0
    batch_size = 2000
    total = 0
    
    print("Downloading EPA All Places of Worship...")
    while True:
        print(f"  Fetching records {offset}-{offset+batch_size}...")
        records = fetch_batch(offset, batch_size)
        if not records:
            break
        all_records.extend(records)
        total += len(records)
        print(f"  Got {len(records)} records ({total} total)")
        offset += batch_size
        time.sleep(0.5)  # rate limit
        
        if len(records) < batch_size:
            break
    
    print(f"\nTotal: {total} records")
    
    # Save CSV
    out_path = os.path.join(out_dir, "epa_worship_all.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "ein","name","street","city","state","zip","ntee_cd",
            "latitude","longitude","geocode_score","match_type"
        ])
        w.writeheader()
        w.writerows(all_records)
    
    print(f"Saved to {out_path}")
    
    # Upload to S3
    os.system(f"aws s3 cp {out_path} s3://grantwizard-scripts/epa_worship_all.csv --region us-east-1")
    print("Uploaded to S3")

if __name__ == "__main__":
    main()
