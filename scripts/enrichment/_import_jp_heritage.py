"""
Import Japanese designated cultural properties (shrines & temples) from
Japan Search (jpsearch.go.jp), which aggregates:
- National Treasures (国宝) — kunishitei.bunka.go.jp
- Important Cultural Properties (重要文化財)
- Historic Sites (史跡)
- Registered Tangible Cultural Properties (登録有形文化財)

Uses EasySPARQL REST API — query by prefecture, type=神社/寺院.
Records heritage_status, designation level, and matches against churches.db.
"""
import requests, json, time, sqlite3, sys
from datetime import datetime, timezone

DB = "churches.db"
EASYSPARQL = "https://jpsearch.go.jp/rdf/sparql/easy/"
PREFS = [
    "北海道","青森","岩手","宮城","秋田","山形","福島",
    "茨城","栃木","群馬","埼玉","千葉","東京","神奈川",
    "新潟","富山","石川","福井","山梨","長野","岐阜","静岡","愛知",
    "三重","滋賀","京都","大阪","兵庫","奈良","和歌山",
    "鳥取","島根","岡山","広島","山口",
    "徳島","香川","愛媛","高知",
    "福岡","佐賀","長崎","熊本","大分","宮崎","鹿児島","沖縄",
]

def query_easy(where, what, limit=2000):
    """Query Japan Search EasySPARQL. Returns list of binding dicts."""
    params = {"where": where, "what": what, "format": "json", "limit": limit}
    r = requests.get(EASYSPARQL, params=params, timeout=120)
    r.raise_for_status()
    data = r.json()
    bindings = data.get("results", {}).get("bindings", [])
    results = []
    for b in bindings:
        item = {}
        for k, v in b.items():
            item[k] = v.get("value", "") if v else ""
        results.append(item)
    return results

def get_coords(item):
    """Extract lat/lon from EasySPARQL result (lat/long fields present when where=prefecture)."""
    try:
        lat = float(item.get("lat", 0))
        lon = float(item.get("long", 0))
        if lat and lon:
            return lat, lon
    except (ValueError, TypeError):
        pass
    return None, None

def classify_jp_type(item):
    """Determine faith and landmark type from Japan Search class."""
    t = item.get("type", "")
    label = item.get("label", "")
    
    if "神社" in t or "shrine" in t.lower():
        faith = "Shinto"
        lm = "shrine"
    elif "寺院" in t or "temple" in t.lower():
        faith = "Buddhist"
        lm = "temple"
    elif "教会" in t or "church" in t.lower():
        faith = "Christian"
        lm = "church"
    else:
        # Guess from label
        if any(w in label for w in ["神社","神宮","大社","八幡"]):
            faith, lm = "Shinto", "shrine"
        elif any(w in label for w in ["寺","院","坊"]):
            faith, lm = "Buddhist", "temple"
        elif any(w in label for w in ["教会","聖堂","チャペル"]):
            faith, lm = "Christian", "church"
        else:
            faith, lm = None, None
    
    return faith, lm

def infer_designation(item):
    """Infer heritage designation from source info and labels."""
    # Japan Search aggregates from kunishitei.bunka.go.jp among others
    source = item.get("source", "")
    label = item.get("label", "")
    creator = item.get("creator", "")
    
    # The source info tells us which database
    if "kunishitei" in source.lower() or "国指定" in source:
        if "国宝" in label:
            return "National Treasure"
        elif "重要文化財" in label:
            return "Important Cultural Property"
        elif "史跡" in label:
            return "Historic Site"
        elif "登録有形文化財" in label:
            return "Registered Tangible Cultural Property"
        else:
            return "Designated Cultural Property"
    return None

def match_existing(conn, name, lat, lon):
    """Try to match against existing churches.db records."""
    c = conn.cursor()
    # Exact name match + country JP
    c.execute("""SELECT id, name, latitude, longitude FROM churches 
                 WHERE country='JP' AND name=? LIMIT 1""", (name,))
    row = c.fetchone()
    if row:
        return row[0]
    
    # Fuzzy: same lat/lon within ~100m
    if lat and lon:
        c.execute("""SELECT id, name, latitude, longitude FROM churches 
                     WHERE country='JP' 
                     AND ABS(latitude - ?) < 0.001 AND ABS(longitude - ?) < 0.001
                     LIMIT 1""", (lat, lon))
        row = c.fetchone()
        if row:
            return row[0]
    
    return None

def main():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    ts = datetime.now(timezone.utc).isoformat()
    
    # Ensure heritage columns exist
    c.execute("PRAGMA table_info(churches)")
    cols = {r[1] for r in c.fetchall()}
    if "heritage_status" not in cols:
        c.execute("ALTER TABLE churches ADD COLUMN heritage_status TEXT")
        conn.commit()
    if "heritage_source" not in cols:
        c.execute("ALTER TABLE churches ADD COLUMN heritage_source TEXT")
        conn.commit()
    
    # Count existing Japan records
    c.execute("SELECT COUNT(1) FROM churches WHERE country='JP'")
    jp_before = c.fetchone()[0]
    print(f"Japan churches before: {jp_before:,}")
    
    total_new = 0
    total_matched = 0
    total_fetched = 0
    
    for pref in PREFS:
        print(f"\n--- {pref} ---")
        
        for what, faith_label in [("神社", "Shinto"), ("寺院", "Buddhist")]:
            try:
                items = query_easy(pref, what)
                print(f"  {what}: {len(items)} results from Japan Search")
                total_fetched += len(items)
                
                new_in_pref = 0
                for item in items:
                    label = item.get("label", "")
                    if not label:
                        continue
                    
                    lat, lon = get_coords(item)
                    faith, lm = classify_jp_type(item)
                    designation = infer_designation(item)
                    
                    existing_id = match_existing(conn, label, lat, lon)
                    
                    if existing_id:
                        # Update heritage status on existing record
                        if designation:
                            c.execute("""UPDATE churches SET heritage_status=?, heritage_source=? 
                                         WHERE id=?""",
                                      (designation, "bunka_agency", existing_id))
                            conn.commit()
                            total_matched += 1
                    else:
                        # Insert new record
                        c.execute("""INSERT INTO churches(name,latitude,longitude,faith,
                                    landmark_type,country,source,heritage_status,heritage_source)
                                    VALUES(?,?,?,?,?,?,?,?,?)""",
                                  (label, lat, lon, faith, lm, "JP",
                                   "jpsearch", designation, "bunka_agency"))
                        conn.commit()
                        new_in_pref += 1
                        total_new += 1
                
                if new_in_pref:
                    print(f"    +{new_in_pref} new to DB")
                
                time.sleep(0.5)  # Rate limit
                
            except Exception as e:
                print(f"  {what}: ERROR - {e}")
        
        time.sleep(0.3)  # Rate limit between prefectures
    
    # Summary
    c.execute("SELECT COUNT(1) FROM churches WHERE country='JP'")
    jp_after = c.fetchone()[0]
    print(f"\n{'='*50}")
    print(f"Japan Search fetch: {total_fetched:,} total results")
    print(f"New records inserted: {total_new:,}")
    print(f"Existing records updated: {total_matched:,}")
    print(f"Japan churches: {jp_before:,} → {jp_after:,}")
    
    # Provenance
    c.execute("""INSERT INTO provenance_log(source,script_name,started_at,completed_at,
                 churches_inserted,fields_populated,status,notes)
                 VALUES(?,?,?,?,?,?,?,?)""",
              ("jpsearch", "import_jp_heritage.py", ts,
               datetime.now(timezone.utc).isoformat(),
               total_new, "heritage_status,heritage_source", "completed",
               f"Japan Search: {total_new} new, {total_matched} updated across {len(PREFS)} prefectures"))
    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
