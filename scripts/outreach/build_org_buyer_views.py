"""Build BigQuery views for org buyers + generate outreach CSV."""
import sqlite3
from google.cloud import bigquery
import csv
from pathlib import Path

db = sqlite3.connect("E:/grid/churches.db")
db.row_factory = sqlite3.Row

client = bigquery.Client(project="american-rel-infra")
DATASET = "American_Religious_Infrastructure"
PROJECT = "american-rel-infra"
BQ_BASE = f"https://console.cloud.google.com/bigquery?project={PROJECT}&p={PROJECT}&d={DATASET}"

OUT = Path("outputs/outreach/org_buyers.csv")

# ============================================================
# 1. FIND ORG BUYERS WITH EMAIL
# ============================================================
print("Finding org buyers with email...")

buyers = db.execute("""
    SELECT c.id, c.name, c.city, c.state, c.country, c.tradition, c.faith,
           (SELECT value FROM church_contact_values WHERE church_id=c.id AND contact_type='email' LIMIT 1) as email,
           (SELECT value FROM church_contact_values WHERE church_id=c.id AND contact_type='website' LIMIT 1) as website,
           ce.diocese, ce.archdiocese, ce.synod, ce.conference, ce.presbytery, ce.district, ce.association
    FROM churches c
    LEFT JOIN church_enrichment ce ON ce.church_id = c.id
    WHERE c.country = 'US'
      AND c.id IN (SELECT church_id FROM church_contact_values WHERE contact_type='email')
      AND (c.name LIKE '%DIOCES%' OR c.name LIKE '%CHANCERY%' 
           OR c.name LIKE '%SYNOD%' OR c.name LIKE '%PRESBYTERY%'
           OR c.name LIKE '%CONFERENCE%' OR c.name LIKE '%DISTRICT OFFICE%'
           OR c.name LIKE '%HEADQUARTER%' OR c.name LIKE '%GENERAL COUNCIL%'
           OR c.name LIKE '%NATIONAL OFFICE%' OR c.name LIKE '%ARCHDIOCES%'
           OR c.name LIKE '%EPISCOPAL%OFFICE%')
    ORDER BY c.tradition, c.state
""").fetchall()

print(f"  Found {len(buyers)} organizational HQ offices with email\n")

# ============================================================
# 2. FOR EACH, DETERMINE WHAT CHURCHES THEY OVERSEE
# ============================================================
leads = []

for b in buyers:
    name = b["name"]
    email = b["email"]
    tradition = b["tradition"] or "Christian"
    diocese = b["diocese"]
    synod = b["synod"]
    presbytery = b["presbytery"]
    district = b["district"]
    association = b["association"]
    conference = b["conference"]
    state = b["state"]
    city = b["city"]
    
    # Build WHERE clause to find churches under this org
    where_parts = []
    church_count = 0
    
    if diocese and diocese != "":
        # Catholic: churches in same diocese
        cnt = db.execute("SELECT COUNT(*) FROM church_enrichment WHERE diocese=?", (diocese,)).fetchone()[0]
        if cnt > 5:
            where_parts.append(f"diocese = '{diocese.replace(chr(39), chr(39)+chr(39))}'")
            church_count = cnt
    elif synod and synod != "":
        cnt = db.execute("SELECT COUNT(*) FROM church_enrichment WHERE synod=?", (synod,)).fetchone()[0]
        if cnt > 5:
            where_parts.append(f"synod = '{synod.replace(chr(39), chr(39)+chr(39))}'")
            church_count = cnt
    elif presbytery and presbytery != "":
        cnt = db.execute("SELECT COUNT(*) FROM church_enrichment WHERE presbytery=?", (presbytery,)).fetchone()[0]
        if cnt > 5:
            where_parts.append(f"presbytery = '{presbytery.replace(chr(39), chr(39)+chr(39))}'")
            church_count = cnt
    elif district and district != "":
        cnt = db.execute("SELECT COUNT(*) FROM church_enrichment WHERE district=?", (district,)).fetchone()[0]
        if cnt > 5:
            where_parts.append(f"district = '{district.replace(chr(39), chr(39)+chr(39))}'")
            church_count = cnt
    elif state:
        # Fallback: same-state same-tradition
        cnt = db.execute("SELECT COUNT(*) FROM churches WHERE state=? AND tradition LIKE ?", 
                        (state, f"%{tradition}%")).fetchone()[0]
        if cnt > 5:
            where_parts.append(f"state = '{state}'")
            where_parts.append(f"tradition LIKE '%{tradition}%'")
            church_count = cnt
    
    if church_count < 10:
        continue  # Skip tiny orgs
    
    # Create BigQuery view
    view_id = f"demo_{b['id']}"
    view_name = f"{PROJECT}.{DATASET}.{view_id}"
    
    # Build WHERE for BQ (use churches table not enrichment)
    bq_where = ""
    if diocese and diocese != "":
        safe_diocese = diocese.replace("'", "\\'")
        bq_where = f"id IN (SELECT church_id FROM `{PROJECT}.{DATASET}.church_enrichment` WHERE diocese = '{safe_diocese}')"
    elif synod and synod != "":
        safe_synod = synod.replace("'", "\\'")
        bq_where = f"id IN (SELECT church_id FROM `{PROJECT}.{DATASET}.church_enrichment` WHERE synod = '{safe_synod}')"
    else:
        safe_state = state.replace("'", "\\'") if state else ""
        bq_where = f"state = '{safe_state}' AND tradition LIKE '%{tradition}%'"
    
    sql = f"""
    CREATE OR REPLACE VIEW `{view_name}` AS
    SELECT id, name, faith, tradition, landmark_type, address, city, state, zip, country,
           latitude, longitude, ntee_code, confidence_score, county, county_fips_5
    FROM `{PROJECT}.{DATASET}.churches`
    WHERE {bq_where}
    """
    
    try:
        client.query(sql).result()
        bq_link = f"{BQ_BASE}&t={view_id}&page=table"
        org_label = diocese or synod or presbytery or district or f"{tradition} {state}"
        
        leads.append({
            "org_name": name,
            "org_label": org_label,
            "email": email,
            "tradition": tradition,
            "city": city or "",
            "state": state or "",
            "church_count": church_count,
            "bq_view": view_id,
            "bq_link": bq_link,
        })
        print(f"  ✅ {name[:45]:45s} | {org_label:25s} | {church_count:>6,} churches | {email}")
    except Exception as e:
        print(f"  ❌ {name[:45]:45s} | ERROR: {str(e)[:60]}")

# ============================================================
# 3. WRITE OUTREACH CSV
# ============================================================
print(f"\nWriting {len(leads)} leads to {OUT}...")

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["org_name","org_label","email","tradition","city","state","church_count","bq_view","bq_link"])
    w.writeheader()
    w.writerows(leads)

print(f"\nDone! {len(leads)} org buyers with BigQuery views ready.")
print(f"CSV: {OUT}")
print(f"\nSample BQ link: {leads[0]['bq_link'] if leads else 'N/A'}")

db.close()
