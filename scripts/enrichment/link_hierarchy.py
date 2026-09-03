"""
Church Hierarchy Linking — Link X50 schools and X40 food pantries to parent churches
Only links clear cases where the school/pantry name derives from a church name.
"""
import sqlite3, re

DB = "churches.db"

def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# Suffix patterns that CLEARLY indicate a school/pantry attached to a church
SCHOOL_SUFFIXES = [
    r'\s+CATHOLIC\s+(SCHOOL|ACADEMY|PRESCHOOL|ELEMENTARY)$',
    r'\s+CHRISTIAN\s+(SCHOOL|ACADEMY|PRESCHOOL)$',
    r'\s+BAPTIST\s+(SCHOOL|ACADEMY|PRESCHOOL|DAYCARE)$',
    r'\s+LUTHERAN\s+(SCHOOL|ACADEMY|PRESCHOOL)$',
    r'\s+METHODIST\s+(SCHOOL|ACADEMY|PRESCHOOL)$',
    r'\s+EPISCOPAL\s+(SCHOOL|ACADEMY|PRESCHOOL)$',
    r'\s+PENTECOSTAL\s+(SCHOOL|ACADEMY)$',
    r'\s+PRESBYTERIAN\s+(SCHOOL|ACADEMY)$',
    r'\s+ADVENTIST\s+(SCHOOL|ACADEMY)$',
    r'\s+MENNONITE\s+(SCHOOL)$',
    r'\s+FOOD\s+(PANTRY|BANK|CLOSET)$',
    r'\s+COMMUNITY\s+FOOD\s+(PANTRY|BANK)$',
]

def church_suffix(name):
    """If name ends with a church school/pantry pattern, return the church name stem"""
    if not name:
        return None
    n = name.upper().strip()
    for pattern in SCHOOL_SUFFIXES:
        match = re.search(pattern, n)
        if match:
            stem = n[:match.start()].strip()
            if stem:
                return stem
    return None

def link_ntee(ntee_code, label):
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("SELECT id, name, city, state FROM churches WHERE ntee_code=? AND (parent_church_id IS NULL OR parent_church_id='')", (ntee_code,))
    children = cur.fetchall()
    print(f"\n{label} ({ntee_code}): {len(children)} to check")
    
    linked = 0
    for child in children:
        stem = church_suffix(child["name"])
        if not stem:
            continue
        
        # Try to find a church in the same city+state with the stem name
        cur.execute("""
            SELECT id, name FROM churches 
            WHERE UPPER(name) LIKE ? 
              AND city = ? 
              AND state = ? 
              AND id != ?
              AND (ntee_code IS NULL OR ntee_code NOT IN ('X50','X40'))
            ORDER BY 
              CASE 
                WHEN UPPER(name) LIKE '%CHURCH%' THEN 1
                WHEN UPPER(name) LIKE '%PARISH%' THEN 2
                ELSE 3
              END
            LIMIT 1
        """, (f"%{stem}%", child["city"], child["state"], child["id"]))
        
        parent = cur.fetchone()
        if parent:
            cur.execute("UPDATE churches SET parent_church_id=? WHERE id=?", (parent["id"], child["id"]))
            linked += 1
            if linked <= 15 or linked % 50 == 0:
                print(f"  {child['name'][:50]:50s} -> {parent['name'][:50]}")
    
    conn.commit()
    conn.close()
    print(f"  Linked: {linked}")
    return linked

# Main
total = 0
total += link_ntee("X50", "Schools")
total += link_ntee("X40", "Food Pantries")

print(f"\n=== TOTAL LINKED: {total} ===")
