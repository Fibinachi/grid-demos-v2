"""
Build Lutheran synod/district hierarchy from Wikipedia data.
Creates synod/district nodes in lutheran_hierarchy and links congregations by state.
"""
import sqlite3, json
from datetime import datetime, timezone

db = sqlite3.connect("churches.db")
cur = db.cursor()

now = datetime.now(timezone.utc).isoformat()

# ── ELCA Synods: state coverage mapping ──
elca_synod_states = {
    "Alaska Synod": {"states": ["AK"], "abbrev": "AK"},
    "Northwest Washington Synod": {"states": ["WA"]},
    "Southwestern Washington Synod": {"states": ["WA"]},
    "Oregon Synod": {"states": ["OR"]},
    "Montana Synod": {"states": ["MT"]},
    "Sierra Pacific Synod": {"states": ["CA", "NV"]},
    "Southwest California Synod": {"states": ["CA"]},
    "Pacifica Synod": {"states": ["CA", "HI"]},
    "Grand Canyon Synod": {"states": ["AZ", "NV"]},
    "Rocky Mountain Synod": {"states": ["CO", "NM", "UT", "WY"]},
    "Western North Dakota Synod": {"states": ["ND"]},
    "Eastern North Dakota Synod": {"states": ["ND"]},
    "South Dakota Synod": {"states": ["SD"]},
    "Northwestern Minnesota Synod": {"states": ["MN"]},
    "Northeastern Minnesota Synod": {"states": ["MN"]},
    "Southwestern Minnesota Synod": {"states": ["MN"]},
    "Minneapolis Area Synod": {"states": ["MN"]},
    "Saint Paul Area Synod": {"states": ["MN"]},
    "Southeastern Minnesota Synod": {"states": ["MN"]},
    "Nebraska Synod": {"states": ["NE"]},
    "Central States Synod": {"states": ["KS", "MO"]},
    "Arkansas-Oklahoma Synod": {"states": ["AR", "OK"]},
    "Northern Texas-Northern Louisiana Synod": {"states": ["TX", "LA"]},
    "Southwestern Texas Synod": {"states": ["TX"]},
    "Texas-Louisiana Gulf Coast Synod": {"states": ["TX", "LA"]},
    "Metropolitan Chicago Synod": {"states": ["IL"]},
    "Northern Illinois Synod": {"states": ["IL"]},
    "Central/Southern Illinois Synod": {"states": ["IL"]},
    "Southeastern Iowa Synod": {"states": ["IA"]},
    "Western Iowa Synod": {"states": ["IA"]},
    "Northeastern Iowa Synod": {"states": ["IA"]},
    "Northern Great Lakes Synod": {"states": ["MI"]},
    "Northwest Synod of Wisconsin": {"states": ["WI"]},
    "East-Central Synod of Wisconsin": {"states": ["WI"]},
    "Greater Milwaukee Synod": {"states": ["WI"]},
    "South-Central Synod of Wisconsin": {"states": ["WI"]},
    "La Crosse Area Synod": {"states": ["WI"]},
    "Southeast Michigan Synod": {"states": ["MI"]},
    "North/West Lower Michigan Synod": {"states": ["MI"]},
    "Indiana-Kentucky Synod": {"states": ["IN", "KY"]},
    "Northwestern Ohio Synod": {"states": ["OH"]},
    "Northeastern Ohio Synod": {"states": ["OH"]},
    "Southern Ohio Synod": {"states": ["OH"]},
    "New Jersey Synod": {"states": ["NJ"]},
    "New England Synod": {"states": ["CT", "ME", "MA", "NH", "RI", "VT", "NY"]},
    "Metropolitan New York Synod": {"states": ["NY"]},
    "Upstate New York Synod": {"states": ["NY"]},
    "Northeastern Pennsylvania Synod": {"states": ["PA"]},
    "Southeastern Pennsylvania Synod": {"states": ["PA"]},
    "Slovak Zion Synod": {"states": ["*"], "note": "non-geographic, Slovak heritage"},
    "Northwestern Pennsylvania Synod": {"states": ["PA"]},
    "Southwestern Pennsylvania Synod": {"states": ["PA"]},
    "Allegheny Synod": {"states": ["PA"]},
    "Lower Susquehanna Synod": {"states": ["PA"]},
    "Upper Susquehanna Synod": {"states": ["PA"]},
    "Delaware-Maryland Synod": {"states": ["DE", "MD"]},
    "Metropolitan Washington D.C. Synod": {"states": ["DC", "MD", "VA"]},
    "West Virginia-Western Maryland Synod": {"states": ["WV", "MD"]},
    "Virginia Synod": {"states": ["VA"]},
    "North Carolina Synod": {"states": ["NC"]},
    "South Carolina Synod": {"states": ["SC"]},
    "Southeastern Synod": {"states": ["AL", "GA", "MS", "TN"]},
    "Florida-Bahamas Synod": {"states": ["FL"]},
    "Caribbean Synod": {"states": ["PR", "VI"]},
}

# ── LCMS Districts: state coverage mapping ──
lcms_district_states = {
    "Atlantic District": {"states": ["NY"]},
    "California-Nevada-Hawaii District": {"states": ["CA", "NV", "HI"]},
    "Central Illinois District": {"states": ["IL"]},
    "Eastern District": {"states": ["NY", "PA", "MD"]},
    "English District": {"states": ["*"], "note": "non-geographic, nationwide"},
    "Florida-Georgia District": {"states": ["FL", "GA"]},
    "Indiana District": {"states": ["IN", "KY"]},
    "Iowa District East": {"states": ["IA"]},
    "Iowa District West": {"states": ["IA"]},
    "Kansas District": {"states": ["KS"]},
    "Michigan District": {"states": ["MI"]},
    "Mid-South District": {"states": ["AR", "TN", "KY"]},
    "Minnesota North District": {"states": ["MN", "WI"]},
    "Minnesota South District": {"states": ["MN"]},
    "Missouri District": {"states": ["MO"]},
    "Montana District": {"states": ["MT"]},
    "Nebraska District": {"states": ["NE"]},
    "New England District": {"states": ["CT", "ME", "MA", "NH", "RI", "VT"]},
    "New Jersey District": {"states": ["NJ"]},
    "North Dakota District": {"states": ["ND"]},
    "North Wisconsin District": {"states": ["WI", "MI"]},
    "Northern Illinois District": {"states": ["IL"]},
    "Northwest District": {"states": ["WA", "OR", "ID", "AK"]},
    "Ohio District": {"states": ["OH", "WV", "KY"]},
    "Oklahoma District": {"states": ["OK"]},
    "Pacific Southwest District": {"states": ["AZ", "CA", "NV"]},
    "Rocky Mountain District": {"states": ["CO", "UT", "NM", "TX"]},
    "SELC District": {"states": ["*"], "note": "non-geographic, nationwide"},
    "South Dakota District": {"states": ["SD"]},
    "South Wisconsin District": {"states": ["WI"]},
    "Southeastern District": {"states": ["MD", "DC", "DE", "VA", "NC", "SC", "PA"]},
    "Southern District": {"states": ["LA", "MS", "AL", "FL"]},
    "Southern Illinois District": {"states": ["IL"]},
    "Texas District": {"states": ["TX"]},
    "Wyoming District": {"states": ["WY", "NE", "CO"]},
}

# ── 1. Get HQ hierarchy IDs ──
cur.execute("SELECT id, body FROM lutheran_hierarchy WHERE lutheran_type = 'hq'")
hq_ids = {body: id for id, body in cur.fetchall()}
elca_hq_id = hq_ids.get("ELCA")
lcms_hq_id = hq_ids.get("LCMS")
other_hq_id = hq_ids.get("Other")
print(f"HQ IDs: ELCA={elca_hq_id}, LCMS={lcms_hq_id}, Other={other_hq_id}")

# ── 2. Create synod/district nodes ──
synod_created = 0
district_created = 0

for synod_name, info in elca_synod_states.items():
    states_str = ", ".join(info["states"]) if info["states"][0] != "*" else "Nationwide"
    cur.execute("""
        INSERT INTO lutheran_hierarchy 
        (parent_id, name, lutheran_type, body, state, country, notes, created_at)
        VALUES (?, ?, 'synod', 'ELCA', ?, 'US', ?, ?)
    """, (elca_hq_id, synod_name, states_str, f"ELCA synod covering {states_str}", now))
    synod_created += 1

for district_name, info in lcms_district_states.items():
    states_str = ", ".join(info["states"]) if info["states"][0] != "*" else "Nationwide"
    cur.execute("""
        INSERT INTO lutheran_hierarchy 
        (parent_id, name, lutheran_type, body, state, country, notes, created_at)
        VALUES (?, ?, 'district', 'LCMS', ?, 'US', ?, ?)
    """, (lcms_hq_id, district_name, states_str, f"LCMS district covering {states_str}", now))
    district_created += 1

db.commit()
print(f"Created {synod_created} ELCA synods and {district_created} LCMS districts")

# ── 3. Get the hierarchy IDs we just created ──
elca_synod_ids = {}
cur.execute("SELECT id, name FROM lutheran_hierarchy WHERE parent_id = ? AND lutheran_type = 'synod'", (elca_hq_id,))
for r in cur.fetchall():
    elca_synod_ids[r[1]] = r[0]

lcms_district_ids = {}
cur.execute("SELECT id, name FROM lutheran_hierarchy WHERE parent_id = ? AND lutheran_type = 'district'", (lcms_hq_id,))
for r in cur.fetchall():
    lcms_district_ids[r[1]] = r[0]

print(f"  Synods in DB: {len(elca_synod_ids)}, Districts in DB: {len(lcms_district_ids)}")

# ── 4. Re-link congregations: find each church's synod/district by state ──
# ELCA: re-link congregations from HQ to synod
cur.execute("""
    SELECT lh.id, lh.church_id, c.state
    FROM lutheran_hierarchy lh
    JOIN churches c ON c.id = lh.church_id
    WHERE lh.body = 'ELCA' AND lh.lutheran_type = 'congregation' AND lh.parent_id = ?
""", (elca_hq_id,))
elca_congs = cur.fetchall()
print(f"\nELCA congregations linked to HQ: {len(elca_congs)}")

relinked_elca = 0
for h_id, church_id, state in elca_congs:
    if not state:
        continue
    # Find which synod covers this state
    for synod_name, info in elca_synod_states.items():
        if state in info["states"] or info["states"][0] == "*":
            synod_h_id = elca_synod_ids.get(synod_name)
            if synod_h_id:
                cur.execute("UPDATE lutheran_hierarchy SET parent_id = ? WHERE id = ?", (synod_h_id, h_id))
                relinked_elca += 1
                break

# LCMS: re-link congregations from HQ to district
cur.execute("""
    SELECT lh.id, lh.church_id, c.state
    FROM lutheran_hierarchy lh
    JOIN churches c ON c.id = lh.church_id
    WHERE lh.body = 'LCMS' AND lh.lutheran_type = 'congregation' AND lh.parent_id = ?
""", (lcms_hq_id,))
lcms_congs = cur.fetchall()
print(f"LCMS congregations linked to HQ: {len(lcms_congs)}")

relinked_lcms = 0
for h_id, church_id, state in lcms_congs:
    if not state:
        continue
    for district_name, info in lcms_district_states.items():
        if state in info["states"] or info["states"][0] == "*":
            dist_h_id = lcms_district_ids.get(district_name)
            if dist_h_id:
                cur.execute("UPDATE lutheran_hierarchy SET parent_id = ? WHERE id = ?", (dist_h_id, h_id))
                relinked_lcms += 1
                break

db.commit()
print(f"  Re-linked {relinked_elca} ELCA congregations to synods")
print(f"  Re-linked {relinked_lcms} LCMS congregations to districts")

# ── 5. Summary ──
cur.execute("""
    SELECT lh.body, lh.lutheran_type, COUNT(*) 
    FROM lutheran_hierarchy lh
    GROUP BY lh.body, lh.lutheran_type
    ORDER BY lh.body, lh.lutheran_type
""")
print(f"\nFinal hierarchy summary:")
for r in cur.fetchall():
    print(f"  {r[0]:6s} {r[1]:15s} {r[2]}")

# ── 6. Provenance ──
cur.execute("""
    INSERT INTO provenance_log
    (source, script_name, started_at, completed_at, churches_updated,
     records_attempted, status, notes, parameters)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "lutheran_hierarchy", "build_synod_district_hierarchy",
    now, datetime.now(timezone.utc).isoformat(),
    relinked_elca + relinked_lcms,
    synod_created + district_created,
    "completed",
    f"Added {synod_created} ELCA synods and {district_created} LCMS districts to lutheran_hierarchy. "
    f"Re-linked {relinked_elca} ELCA congregations to synods and {relinked_lcms} LCMS congregations to districts by state.",
    json.dumps({"elca_synods": synod_created, "lcms_districts": district_created, 
                "relinked_elca": relinked_elca, "relinked_lcms": relinked_lcms})
))

db.commit()
db.close()

print(f"\n{'='*50}")
print(f"Lutheran synod/district hierarchy complete!")
print(f"{'='*50}")
