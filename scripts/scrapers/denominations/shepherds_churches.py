"""
Shepherd's Stream Church Scraper — Elasticsearch API + EPA cross-ref.
- Queries site's public Elasticsearch index by state category (14-63)
- Gets ALL fields directly: name, phone, website, state, denom, address, lat/lon
- Cross-references with EPA dataset (name+state) to add EIN
- Write to RDS every 100 records
"""
import csv, json, os, re, time, urllib.request, urllib.parse

UA = "Mozilla/5.0 (compatible; GrantWizard/1.0; ResearchProject)"
ES_URL = "https://shepherdsstream.org/elasticsearch"

STATE_IDS = {
    14: "AL", 15: "AK", 16: "AZ", 17: "AR", 18: "CA", 19: "CO", 20: "CT",
    21: "DE", 22: "FL", 23: "GA", 24: "HI", 25: "ID", 26: "IL", 27: "IN",
    28: "IA", 29: "KS", 30: "KY", 31: "LA", 32: "ME", 33: "MD", 34: "MA",
    35: "MI", 36: "MN", 37: "MS", 38: "MO", 39: "MT", 40: "NE", 41: "NV",
    42: "NH", 43: "NJ", 44: "NM", 45: "NY", 46: "NC", 47: "ND", 48: "OH",
    49: "OK", 50: "OR", 51: "PA", 52: "RI", 53: "SC", 54: "SD", 55: "TN",
    56: "TX", 57: "UT", 58: "VT", 59: "VA", 60: "WA", 61: "WV", 62: "WI",
    63: "WY",
}

# EPA cross-reference lookup
EPA_LOOKUP = {}

def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def fetch_es(params):
    """Query the site's Elasticsearch index with retries."""
    url = ES_URL + "?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            resp = urllib.request.urlopen(req, timeout=15)
            return json.loads(resp.read())
        except Exception as e:
            log(f"  ES query failed (attempt {attempt+1}): {e}")
            time.sleep(2)
    return None

def load_epa():
    """Download EPA CSV from ArcGIS API directly and build lookup."""
    log("Downloading EPA data from ArcGIS...")
    BASE = "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/All_Places_Of_Worship__HiFLD_Open_/FeatureServer/42/query"
    offset = 0
    count = 0
    while True:
        params = {
            "where": "1=1",
            "outFields": "EIN,NAME,STATE,Y,X,SCORE",
            "returnGeometry": "false",
            "resultOffset": offset,
            "resultRecordCount": 2000,
            "f": "json"
        }
        url = BASE + "?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            resp = urllib.request.urlopen(req, timeout=30)
            data = json.loads(resp.read())
        except Exception as e:
            log(f"  EPA query failed at offset {offset}: {e}")
            break
        features = data.get("features", [])
        if not features:
            break
        for x in features:
            a = x.get("attributes", {})
            name = (a.get("NAME") or "").strip().upper()
            state = (a.get("STATE") or "").strip().upper()
            if name and state and len(state) == 2:
                key = (re.sub(r"[^A-Z0-9 ]", "", name).strip(), state)
                if key not in EPA_LOOKUP:
                    EPA_LOOKUP[key] = []
                EPA_LOOKUP[key].append({
                    "ein": a.get("EIN", ""),
                    "lat": a.get("Y"),
                    "lon": a.get("X"),
                    "score": a.get("SCORE"),
                })
                count += 1
        offset += len(features)
        log(f"  EPA: {count} records downloaded")
        time.sleep(0.3)
    log(f"Loaded {count} EPA records ({len(EPA_LOOKUP)} unique name+state keys)")

def epa_lookup(name, state):
    """Find EPA match by name + state. Returns best match or None."""
    key = (re.sub(r"[^A-Z0-9 ]", "", (name or "").upper()).strip(), (state or "").upper())
    matches = EPA_LOOKUP.get(key, [])
    if not matches:
        return None
    matches.sort(key=lambda x: float(x["score"] or 0), reverse=True)
    return matches[0]

cc_hits = 0
cc_miss = 0
direct_hits = 0

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def query_state(cat_id, state_abbr, size=200):
    """Query ES for all churches in a state category. Returns list of records."""
    all_records = []
    start = 0
    while True:
        params = {
            "index": "shepherdsstream",
            "q": f"cat_id:*{cat_id}*",
            "size": size,
            "from": start,
        }
        data = fetch_es(params)
        if not data:
            break
        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break
        for h in hits:
            src = h.get("_source", {})
            tax = src.get("taxonomy", [{}])[0] if src.get("taxonomy") else {}
            loc = src.get("location") or {}
            rec = {
                "name": src.get("title", ""),
                "phone": tax.get("jreviews_jr_mainphone", ""),
                "website": tax.get("jreviews_jr_website", ""),
                "state": state_abbr,
                "denomination": tax.get("jreviews_jr_denomination", ""),
                "address": tax.get("jreviews_jr_address", ""),
                "city": tax.get("jreviews_jr_city", ""),
                "zip": tax.get("jreviews_jr_zipcode", ""),
                "latitude": loc.get("lat", ""),
                "longitude": loc.get("lon", ""),
                "url": "https://shepherdsstream.org/" + src.get("path", ""),
            }
            all_records.append(rec)
        total = data.get("hits", {}).get("total", {}).get("value", 0)
        log(f"  {state_abbr}: fetched {len(all_records)}/{total}")
        if len(all_records) >= total:
            break
        start += size
        time.sleep(0.3)
    return all_records

def write_to_rds(records):
    """Write batch to RDS. Uses mysql.connector if available, else CSV."""
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host="grantwizard.csjiu2wagplc.us-east-1.rds.amazonaws.com",
            user="grantwizard", password="F3y6bBoQZeYPMJir",
            database="grantwizard", connect_timeout=5
        )
        cur = conn.cursor()
        for r in records:
            n, ci, st = r.get("name",""), r.get("city",""), r.get("state","")
            if not n or not st:
                continue
            cur.execute("SELECT id FROM churches WHERE name=%s AND state=%s LIMIT 1", (n, st))
            exists = cur.fetchone()
            phone = r.get("phone","")
            web = r.get("website","")
            denom = r.get("denomination","")
            desc = r.get("description","")
            ein = r.get("ein","")
            lat = r.get("latitude","")
            lon = r.get("longitude","")
            src = "shepherds_stream"
            if exists:
                cid = exists[0]
                sets = []; vals = []
                if phone: sets.append("phone=%s"); vals.append(phone)
                if web: sets.append("website=%s"); vals.append(web)
                if denom: sets.append("denomination=%s"); vals.append(denom)
                if desc: sets.append("notes=%s"); vals.append(desc)
                if ein: sets.append("ein=%s"); vals.append(ein)
                if lat: sets.append("latitude=%s"); vals.append(lat)
                if lon: sets.append("longitude=%s"); vals.append(lon)
                if sets:
                    vals.append(cid)
                    cur.execute(f"UPDATE churches SET {','.join(sets)} WHERE id=%s", vals)
            else:
                cur.execute(
                    "INSERT INTO churches (name,state,phone,website,denomination,notes,source,ein,latitude,longitude) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (n, st, phone, web, denom, desc, src, ein, lat or None, lon or None)
                )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except:
        return False

def main():
    log("Phase 1: Loading EPA cross-reference...")
    load_epa()
    
    log("Phase 2: Querying Elasticsearch by state...")
    total_records = 0
    batch = []
    
    for cat_id in range(14, 64):
        state_abbr = STATE_IDS[cat_id]
        records = query_state(cat_id, state_abbr)
        log(f"  {state_abbr} (cat {cat_id}): {len(records)} listings")
        
        for rec in records:
            epa = epa_lookup(rec.get("name"), rec.get("state"))
            if epa:
                rec["ein"] = epa["ein"]
                if not rec.get("latitude") or not rec.get("longitude"):
                    rec["latitude"] = epa.get("lat")
                    rec["longitude"] = epa.get("lon")
            else:
                rec["ein"] = ""
            batch.append(rec)
            total_records += 1
        
        # Write per state
        if batch:
            ok = write_to_rds(batch)
            log(f"  Wrote {len(batch)} records to RDS {'OK' if ok else 'FAILED'}")
            batch = []
        
        log(f"  Running total: {total_records}")
        time.sleep(0.5)
    
    log(f"Done! Total: {total_records} records")

if __name__ == "__main__":
    main()
