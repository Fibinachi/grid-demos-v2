import json, os, time, urllib.request
from datetime import datetime

RAW_PATH = "data/arcgis/arcgis_catalog_raw.json"
PROBED_PATH = "data/arcgis/arcgis_probed.json"
CATALOG_PATH = "data/arcgis/arcgis_catalog.json"
os.makedirs("data/arcgis", exist_ok=True)

with open(RAW_PATH, "r", encoding="utf-8") as f:
    raw = json.load(f)

all_ds = raw.get("datasets", [])
print(f"Total datasets: {len(all_ds):,}")

# Filter to FeatureService only
def has_fs_url(ds):
    u = ds.get("url","") or ""
    return "/FeatureServer" in u

fs_ds = [d for d in all_ds if has_fs_url(d)]
print(f"FeatureService datasets: {len(fs_ds):,}")

# --- Load cached probes if exist ---
probed = []
if os.path.exists(PROBED_PATH):
    with open(PROBED_PATH, "r", encoding="utf-8") as f:
        probed = json.load(f)
    print(f"Loaded {len(probed)} cached probes")

already_probed = {p["id"] for p in probed}

def get_layers(base_url):
    """Get usable layers (point/polygon Feature Layer) from a FeatureServer."""
    try:
        req = urllib.request.Request(base_url + "?f=json", headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            info = json.loads(r.read().decode("utf-8"))
        layers = info.get("layers") or info.get("tables") or []
        return [l for l in layers if l.get("type") == "Feature Layer" and l.get("geometryType") in ("esriGeometryPoint","esriGeometryPolygon")]
    except:
        return []

def probe_layer(base_url, lid):
    """Get count and sample record fields from a layer."""
    base = base_url.rstrip("/")
    try:
        cu = f"{base}/{lid}/query?where=1%3D1&returnCountOnly=true&f=json"
        req = urllib.request.Request(cu, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            cd = json.loads(r.read().decode("utf-8"))
        cnt = cd.get("count", 0)
        
        fu = f"{base}/{lid}/query?where=1%3D1&outFields=*&returnGeometry=false&f=json&resultRecordCount=1"
        req2 = urllib.request.Request(fu, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req2, timeout=15) as r2:
            smp = json.loads(r2.read().decode("utf-8"))
        fields = []
        if "features" in smp and smp["features"]:
            fields = list(smp["features"][0].get("attributes", {}).keys())
        return cnt, fields
    except:
        return 0, []

# Build subcatalog: sort by numViews desc
sorted_ds = sorted(fs_ds, key=lambda d: -(d.get("numViews",0) or 0))

# Score and categorize each dataset
HIGH_PRIORITY_KEYWORDS = [
    "place of worship", "places of worship", "house of worship", "houses of worship",
    "all places of worship", "worship enhanced", "places_of_worship",
    "places de culte", "lieux de culte", "kirchen",
    "national", "global", "world",
    "massgis", "usgs", "openstreetmap", "overture", "hifld",
]

LOW_PRIORITY_KEYWORDS = [
    "buffer", "network", "drive time", "drive-time", "isochrone", "service area",
    "map", "dashboard", "story map", "storymap", "app",
    "analysis", "heat map", "heatmap", "cluster",
    "covid", "evacuation", "emergency", "shelter", "disaster",
    "crime", "traffic", "accident", "fire station", "police",
    "population", "demographic", "demograph", "census", "income",
    "land use", "landuse", "zoning", "parcel", "property",
    "school", "library", "park", "hospital", "childcare",
    "walkability", "walk score", "transit", "bike",
    "ada", "accessibility", "sidewalk", "side walks",
    "flu", "vaccine", "health", "nutrition",
    "survey", "questionnaire", "polling", "election",
    "homeless", "poverty", "food desert", "food access",
    "noise", "environmental justice", "environment",
    "nuisance", "complaint", "violation", "permit",
    "property value", "assessment", "real estate",
    "template", "training", "tutorial",
    "address point", "addresspoint", "address_points",
    "building footprint", "buildings",
    "historic district", "historic preservation",
]

STATE_FIELDS = ["STATE","STATE_NAME","ST","STATE_CODE","STATE_FIPS","State","ST_ABBR"]
CITY_FIELDS = ["CITY","CITY_NAME","City","MUNICIPAL","TOWN","CITYNAME","MUN_NAME"]
ZIP_FIELDS = ["ZIP","ZIPCODE","ZIP_CODE","POSTAL","POSTCODE","POSTALCODE"]
NAME_FIELDS = ["NAME","NAME_1","NAME_2","FULL_NAME","SITENAME","SITE_NAME","FACILITY","FACILITY_NAME","CHURCH","CHURCH_NAME","CONGREGATION","ORGANIZATION_NAME","ORG_NAME","LABEL","TITLE"]
CONTACT_PHONE = ["PHONE","TELEPHONE","TEL","PHONE_NUMBER","PHONE1","CONTACT_PHONE"]
CONTACT_EMAIL = ["EMAIL","E_MAIL","EMAIL_ADDRESS","CONTACT_EMAIL","MAIL"]
CONTACT_WEB = ["WEBSITE","URL","WEB","WEB_URL","WEBSITE_URL","SITE_URL","WWW"]
DENOM_FIELDS = ["DENOM","DENOMINATION","DENOM_GROUP","RELIGION","FAITH","AFFILIATION","NTEE_CD","NTEE_CODE","GROUP","CATEGORY","TYPE","SUBTYPE","REL_TYPE","WORSHIP_TYPE"]
ADDR_FIELDS = ["ADDRESS","STREET","STREET_ADDRESS","ADDR","ADDRESS1","STREET1","SITE_ADDRESS","LOCATION","LOC"]

def score_dataset(entry):
    """Score 0-100 for how useful this is as a primary worship data source."""
    title = (entry.get("title","") or "").lower()
    desc = ((entry.get("description","") or "") + " " + (entry.get("snippet","") or "")).lower()
    combined = title + " " + desc
    
    score = 0
    
    # High priority keyword bonus
    for kw in HIGH_PRIORITY_KEYWORDS:
        if kw in combined:
            score += 25
    
    # Name fields presence gives the highest score
    for fn in NAME_FIELDS:
        if fn.lower() in combined:
            score += 5
            break
    
    # Low priority penalty
    for kw in LOW_PRIORITY_KEYWORDS:
        if kw in combined:
            score -= 20
    
    # Views/popularity bonus
    views = entry.get("numViews",0) or 0
    if views > 1000:
        score += 15
    elif views > 500:
        score += 10
    elif views > 100:
        score += 5
    
    # Owner quality
    owner = entry.get("owner","") or ""
    if any(g in owner for g in ["HIFLD","usgs","NOAA","EPA","DHS","FEMA","Census","gov","GIS"]):
        score += 10
    
    return max(0, score)

# Process high-scored datasets for probing
high_priority = []
for ds in fs_ds:
    s = score_dataset(ds)
    if s >= 20:
        high_priority.append((s, ds))

high_priority.sort(key=lambda x: -x[0])
print(f"High-priority datasets (score>=20): {len(high_priority):,}")

# Save high-priority list
with open("data/arcgis/catalog_scores.json","w") as f:
    json.dump([{"score":s, "id":d["id"], "title":d["title"], "views":d.get("numViews",0)} for s,d in high_priority], f, indent=1)

print(f"\nTop 50 high-priority datasets by score:")
for s, d in high_priority[:50]:
    t = (d.get("title","") or "")[:60]
    v = d.get("numViews",0)
    print(f"  [{s:3d}] {t:60s} views={v:>6,}")

# Count by keywords
print(f"\n--- Count by keyword ---")
kw_counts = {
    "worship": 0, "church": 0, "mosque": 0, "synagog": 0,
    "temple": 0, "religi": 0, "faith": 0, "parish": 0,
    "cemetery": 0, "prayer": 0, "meetinghouse": 0, "shrine": 0,
    "monastery": 0, "convent": 0, "chapel": 0, "cathedral": 0,
    "mandir": 0, "gurdwara": 0, "pagoda": 0, "stupa": 0,
    "masjid": 0, "islamic": 0, "buddhist": 0, "hindu": 0,
    "jewish": 0, "sikh": 0, "jain": 0, "bahai": 0,
    "bible": 0, "gospel": 0, "mission": 0, "pastor": 0,
    "anglican": 0, "catholic": 0, "methodist": 0, "baptist": 0,
    "lutheran": 0, "presbyterian": 0, "orthodox": 0,
    "latter-day": 0, "mormon": 0, "jehovah": 0, "evangelical": 0,
    "pentecostal": 0, "nazarene": 0, "salvation army": 0,
    "episcopal": 0, "united church": 0, "christian church": 0,
    "church of god": 0, "church of christ": 0,
    "culto": 0, "iglesia": 0, "templo": 0, "capilla": 0,
    "eglise": 0, "temple": 0, "culte": 0,
    "kirche": 0, "gemeinde": 0,
    "chiesa": 0, "parrocchia": 0,
}

for ds in fs_ds:
    t = (ds.get("title","") + " " + (ds.get("description","") or "") + " " + (ds.get("snippet","") or "")).lower()
    for kw in kw_counts:
        if kw in t:
            kw_counts[kw] += 1

for k, v in sorted(kw_counts.items(), key=lambda x:-x[1]):
    if v > 0:
        print(f"  {k:20s} {v:>6,}")
