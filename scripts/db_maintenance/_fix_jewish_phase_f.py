"""
Phase F: Fix remaining entries with slam-dunk Christian names
=============================================================

F1: lm=synagogue + Christian denomination keywords in name (no denom signal needed)
    e.g., "CALVARY BAPTIST CHURCH", "GOOD SHEPHERD UNITED METHODIST CHURCH",
          "FIRST CONGREGATIONAL CHURCH", "IGLESIA BAUTISTA NOROESTE"

    Patterns: %baptist%, %methodist%, %lutheran%, %presbyterian%, %episcopal%,
              %pentecostal%, %congregational%, %iglesia%, %eglis%, %kirche%,
              %catholic%, %cathedral%, %monastery%, %abbey%, %convent%,
              %nunnery%, %rosary%

    Also: %unit church% (not universalist) — "Unit Church Of Staten Island"

F2: lm=church — entries with ambiguous names but clearly Christian orgs
    (convent, abbey, rosary, monastery, etc.)

F3: Generic Christian org names — "BELIEVERS IN RECOVERY", "WOMEN TOGETHER",
    "A SHEPHERDS LIFE 7 INC", "LOVE INC OF ..." etc. — these have lm=church
    so they came from IRS/holy_sites pipeline. Name doesn't prove faith alone,
    so skip unless lm=church + Christian keyword.
"""

import sqlite3

DB = r'E:\grid\churches.db'

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    total = 0

    # Denomination keyword patterns for F1
    denom_patterns = [
        ('baptist', 'Baptist'),
        ('methodist', 'Methodist'),
        ('lutheran', 'Lutheran'),
        ('presbyterian', 'Presbyterian'),
        ('episcopal', 'Episcopal'),
        ('pentecostal', 'Pentecostal'),
        ('congregational', 'Congregational'),
        ('iglesia', 'Iglesia (Spanish church)'),
        ('eglis', 'Église (French church)'),
        ('kirche', 'Kirche (German church)'),
        ('catholic', 'Catholic'),
        ('cathedral', 'Cathedral'),
        ('monastery', 'Monastery'),
        ('abbey', 'Abbey'),
        ('convent', 'Convent'),
        ('nunnery', 'Nunnery'),
        ('rosary', 'Rosary'),
        ('jesuit', 'Jesuit'),
    ]

    for pattern, label in denom_patterns:
        cur.execute("""
            SELECT rowid, name FROM churches
            WHERE faith='Jewish' AND faith_tradition='Judaism'
            AND landmark_type IN ('synagogue', 'church')
            AND (name LIKE ? OR name LIKE ?)
            ORDER BY rowid
        """, (f'%{pattern}%', f'%{pattern.upper()}%'))
        rows = cur.fetchall()
        if rows:
            print(f"  lm in (synagogue,church) + '{pattern}': {len(rows)}")
            # Update
            cur.execute("""
                UPDATE churches SET faith='Christian', faith_tradition=NULL
                WHERE faith='Jewish' AND faith_tradition='Judaism'
                AND landmark_type IN ('synagogue', 'church')
                AND (name LIKE ? OR name LIKE ?)
            """, (f'%{pattern}%', f'%{pattern.upper()}%'))
            conn.commit()
            total += len(rows)

    # F1b: "Unit" in name + lm=synagogue (NOT Unitarian)
    cur.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith='Jewish' AND faith_tradition='Judaism'
        AND landmark_type='synagogue'
        AND name LIKE '%Unit %' AND name NOT LIKE '%Unitarian%'
    """)
    cnt = cur.fetchone()[0]
    if cnt:
        print(f"  lm=synagogue + 'Unit' (not Unitarian): {cnt}")
        cur.execute("""
            UPDATE churches SET faith='Christian', faith_tradition=NULL
            WHERE faith='Jewish' AND faith_tradition='Judaism'
            AND landmark_type='synagogue'
            AND name LIKE '%Unit %' AND name NOT LIKE '%Unitarian%'
        """)
        conn.commit()
        total += cnt

    # F2: lm=church + Christian org keywords (convent/nunnery/abbey/rosary/jesuit)
    # These have no denom signal but the keywords are slam dunks
    christian_org_kw = ['convent', 'nunnery', 'abbey', 'rosary', 'jesuit',
                        'monastery', 'cathedral']
    for kw in christian_org_kw:
        cur.execute("""
            SELECT COUNT(*) FROM churches
            WHERE faith='Jewish' AND faith_tradition='Judaism'
            AND landmark_type='church'
            AND (name LIKE ? OR name LIKE ?)
        """, (f'%{kw}%', f'%{kw.upper()}%'))
        cnt = cur.fetchone()[0]
        if cnt:
            print(f"  lm=church + '{kw}': {cnt}")
            cur.execute("""
                UPDATE churches SET faith='Christian', faith_tradition=NULL
                WHERE faith='Jewish' AND faith_tradition='Judaism'
                AND landmark_type='church'
                AND (name LIKE ? OR name LIKE ?)
            """, (f'%{kw}%', f'%{kw.upper()}%'))
            conn.commit()
            total += cnt

    print(f"\n{'='*60}")
    print(f"Total fixed: {total}")

    # Verify
    c2 = sqlite3.connect(DB)
    cur2 = c2.cursor()
    jewish = cur2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]
    print(f"\n  Jewish total now: {jewish:,}")
    
    # Check remaining lm=synagogue + denom keyword patterns
    for pattern, label in denom_patterns:
        cnt = cur2.execute("""
            SELECT COUNT(*) FROM churches WHERE faith='Jewish'
            AND landmark_type='synagogue'
            AND (name LIKE ? OR name LIKE ?)
        """, (f'%{pattern}%', f'%{pattern.upper()}%')).fetchone()[0]
        if cnt:
            print(f"  REMAINING: {label} + lm=synagogue: {cnt}")
    
    c2.close()
    conn.close()

if __name__ == '__main__':
    main()
