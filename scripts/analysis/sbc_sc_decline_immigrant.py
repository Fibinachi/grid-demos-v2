#!/usr/bin/env python3
"""
SCBC Report: 25 Declining SC SBC Churches Positioned for Immigrant Congregations

Identifies Southern Baptist Convention churches in rural South Carolina that are:
  1. In non-metro counties (RUCC 4-9) with declining SBC adherents (ARDA 2010->2020)
  2. Near immigrant populations within a 15-min drive (15km radius proxy)
  3. Have viable facilities (building, parking) to host a new congregation
  4. Ranked by composite rural sustainability + opportunity score

Outputs:
  - reports/scbc_immigrant/scbc_decline_immigrant_rural_report.md
  - reports/scbc_immigrant/scbc_decline_immigrant_rural_data.csv
  - reports/scbc_immigrant/scbc_decline_immigrant_rural_map.html
"""
import sqlite3, csv, os, json
from datetime import datetime
import pandas as pd
import numpy as np

DB = r"E:\grid\churches.db"
OUT_DIR = r"E:\grid\reports\scbc_immigrant"
CATCHMENT = r"E:\grid\data\catchment_euclidean.parquet"
TOP_N = 25

os.makedirs(OUT_DIR, exist_ok=True)
now_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")

print("=== SCBC Immigrant Congregation Opportunity Report ===")
print(f"  Started: {now_str}\n")

# ── Load catchment data ────────────────────────────────────────────
print("[1/6] Loading 15km catchment data...")
catchment = pd.read_parquet(CATCHMENT)
catchment = catchment.set_index("church_rowid")
print(f"  {len(catchment):,} churches with catchment data")

# ── Connect to DB ──────────────────────────────────────────────────
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row
c = db.cursor()

# ── Build ARDA decline lookup ──────────────────────────────────────
print("[2/6] Building ARDA SBC county decline lookup...")
c.execute("""
    SELECT a20.county_fips, cl.county_name,
           a20.arda_adherents as adh2020, a10.arda_adherents as adh2010,
           a20.arda_congregations as cong2020, a10.arda_congregations as cong2010
    FROM arda_counts a20
    LEFT JOIN arda_counts_2010 a10
      ON a20.county_fips = a10.county_fips AND a20.denom_code = a10.denom_code
    JOIN county_fips_lookup cl ON a20.county_fips = cl.county_fips
    WHERE a20.denom_code = 'SBC' AND cl.state_fips = '45'
""")
arda = {}
for r in c.fetchall():
    pct = ((r["adh2010"] - r["adh2020"]) / r["adh2010"] * 100.0) if (r["adh2010"] and r["adh2010"] > 0 and r["adh2020"] is not None) else 0.0
    arda[r["county_fips"]] = {
        "name": r["county_name"], "adh2020": r["adh2020"], "adh2010": r["adh2010"],
        "cong2020": r["cong2020"], "cong2010": r["cong2010"], "pct_decline": pct,
    }
print(f"  {len(arda)} SC counties with ARDA SBC data")

# ── Load ZIP immigrant data ────────────────────────────────────────
print("[3/6] Loading ZIP-level immigrant demographics...")
c.execute("SELECT zip5, hisp_pct, asian_pct, total_pop, median_hh_income, poverty_rate FROM census_zip_data")
zip_lookup = {}
for r in c.fetchall():
    if r["zip5"] and r["total_pop"] and r["total_pop"] > 0:
        zip_lookup[r["zip5"]] = {
            "hisp_pct": r["hisp_pct"] or 0, "asian_pct": r["asian_pct"] or 0,
            "total_pop": r["total_pop"], "median_income": r["median_hh_income"],
            "poverty_rate": r["poverty_rate"] or 0,
        }
print(f"  {len(zip_lookup):,} ZIP codes loaded")

# ── Query SC SBC churches + ACS data (RURAL ONLY) ──────────────────
print("[4/6] Querying rural SC SBC churches (RUCC 4-9) with ACS and catchment data...")
query = """
SELECT
    c.rowid, c.id, c.name, c.city, c.state, c.address, c.zip5 as zip,
    c.latitude, c.longitude,
    c.county_fips_5, c.county, c.source,
    c.pop_15km, c.building_sqft, c.capacity_estimate, c.parking_spots,
    c.building_year, c.closed_year,
    ce.tract_fips,
    ce.county_hispanic_pct, ce.county_asian_pct,
    ce.attendance_arda, ce.diocese, ce.association,
    rc.rucc_code, rc.description as rucc_description,
    cus.acs_total_pop, cus.acs_median_income, cus.acs_poverty_rate,
    cus.acs_median_age, cus.acs_unemployment_rate,
    cus.acs_median_home_value,
    cus.acs_hispanic_pop, cus.acs_asian_pop,
    cus.acs_white_pop, cus.acs_black_pop,
    cus.acs_bachelors_count
FROM churches c
JOIN rucc_codes rc ON c.county_fips_5 = rc.fips
LEFT JOIN church_enrichment ce ON c.id = ce.church_id
LEFT JOIN church_census_us cus ON c.id = cus.church_id
WHERE c.taxonomy_id = 314
  AND c.state = 'SC'
  AND rc.rucc_code >= 4
ORDER BY c.name
"""
rows = c.execute(query).fetchall()
print(f"  {len(rows):,} SC SBC churches")

# ── Get contacts ───────────────────────────────────────────────────
print("[5/6] Loading contacts (website/phone/email)...")
church_ids = [r["id"] for r in rows]
contacts = {}
batch_size = 500
for i in range(0, len(church_ids), batch_size):
    batch = church_ids[i:i+batch_size]
    placeholders = ",".join("?" * len(batch))
    c.execute(f"""
        SELECT church_id, contact_type, value
        FROM church_contact_values
        WHERE church_id IN ({placeholders})
          AND contact_type IN ('website','phone','email')
          AND is_primary = 1
    """, batch)
    for r in c.fetchall():
        cid = r["church_id"]
        if cid not in contacts:
            contacts[cid] = {}
        contacts[cid][r["contact_type"]] = r["value"]
print(f"  {len(contacts):,} churches with contacts")

# ── Score each church ──────────────────────────────────────────────
print("[6/6] Scoring and ranking...")
results = []
for i, r in enumerate(rows):
    rowid = r["rowid"]
    church_id = r["id"]
    county_fips = r["county_fips_5"]
    zip5 = r["zip"]

    # --- County ARDA decline ---
    a = arda.get(county_fips, {})
    county_decline = a.get("pct_decline", 0.0)

    # --- 15km catchment ---
    catchment_pop = 0
    if rowid in catchment.index:
        catchment_pop = int(catchment.at[rowid, "pop_15km"])

    # --- Immigrant % (ZIP level, fallback to tract ACS) ---
    zd = zip_lookup.get(zip5, {})
    zip_hisp = zd.get("hisp_pct", 0) or 0
    zip_asian = zd.get("asian_pct", 0) or 0
    zip_imm_pct = zip_hisp + zip_asian

    tract_hisp = r["acs_hispanic_pop"] or 0
    tract_asian = r["acs_asian_pop"] or 0
    tract_total = r["acs_total_pop"] or 1
    tract_imm_pct = ((tract_hisp + tract_asian) / tract_total * 100) if tract_total > 0 else 0

    if zip_imm_pct > 0:
        imm_pct = zip_imm_pct
        imm_source = "ZIP"
    else:
        imm_pct = tract_imm_pct
        imm_source = "tract"

    # --- Estimated immigrant pop in 15km ---
    est_imm_pop_15km = int(catchment_pop * imm_pct / 100.0)

    # --- Opportunity score (0-100) — rural-adjusted ---
    # 35% immigrant presence, 30% SBC decline, 15% catchment, 20% facility viability
    imm_norm = min(imm_pct / 15.0, 1.0)         # lower bar for rural (15% vs 20%)
    dec_norm = min(county_decline / 40.0, 1.0)   # lower bar for decline (40% vs 50%)
    cat_norm = min(catchment_pop / 200000.0, 1.0) # rural scale (200K vs 500K)
    # Facility: building exists + parking + capacity estimate
    bldg = 1.0 if (r["building_sqft"] or 0) > 0 else 0.5
    park = min((r["parking_spots"] or 0) / 50.0, 1.0)
    cap  = min((r["capacity_estimate"] or 0) / 200.0, 1.0)
    fac_norm = bldg * 0.4 + park * 0.3 + cap * 0.3
    score = round(imm_norm * 35.0 + dec_norm * 30.0 + cat_norm * 15.0 + fac_norm * 20.0, 1)

    # --- Contacts ---
    cc = contacts.get(church_id, {})
    website = cc.get("website", "")
    phone = cc.get("phone", "")
    email = cc.get("email", "")

    results.append({
        "rowid": rowid, "id": church_id,
        "name": r["name"] or "", "city": r["city"] or "", "state": "SC",
        "address": r["address"] or "", "zip": zip5 or "",
        "county": a.get("name", r["county"] or ""),
        "county_fips": county_fips or "",
        "latitude": r["latitude"], "longitude": r["longitude"],
        "county_decline_pct": round(county_decline, 1),
        "arda_adh_2020": a.get("adh2020"), "arda_adh_2010": a.get("adh2010"),
        "zip_hisp_pct": round(zip_hisp, 1), "zip_asian_pct": round(zip_asian, 1),
        "zip_immigrant_pct": round(zip_imm_pct, 1),
        "tract_immigrant_pct": round(tract_imm_pct, 1),
        "immigrant_source": imm_source,
        "catchment_pop_15km": catchment_pop,
        "est_immigrant_pop_15km": est_imm_pop_15km,
        "acs_total_pop": r["acs_total_pop"],
        "acs_median_income": r["acs_median_income"],
        "acs_median_age": r["acs_median_age"],
        "acs_poverty_rate": r["acs_poverty_rate"],
        "acs_unemployment_rate": r["acs_unemployment_rate"],
        "acs_median_home_value": r["acs_median_home_value"],
        "acs_hispanic_pop": tract_hisp, "acs_asian_pop": tract_asian,
        "tract_fips": r["tract_fips"] or "",
        "county_hispanic_pct": r["county_hispanic_pct"],
        "county_asian_pct": r["county_asian_pct"],
        "rucc_description": r["rucc_description"] or "",
        "website": website, "phone": phone, "email": email,
        "source": r["source"] or "",
        "attendance_arda": r["attendance_arda"],
        "diocese": r["diocese"] or "", "association": r["association"] or "",
        "building_sqft": r["building_sqft"],
        "capacity_estimate": r["capacity_estimate"],
        "parking_spots": r["parking_spots"],
        "building_year": r["building_year"],
        "closed_year": r["closed_year"],
        "opportunity_score": score,
    })

    if (i + 1) % 300 == 0:
        print(f"  ...{i+1}/{len(rows)} scored")

# ── Sort, then take top 3 per county for geographic diversity ─────
results.sort(key=lambda x: x["opportunity_score"], reverse=True)

# Cap at 3 per county
MAX_PER_COUNTY = 3
county_counts = {}
diverse = []
for r in results:
    county = r["county"]
    if county not in county_counts:
        county_counts[county] = 0
    if county_counts[county] < MAX_PER_COUNTY:
        diverse.append(r)
        county_counts[county] += 1
    if len(diverse) >= TOP_N:
        break

top = diverse

# County breakdown for summary
county_breakdown = {}
for r in top:
    c = r["county"]
    county_breakdown[c] = county_breakdown.get(c, 0) + 1

print(f"\n  Scored {len(results):,} churches")
print(f"  Top score: {top[0]['opportunity_score']:.1f} - {top[0]['name'][:55]}")
print(f"  #25 score: {top[-1]['opportunity_score']:.1f} - {top[-1]['name'][:55]}")
print(f"  Counties represented: {len(county_breakdown)}")
for c, n in sorted(county_breakdown.items(), key=lambda x: -top[[r['county'] for r in top].index(x[0])]['opportunity_score']):
    print(f"    {c}: {n} churches")

# ── Stats ──────────────────────────────────────────────────────────
avg_dec = sum(r["county_decline_pct"] for r in top) / TOP_N
avg_imm = sum(r["zip_immigrant_pct"] for r in top) / TOP_N
avg_eip = sum(r["est_immigrant_pop_15km"] for r in top) / TOP_N
n_web = sum(1 for r in top if r["website"])
n_ph = sum(1 for r in top if r["phone"])
n_em = sum(1 for r in top if r["email"])

# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════
def pct2(v):
    return f"{v*100:.1f}%" if v is not None else "N/A"
def dollar(v):
    return f"${v:,.0f}" if v is not None else "N/A"
def comma(v):
    return f"{v:,.0f}" if v is not None else "N/A"
def fmt(v, d="--"):
    return str(v) if v and str(v).strip() else d

# ═══════════════════════════════════════════════════════════════════
# Markdown Report
# ═══════════════════════════════════════════════════════════════════
print("\nGenerating Markdown report...")

md = []
md.append("# SCBC Rural Immigrant Congregation Opportunity Report")
md.append("")
md.append(f"**Generated:** {now_str}")
md.append("")
md.append("**Purpose:** Identify 25 declining Southern Baptist Convention churches in ")
md.append("**rural South Carolina** (non-metro counties, RUCC 4-9) strategically positioned ")
md.append("near immigrant populations. These are candidates for sustainable immigrant ")
md.append("congregation planting in rural America -- where lower costs, available facilities, ")
md.append("and community need create conditions for long-term viability.")
md.append("")
md.append("---")
md.append("")
md.append("## Methodology")
md.append("")
md.append("### Composite Rural Opportunity Score (0-100)")
md.append("")
md.append("| Factor | Weight | Data Source |")
md.append("|--------|--------|-------------|")
md.append("| **Immigrant presence** | 35% | ZIP-level Hispanic% + Asian% (ACS 5-year), capped at 15% rural threshold |")
md.append("| **SBC decline** | 30% | County SBC adherent change 2010->2020 (ARDA), capped at 40% |")
md.append("| **Population reach** | 15% | 15km radius catchment (Census 2020 tracts), capped at 200K rural scale |")
md.append("| **Facility viability** | 20% | Building sq ft, parking spots, capacity estimate from property data |")
md.append("")
md.append("Rural-adjusted thresholds reflect the reality that immigrant percentages and ")
md.append("total populations are lower outside metro areas, but facility costs and ")
md.append("competition are also lower -- creating sustainable conditions for immigrant ")
md.append("congregations with smaller numeric reach.")
md.append("")
md.append("### Geographic Diversity Capping")
md.append("")
md.append(f"Results are capped at **3 churches per county** to ensure geographic diversity ")
md.append(f"across rural South Carolina. Without this cap, high-scoring counties like Newberry ")
md.append(f"would dominate the list. The final {TOP_N} represent {len(county_breakdown)} counties, ")
md.append("giving SCBC actionable options statewide.")
md.append("")
md.append("---")
md.append("")
md.append("## Executive Summary")
md.append("")
md.append(f"The {TOP_N} churches identified span **{len(county_breakdown)} rural counties** where SBC adherents declined ")
md.append(f"an average of **{avg_dec:.1f}%** from 2010 to 2020. Their 15km catchment areas ")
md.append(f"average **{avg_imm:.1f}%** Hispanic + Asian population, representing an estimated ")
md.append(f"**{comma(avg_eip)}** potential immigrant residents nearby.")
md.append("")
md.append(f"- **{n_web}/{TOP_N}** have websites")
md.append(f"- **{n_ph}/{TOP_N}** have phone numbers")
md.append(f"- **{n_em}/{TOP_N}** have email addresses")
md.append("")
county_list = sorted(county_breakdown.keys(), key=lambda c: -max((r["opportunity_score"] for r in top if r["county"]==c), default=0))
md.append("**Counties represented:** " + ", ".join(f"{c} ({county_breakdown[c]})" for c in county_list))
md.append("")
md.append("---")
md.append("")
md.append("## Top 25 Rural SC SBC Churches -- Ranked by Opportunity")
md.append("")
md.append("*(Max 3 per county for geographic diversity)*")
md.append("")
md.append("| # | Church | City | County | SBC Decline | Immig.% | Est.Immig.Pop | Score |")
md.append("|---|--------|------|--------|-------------|---------|---------------|-------|")
for i, r in enumerate(top, 1):
    name = r["name"][:42] if r["name"] else "?"
    city = r["city"][:14] if r["city"] else ""
    county = r["county"][:18] if r["county"] else ""
    md.append(f"| {i} | {name} | {city} | {county} | {r['county_decline_pct']:.0f}% | {r['zip_immigrant_pct']:.1f}% | {comma(r['est_immigrant_pop_15km'])} | {r['opportunity_score']} |")

md.append("")
md.append("---")
md.append("")

# ── Detailed profiles ──────────────────────────────────────────────
md.append("## Detailed Church Profiles")
md.append("")
for i, r in enumerate(top, 1):
    md.append(f"### {i}. {r['name']}")
    md.append("")
    loc = []
    if r["address"]: loc.append(r["address"])
    if r["city"]: loc.append(r["city"])
    loc.append("SC")
    if r["zip"]: loc.append(r["zip"])
    md.append(f"**Location:** {', '.join(loc)}")
    md.append("")
    if r["latitude"]:
        md.append(f"**GPS:** {r['latitude']:.5f}, {r['longitude']:.5f}")
        md.append("")

    md.append("#### Opportunity Assessment")
    md.append("")
    md.append("| Metric | Value |")
    md.append("|--------|-------|")
    md.append(f"| **Opportunity Score** | {r['opportunity_score']:.1f} / 100 |")
    md.append(f"| **County SBC Decline (2010->2020)** | {r['county_decline_pct']:.1f}% ({comma(r['arda_adh_2020'])} adh vs {comma(r['arda_adh_2010'])} in 2010) |")
    md.append(f"| **ZIP Immigrant %** | {r['zip_immigrant_pct']:.1f}% (Hisp {r['zip_hisp_pct']:.1f}% + Asian {r['zip_asian_pct']:.1f}%) |")
    md.append(f"| **15km Catchment Population** | {comma(r['catchment_pop_15km'])} |")
    md.append(f"| **Est. Immigrant Pop in 15km** | {comma(r['est_immigrant_pop_15km'])} |")
    md.append("")

    md.append("#### Community Demographics")
    md.append("")
    md.append("| Measure | Tract | County |")
    md.append("|---------|-------|--------|")
    ht = r['acs_hispanic_pop'] / max(r['acs_total_pop'] or 1, 1) * 100 if r['acs_hispanic_pop'] else None
    at = r['acs_asian_pop'] / max(r['acs_total_pop'] or 1, 1) * 100 if r['acs_asian_pop'] else None
    chp = r['county_hispanic_pct']
    cap = r['county_asian_pct']
    md.append(f"| **Hispanic %** | {f'{ht:.1f}%' if ht else 'N/A'} | {f'{chp:.1f}%' if chp else 'N/A'} |")
    md.append(f"| **Asian %** | {f'{at:.1f}%' if at else 'N/A'} | {f'{cap:.1f}%' if cap else 'N/A'} |")
    md.append(f"| **Poverty Rate** | {pct2(r['acs_poverty_rate'])} | -- |")
    md.append(f"| **Median Household Income** | {dollar(r['acs_median_income'])} | -- |")
    md.append(f"| **Median Age** | {fmt(r['acs_median_age'])} | -- |")
    md.append(f"| **Unemployment** | {pct2(r['acs_unemployment_rate'])} | -- |")
    md.append(f"| **Total Population** | {comma(r['acs_total_pop'])} | -- |")
    if r["tract_fips"]:
        md.append(f"| **Census Tract** | [{r['tract_fips']}](https://censusreporter.org/profiles/14000US{r['tract_fips']}/) | -- |")
    md.append("")

    md.append("#### Church Profile")
    md.append("")
    md.append("| Field | Value |")
    md.append("|-------|-------|")
    md.append(f"| **Website** | {fmt(r['website'])} |")
    md.append(f"| **Phone** | {fmt(r['phone'])} |")
    md.append(f"| **Email** | {fmt(r['email'])} |")
    md.append(f"| **Source** | {fmt(r['source'])} |")
    md.append(f"| **ARDA Attendance** | {fmt(r['attendance_arda'])} |")
    md.append(f"| **Association** | {fmt(r['association'])} |")
    md.append(f"| **Building Sq Ft** | {fmt(r['building_sqft'])} |")
    md.append(f"| **Capacity Est.** | {fmt(r['capacity_estimate'])} |")
    md.append(f"| **Parking Spots** | {fmt(r['parking_spots'])} |")
    md.append(f"| **Building Year** | {fmt(r['building_year'])} |")
    md.append(f"| **Closed Year** | {fmt(r['closed_year'])} |")
    md.append(f"| **RUCC** | {fmt(r['rucc_description'])} |")
    md.append("")

    md.append("---")
    md.append("")

# ── Recommendations ────────────────────────────────────────────────
md.append("## Recommendations for SCBC")
md.append("")
md.append("### Rural Sustainability Framework")
md.append("")
md.append("Rural immigrant congregations face different economics than urban ones. Lower ")
md.append("facility costs and less market competition mean smaller congregations can be ")
md.append("sustainable. The key is identifying churches with:")
md.append("")
md.append("- **Viable facilities** (building exists, parking available, capacity for growth)")
md.append("- **Welcoming communities** (rural areas often have stronger social cohesion)")
md.append("- **Economic opportunity** (agriculture, meatpacking, manufacturing draw immigrant workers)")
md.append("")
tier1 = [r for r in top if r["opportunity_score"] >= 70]
tier2 = [r for r in top if 50 <= r["opportunity_score"] < 70]
tier3 = [r for r in top if r["opportunity_score"] < 50]

md.append(f"**Tier 1 -- Immediate Outreach (Score >= 70):** {len(tier1)} churches")
if tier1:
    md.append("")
    for r in tier1:
        idx = next(i for i, x in enumerate(top, 1) if x["rowid"] == r["rowid"])
        md.append(f"- **#{idx} {r['name']}** -- {r['city']}, {r['county']} County. ")
        md.append(f"Score {r['opportunity_score']:.1f}. ")
        md.append(f"Estimated {comma(r['est_immigrant_pop_15km'])} immigrant residents within 15km. ")
        if r.get("building_sqft"):
            md.append(f"{comma(r['building_sqft'])} sq ft, {r.get('parking_spots') or '?'} parking spots. ")
    md.append("")

md.append(f"**Tier 2 -- Strong Potential (Score 50-69):** {len(tier2)} churches")
md.append(f"**Tier 3 -- Monitor (Score < 50):** {len(tier3)} churches")
md.append("")

md.append("### Action Items")
md.append("")
md.append("1. **Contact top 5 rural churches** to gauge interest in hosting an immigrant congregation")
md.append("2. **Conduct site visits** to assess facility viability -- sanctuary, classrooms, parking, kitchen")
md.append("3. **Map local immigrant employers** -- farms, processing plants, construction, manufacturing")
md.append("4. **Partner with NAMB** for rural church planting resources and Send Network assessment")
md.append("5. **Identify bi-vocational pastors** who can serve smaller rural immigrant congregations")
md.append("6. **Evaluate language needs** -- Spanish (most likely), plus Korean, Vietnamese, Tagalog ")
md.append("   based on local industry workforce patterns")
md.append("")
md.append("---")
md.append("")
md.append(f"*Report generated {now_str} by GRID (Global Religious Infrastructure Database)*  ")
md.append("*Data: ACS 2019-2023 5-year, ARDA US Religion Census 2010 & 2020, Census 2020 tracts*")

md_path = os.path.join(OUT_DIR, "scbc_decline_immigrant_rural_report.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md))
print(f"  Markdown: {md_path}")

# ═══════════════════════════════════════════════════════════════════
# CSV
# ═══════════════════════════════════════════════════════════════════
csv_path = os.path.join(OUT_DIR, "scbc_decline_immigrant_rural_data.csv")
csv_fields = [
    "rank","name","city","county","opportunity_score",
    "county_decline_pct","zip_immigrant_pct","zip_hisp_pct","zip_asian_pct",
    "catchment_pop_15km","est_immigrant_pop_15km",
    "acs_poverty_rate","acs_median_income","acs_median_age","acs_unemployment_rate",
    "address","zip","latitude","longitude",
    "website","phone","email","source",
    "attendance_arda","association","building_sqft","capacity_estimate","parking_spots",
    "building_year","closed_year","tract_fips","rucc_description",
]
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
    w.writeheader()
    for i, r in enumerate(top, 1):
        r["rank"] = i
        w.writerow(r)
print(f"  CSV:      {csv_path}")

# ═══════════════════════════════════════════════════════════════════
# Leaflet Map
# ═══════════════════════════════════════════════════════════════════
print("Generating Leaflet map...")

features = []
for i, r in enumerate(top, 1):
    if not r["latitude"] or not r["longitude"]:
        continue
    score = r["opportunity_score"]
    if score >= 70:
        color = "#e53e3e"
    elif score >= 50:
        color = "#dd6b20"
    else:
        color = "#3182ce"

    popup = (
        f"<b>#{i} {r['name']}</b><br>"
        f"{r['city']}, SC {r['zip']}<br>"
        f"<b>Score:</b> {score:.1f}/100<br>"
        f"<b>SBC Decline:</b> {r['county_decline_pct']:.1f}%<br>"
        f"<b>Immigrant %:</b> {r['zip_immigrant_pct']:.1f}%<br>"
        f"<b>Est. Immigrant Pop (15km):</b> {comma(r['est_immigrant_pop_15km'])}<br>"
        + (f"<a href='{r['website']}' target='_blank'>Website</a>" if r["website"] else "")
    )

    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
        "properties": {
            "name": r["name"], "city": r["city"], "rank": i,
            "score": score, "decline": r["county_decline_pct"],
            "immigrant_pct": r["zip_immigrant_pct"],
            "immigrant_pop": r["est_immigrant_pop_15km"],
            "color": color, "popup": popup,
        },
    })

geojson = {"type": "FeatureCollection", "features": features}
geojson_path = os.path.join(OUT_DIR, "scbc_immigrant_rural_data.json")
with open(geojson_path, "w") as f:
    json.dump(geojson, f)

sc_lat, sc_lon = 33.8361, -81.1637
map_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SCBC Immigrant Congregation Opportunities</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
  html,body{{margin:0;padding:0;height:100%;font-family:'Segoe UI',sans-serif;}}
  #map{{width:100%;height:100%;}}
  .legend{{background:white;padding:10px 14px;border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,0.2);font-size:13px;line-height:1.7;}}
  .legend i{{width:16px;height:16px;display:inline-block;margin-right:6px;border-radius:50%;vertical-align:middle;}}
  .legend b{{display:block;margin-bottom:4px;}}
  .panel{{position:absolute;top:10px;right:10px;background:white;padding:12px 16px;border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,0.2);max-width:300px;font-size:12px;z-index:1000;}}
  .panel h2{{margin:0 0 6px;font-size:15px;}}
  .panel p{{margin:3px 0;}}
</style>
</head>
<body>
<div id="map"></div>
<div class="panel">
  <h2>SCBC Rural Immigrant<br>Congregation Opportunities</h2>
  <p><b>{TOP_N} rural SC SBC churches</b> ranked</p>
  <p>Avg SBC decline: <b>{avg_dec:.1f}%</b></p>
  <p>Avg immigrant pop (15km): <b>{comma(avg_eip)}</b></p>
  <p style="margin-top:8px;font-size:10px;color:#666;">Generated {now_str}<br>GRID</p>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
fetch('scbc_immigrant_rural_data.json')
  .then(r=>r.json())
  .then(data=>{{
    const map=L.map('map').setView([{sc_lat},{sc_lon}],8);
    L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{
      attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
      subdomains:'abcd',maxZoom:19
    }}).addTo(map);
    L.geoJSON(data,{{
      pointToLayer:(f,ll)=>{{
        const s=Math.max(12,Math.min(26,f.properties.score*0.28));
        return L.circleMarker(ll,{{radius:s,fillColor:f.properties.color,color:'#333',weight:1.5,opacity:1,fillOpacity:0.8}});
      }},
      onEachFeature:(f,l)=>{{
        l.bindPopup(f.properties.popup);
        l.bindTooltip('#'+f.properties.rank+' '+f.properties.name,{{direction:'top',offset:[0,-8]}});
      }}
    }}).addTo(map);
    const leg=L.control({{position:'bottomleft'}});
    leg.onAdd=()=>{{
      const d=L.DomUtil.create('div','legend');
      d.innerHTML='<b>Opportunity Score</b><i style="background:#e53e3e"></i> High (>=70)<br><i style="background:#dd6b20"></i> Medium (50-69)<br><i style="background:#3182ce"></i> Monitor (<50)<br><small>Marker size = score</small>';
      return d;
    }};
    leg.addTo(map);
  }});
</script>
</body>
</html>"""

map_path = os.path.join(OUT_DIR, "scbc_decline_immigrant_rural_map.html")
with open(map_path, "w", encoding="utf-8") as f:
    f.write(map_html)
print(f"  Map:      {map_path}")
print(f"  GeoJSON:  {geojson_path}")

# ── Summary ────────────────────────────────────────────────────────
print()
print("=" * 60)
print(f"  REPORT COMPLETE")
print("=" * 60)
print(f"  Markdown: {md_path}")
print(f"  CSV:      {csv_path}")
print(f"  Map:      {map_path}")
print()
print("  Top 5:")
for i, r in enumerate(top[:5], 1):
    print(f"  #{i} [{r['opportunity_score']:.1f}] {r['name'][:55]}")
    print(f"       {r['city']}, {r['county']} Co. | Decline {r['county_decline_pct']:.0f}% | Immig {r['zip_immigrant_pct']:.1f}% | Est pop {r['est_immigrant_pop_15km']:,}")

db.close()
print("\n[DONE]")
