"""
Phase G: Fix remaining stragglers regardless of faith_tradition
=============================================================

The earlier phases filtered by faith_tradition='Judaism', but many surviving
entries have faith_tradition='Reform' (because they have 'Temple' in the name)
or other values. This phase catches ALL remaining Christian-keyword entries.
"""

import sqlite3

DB = r'E:\grid\churches.db'

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    total = 0

    # Patterns that are slam dunks — these are Christian denomination keywords
    # regardless of faith_tradition
    patterns = [
        'baptist', 'methodist', 'lutheran', 'presbyterian', 'episcopal',
        'pentecostal', 'congregational', 'iglesia', 'eglis', 'kirche',
        'catholic', 'cathedral', 'monastery', 'abbey', 'convent',
        'nunnery', 'rosary', 'jesuit',
    ]
    
    # Check what we'd hit
    for pattern in patterns:
        cur.execute("""
            SELECT COUNT(*) FROM churches
            WHERE faith='Jewish'
            AND landmark_type IN ('synagogue', 'church')
            AND (name LIKE ? OR name LIKE ?)
        """, (f'%{pattern}%', f'%{pattern.upper()}%'))
        cnt = cur.fetchone()[0]
        if cnt:
            print(f"  '{pattern}': {cnt}")
    
    # Also Iglesia patterns with "Cristiana" (Christian)
    for pattern in ['cristiana', 'cristiano']:
        cur.execute("""
            SELECT COUNT(*) FROM churches
            WHERE faith='Jewish'
            AND landmark_type IN ('synagogue', 'church')
            AND (name LIKE ? OR name LIKE ?)
        """, (f'%{pattern}%', f'%{pattern.upper()}%'))
        cnt = cur.fetchone()[0]
        if cnt:
            print(f"  '{pattern}': {cnt}")
    
    # Now do the actual update — catch ALL patterns at once
    all_conditions = []
    all_params = []
    
    for pattern in patterns:
        all_conditions.append("(name LIKE ? OR name LIKE ?)")
        all_params.extend([f'%{pattern}%', f'%{pattern.upper()}%'])
    
    for pattern in ['cristiana', 'cristiano']:
        all_conditions.append("(name LIKE ? OR name LIKE ?)")
        all_params.extend([f'%{pattern}%', f'%{pattern.upper()}%'])
    
    where_clause = ' OR '.join(all_conditions)
    
    sql = f"""
        UPDATE churches SET faith='Christian', faith_tradition=NULL
        WHERE faith='Jewish'
        AND landmark_type IN ('synagogue', 'church')
        AND ({where_clause})
    """
    
    cur.execute(sql, all_params)
    conn.commit()
    total = cur.rowcount
    print(f"\n  Fixed: {total}")
    
    print(f"\n{'='*60}")
    
    # Verify what's left
    c2 = sqlite3.connect(DB)
    cur2 = c2.cursor()
    
    jewish = cur2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]
    print(f"\n  Jewish total now: {jewish:,}")
    
    # Check remaining Christian keywords
    remaining = 0
    for pattern in patterns:
        cnt = cur2.execute("""
            SELECT COUNT(*) FROM churches WHERE faith='Jewish'
            AND landmark_type='synagogue'
            AND (name LIKE ? OR name LIKE ?)
        """, (f'%{pattern}%', f'%{pattern.upper()}%')).fetchone()[0]
        remaining += cnt
        if cnt:
            print(f"  REMAINING '{pattern}': {cnt}")
    
    # Also check "Temple" in name + lm=synagogue — how many are left
    temple_cnt = cur2.execute("""
        SELECT COUNT(*) FROM churches WHERE faith='Jewish'
        AND landmark_type='synagogue'
        AND name LIKE '%temple%'
    """).fetchone()[0]
    temple_church = cur2.execute("""
        SELECT COUNT(*) FROM churches WHERE faith='Jewish'
        AND landmark_type='synagogue'
        AND name LIKE '%temple%'
        AND (name LIKE '%church%' OR name LIKE '%baptist%' OR name LIKE '%methodist%'
             OR name LIKE '%christ%' OR name LIKE '%presbyterian%')
    """).fetchone()[0]
    print(f"\n  Remaining 'temple' + lm=synagogue: {temple_cnt}")
    print(f"  Of which temple + Christian keyword: {temple_church}")
    
    c2.close()
    conn.close()

if __name__ == '__main__':
    main()
