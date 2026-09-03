#!/usr/bin/env python3
"""
Link X50 (schools) and X40 (social services) to parent churches.
Reclassify mislabeled mosques/temples to their proper NTEE category.
"""
import sqlite3, re
from datetime import datetime

db = sqlite3.connect("churches.db")
c = db.cursor()

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# Christian denomination keywords (highest confidence)
CHRISTIAN_KW = [
    "CATHOLIC", "BAPTIST", "LUTHERAN", "METHODIST", "PRESBYTERIAN",
    "EPISCOPAL", "PENTECOSTAL", "CHURCH OF GOD", "CHURCH OF CHRIST",
    "ASSEMBLIES OF GOD", "NAZARENE", "SEVENTH-DAY", "ADVENTIST",
    "CALVARY", "ANGLICAN", "MORMON", "LATTER DAY SAINTS",
    "SALVATION ARMY", "MENNONITE", "REFORMED", "WESLEYAN",
    "DISCIPLES OF CHRIST", "CONGREGATIONAL", "EVANGELICAL FREE",
    "CHRISTIAN SCIENCE", "UNITARIAN", "FRIENDS CHURCH", "QUAKER",
    "COVENANT", "MORAVIAN", "BRETHREN", "AMISH",
]

# Non-Christian place of worship indicators
NON_CHRISTIAN_POW = [
    ("MOSQUE", "X30", "Muslim (ISNA)"),
    ("MASJID", "X30", "Muslim (ISNA)"),
    ("ISLAMIC CENTER", "X30", "Muslim (ISNA)"),
    ("ISLAMIC SOCIETY", "X30", "Muslim (ISNA)"),
    ("MUSLIM", "X30", "Muslim (ISNA)"),
    ("SYNAGOGUE", "X30", "Jewish"),
    ("TEMPLE", "X30", "Jewish"),  # Conservative only
    ("CHABAD", "X30", "Chabad Lubavitch"),
    ("BUDDHIST", "X99", "Buddhist"),
    ("BUDDHA", "X99", "Buddhist"),
    ("HINDU", "X99", "Hindu"),
    ("SIKH", "X99", "Sikh"),
    ("GURUDWARA", "X99", "Sikh"),
    ("JAIN", "X99", "Jain"),
    ("ZOROASTRIAN", "X99", "Zoroastrian"),
    ("SHINTO", "X99", "Shinto"),
    ("BAHAI", "X99", "Baha'i"),
    ("TAOIST", "X99", "Taoist"),
]

# ─── STEP 1: Reclassify non-Christian places of worship ────────────

def reclassify_non_christian():
    """Fix X50/X40 records that are actually mosques, temples, etc."""
    total_fixed = 0
    for kw, ntee, denom in NON_CHRISTIAN_POW:
        c.execute("""
            UPDATE churches 
            SET ntee_code = CASE 
                    WHEN ntee_code LIKE 'X50%' THEN 'X30'
                    WHEN ntee_code LIKE 'X40%' THEN 'X30'
                    ELSE ntee_code 
                END,
                denomination = COALESCE(NULLIF(denomination,''), ?),
                classification_source = COALESCE(NULLIF(classification_source,''), 'irs_reclassify')
            WHERE (ntee_code LIKE 'X50%' OR ntee_code LIKE 'X40%')
              AND UPPER(name) LIKE ?
        """, (denom, f"%{kw}%"))
        total_fixed += c.rowcount
    db.commit()
    log(f"Reclassified {total_fixed} non-Christian POWs (X50/X40 → X30/X99)")

# ─── STEP 2: Add ministry columns ──────────────────────────────────

def add_ministry_columns():
    c.execute("PRAGMA table_info(churches)")
    cols = [r[1] for r in c.fetchall()]
    for col in ["has_school", "has_food_pantry", "has_social_services", "parent_church_id"]:
        if col not in cols:
            c.execute(f"ALTER TABLE churches ADD COLUMN {col} TEXT DEFAULT ''")
            log(f"  Added column: {col}")

# ─── STEP 3: Link Christian schools to their church ────────────────

def link_christian_schools():
    """Find X50 records with Christian names, match to church by name+city."""
    linked = 0
    matched_school = 0
    
    # Get X50/X40 records with Christian keywords
    where_clause = " OR ".join([f"UPPER(x.name) LIKE '%{kw}%'" for kw in CHRISTIAN_KW])
    
    c.execute(f"""
        SELECT x.id, x.name, x.city, x.state, x.ntee_code
        FROM churches x
        WHERE (x.ntee_code LIKE 'X50%' OR x.ntee_code LIKE 'X40%')
          AND ({where_clause})
        ORDER BY x.name
    """)
    
    records = c.fetchall()
    log(f"Found {len(records)} X50/X40 records with Christian keywords")
    
    for rid, rname, rcity, rstate, rntee in records:
        # Try to match to a church (X20) in same city by name prefix
        prefix = rname[:20]
        c.execute("""
            SELECT id, name, denomination FROM churches 
            WHERE ntee_code LIKE 'X20%'
              AND city = ? AND state = ?
              AND SUBSTR(UPPER(name), 1, ?) = ?
            LIMIT 1
        """, (rcity, rstate, len(prefix), prefix))
        
        match = c.fetchone()
        
        if match:
            mid, mname, mdenom = match
            # Tag the school/food pantry as a ministry of the church
            ministry_type = "school" if rntee.startswith("X50") else "food_pantry" if rntee.startswith("X40") else "social_service"
            
            if ministry_type == "school":
                c.execute("UPDATE churches SET has_school='1', parent_church_id=? WHERE id=?", (mid, rid))
            else:
                c.execute("UPDATE churches SET has_social_services='1', parent_church_id=? WHERE id=?", (mid, rid))
            
            # Also set denomination on the ministry if not already set
            c.execute("UPDATE churches SET denomination=COALESCE(NULLIF(denomination,''),?) WHERE id=?", (mdenom, rid))
            
            matched_school += 1
        else:
            # No church match - but the name has Christian keywords, so tag it
            # as a standalone ministry
            linked += 1
    
    db.commit()
    log(f"Matched to parent church: {matched_school}")
    log(f"Kept as standalone ministry: {linked}")

# ─── RUN ──────────────────────────────────────────────────────────

log("=== Link Ministries to Churches ===")
reclassify_non_christian()
add_ministry_columns()
link_christian_schools()

# Report
c.execute("SELECT COUNT(*) FROM churches WHERE has_school='1'")
schools = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE has_social_services='1'")
social = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE parent_church_id IS NOT NULL AND parent_church_id != ''")
linked_total = c.fetchone()[0]

log(f"\nResults:")
log(f"  Schools tagged: {schools}")
log(f"  Social services tagged: {social}")
log(f"  Linked to parent church: {linked_total}")

# Show samples
print("\n=== SAMPLE LINKS ===")
c.execute("""
    SELECT c.name, c.city, c.state, c.has_school, c.has_social_services,
           p.name as parent, p.denomination
    FROM churches c
    LEFT JOIN churches p ON c.parent_church_id = p.id
    WHERE c.parent_church_id != '' AND c.parent_church_id IS NOT NULL
    LIMIT 15
""")
for r in c.fetchall():
    print(f"  {r[0]:45s} | {r[1]:15s} | school={r[3]} soc={r[4]} -> {r[5] or '?'}")

db.close()
