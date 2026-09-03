"""Download EPA All Places of Worship from ArcGIS Feature Service to CSV + S3."""
import json, urllib.request, csv, os, time

BASE = "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/All_Places_Of_Worship__HiFLD_Open_/FeatureServer/42/query"
OUT = "epa_worship_all.csv"
UA = "Mozilla/5.0"
FIELDS = ["ein", "name", "street", "city", "state", "zip", "ntee_cd", "lat", "lon", "score"]

f = open(OUT, "w", newline="")
w = csv.DictWriter(f, fieldnames=FIELDS)
w.writeheader()

offset = 0
total = 0

while True:
    params = urllib.parse.urlencode({
        "where": "1=1",
        "outFields": "EIN,NAME,STREET,CITY,STATE,ZIP,NTEE_CD,X,Y,SCORE",
        "returnGeometry": "false",
        "resultOffset": offset,
        "resultRecordCount": 2000,
        "f": "json"
    })
    url = BASE + "?" + params
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())
    features = data.get("features", [])
    batch = len(features)
    
    for x in features:
        attrs = x.get("attributes", {})
        w.writerow({
            "ein": attrs.get("EIN", ""),
            "name": attrs.get("NAME", ""),
            "street": attrs.get("STREET", ""),
            "city": attrs.get("CITY", ""),
            "state": attrs.get("STATE", ""),
            "zip": attrs.get("ZIP", ""),
            "ntee_cd": attrs.get("NTEE_CD", ""),
            "lat": attrs.get("Y"),
            "lon": attrs.get("X"),
            "score": attrs.get("SCORE"),
        })
    
    total += batch
    print(f"offset={offset} got={batch} total={total}")
    offset += batch
    time.sleep(0.3)
    
    if batch < 2000:
        break

f.close()
print(f"\nDone: {total} records -> {OUT}")

os.system(f"aws s3 cp {OUT} s3://grantwizard-scripts/epa_worship_all.csv --region us-east-1")
print("Uploaded to S3")
