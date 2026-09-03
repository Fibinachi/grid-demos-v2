import json, os, time, urllib.request, urllib.parse

RAW_PATH = "data/arcgis/arcgis_catalog_raw.json"
with open(RAW_PATH) as f:
    raw = json.load(f)

datasets = raw.get("datasets", [])
print(f"Loaded {len(datasets):,} datasets")

fs_datasets = [ds for ds in datasets if "/FeatureServer" in (ds.get("url","") or "")]
print(f"FeatureService datasets: {len(fs_datasets):,}")

probed = []
for i, ds in enumerate(fs_datasets[:200]):
    url = ds.get("url", "")
    title = ds.get("title","")[:60]
    info_url = url.rstrip("/") + "?f=json"
    try:
        req = urllib.request.Request(info_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            info = json.loads(resp.read().decode("utf-8"))
        
        layers = info.get("layers") or info.get("tables") or []
        pt_layers = [l for l in layers if l.get("type") == "Feature Layer" and l.get("geometryType") in ("esriGeometryPoint","esriGeometryPolygon")]
        if not pt_layers:
            continue
        
        lid = pt_layers[0]["id"]
        base = url.rstrip("/")
        
        # Count
        cu = f"{base}/{lid}/query?where=1%3D1&returnCountOnly=true&f=json"
        r2 = urllib.request.Request(cu, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(r2, timeout=15) as resp2:
            cd = json.loads(resp2.read().decode("utf-8"))
        cnt = cd.get("count", 0)
        
        # Fields (sample 1 record)
        fu = f"{base}/{lid}/query?where=1%3D1&outFields=*&returnGeometry=false&f=json&resultRecordCount=1"
        r3 = urllib.request.Request(fu, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(r3, timeout=15) as resp3:
            smp = json.loads(resp3.read().decode("utf-8"))
        
        fields = []
        if "features" in smp and smp["features"]:
            fields = list(smp["features"][0].get("attributes", {}).keys())
        
        entry = {
            "id": ds.get("id",""),
            "title": title,
            "description": (ds.get("description","") or "")[:200],
            "url": url,
            "layer_id": lid,
            "count": cnt,
            "fields": fields,
            "num_fields": len(fields),
            "numViews": ds.get("numViews",0),
        }
        probed.append(entry)
        print(f"  [{i+1}] {title[:50]:50s} cnt={cnt:>6,}  flds={len(fields)}")
    except Exception as e:
        pass
    time.sleep(0.3)

with open("data/arcgis/arcgis_probed.json","w") as f:
    json.dump(probed, f, indent=1, ensure_ascii=False)

print(f"\nProbed {len(probed)} datasets, total features: {sum(p['count'] for p in probed):,}")
