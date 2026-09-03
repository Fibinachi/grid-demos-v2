"""
Phase H: Final sweep — catch remaining Christian entries regardless of landmark_type
=============================================================================

Earlier phases filtered by landmark_type IN ('synagogue', 'church'), but
many entries have NULL landmark_type (from IRS, lcms_scraper, overture, etc.)
and were missed. This catches all remaining clearly Christian patterns.
"""

import sqlite3

DB = r'E:\grid\churches.db'

patterns = [
    # Denomination name keywords
    'lutheran', 'methodist', 'baptist', 'presbyterian', 'episcopal',
    'pentecostal', 'congregational', 'iglesia', 'eglis', 'kirche',
    'catholic', 'cathedral', 'monastery', 'abbey', 'convent',
    'nunnery', 'rosary', 'jesuit',
    # Christian theological/school terms
    'theological', 'seminary', 'evangelical',
    # Specific Christian orgs
    'our lady',
    'concordia',
    # Christian publishers
    'apostolic publisher',
    'herald publishing',
    'voice of truth',
    'new life publishing',
    # Christian institutes
    'ankerberg theological',
    'cason theological',
]

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    total = 0
    
    print("Phase H: Final Christian keyword sweep (all landmark types)")
    
    for kw in patterns:
        cur.execute("""
            SELECT COUNT(*) FROM churches
            WHERE faith='Jewish'
            AND (name LIKE ? OR name LIKE ?)
        """, (f'%{kw}%', f'%{kw.upper()}%'))
        cnt = cur.fetchone()[0]
        if cnt:
            print(f"  '{kw}': {cnt}")
    
    # Build combined update
    all_conditions = []
    all_params = []
    
    for kw in patterns:
        all_conditions.append("(name LIKE ? OR name LIKE ?)")
        all_params.extend([f'%{kw}%', f'%{kw.upper()}%'])
    
    where_clause = ' OR '.join(all_conditions)
    
    sql = f"""
        UPDATE churches SET faith='Christian', faith_tradition=NULL
        WHERE faith='Jewish'
        AND ({where_clause})
    """
    
    cur.execute(sql, all_params)
    conn.commit()
    total = cur.rowcount
    
    print(f"\n  Fixed: {total}")
    
    # Verify
    c2 = sqlite3.connect(DB)
    cur2 = c2.cursor()
    jewish = cur2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]
    print(f"  Jewish total now: {jewish:,}")
    
    # Check remaining
    for kw in patterns[:10]:
        cnt = cur2.execute("""
            SELECT COUNT(*) FROM churches WHERE faith='Jewish'
            AND (name LIKE ? OR name LIKE ?)
        """, (f'%{kw}%', f'%{kw.upper()}%')).fetchone()[0]
        if cnt:
            print(f"  REMAINING '{kw}': {cnt}")
    
    c2.close()
    conn.close()

if __name__ == '__main__':
    main()
