"""
Phase D: Fix remaining Jewish misclassifications missed by Phase C
=============================================================

D1: Baháʼí denomination entries (24) still tagged faith=Jewish
    → faith=Baháʼí (all have lm=church, clearly not Jewish)
    
D2: Christian denom + Christian name in name + lm=synagogue
    → Christian (entries like "WORD CHRISTIAN CENTER INC", 
       "SHALOM CHRISTIAN FOUNDATION", "COVENANT CHRISTIAN MINISTRY",
       "SHALOM CHRISTIAN CENTER AND ACADEMY INC", "SHALOM CHRISTIAN MISSIONS",
       "ZION CONGREGATION PLAINVIEW CHRISTIAN SCHOOL", 
       "LIFEPOINT CHRISTIAN COMMUNITY OF SAN DIEGO",
       "APOSTOLIC CHURCH OF TRENTON ACTS2")
    Requires BOTH Christian denomination AND Christian keyword in name
    (excludes entries with Hebrew/Yiddish names even if denom=Baptist)
"""

import sqlite3
import sys

DB = r'E:\grid\churches.db'

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    total_changed = 0
    
    # ============= D1: Baháʼí denomination → Baháʼí faith =============
    print("--- D1: Baháʼí denomination → Baháʼí faith ---")
    cur.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith='Jewish' AND faith_tradition='Judaism'
        AND denomination = 'Bah\u00e1\u02bc\u00ed (General)'
    """)
    count_d1 = cur.fetchone()[0]
    print(f"  Baháʼí denom entries in Judaism pool: {count_d1}")
    
    if count_d1 > 0:
        cur.execute("""
            SELECT rowid, name, landmark_type, country FROM churches
            WHERE faith='Jewish' AND faith_tradition='Judaism'
            AND denomination = 'Bah\u00e1\u02bc\u00ed (General)'
            ORDER BY name LIMIT 25
        """)
        print("  Entries to fix:")
        for r in cur.fetchall():
            print(f"    rowid={r[0]:>7}  {str(r[1] or '')[:60]:60s}  lm={str(r[2] or ''):12s}  {r[3]:2s}")
        
        cur.execute("""
            UPDATE churches SET
                faith = 'Bah\u00e1\u02bc\u00ed',
                faith_tradition = NULL
            WHERE faith='Jewish' AND faith_tradition='Judaism'
            AND denomination = 'Bah\u00e1\u02bc\u00ed (General)'
        """)
        conn.commit()
        print(f"  ✅ Fixed: {count_d1} Baháʼí entries → faith=Baháʼí")
    total_changed += count_d1
    
    # ============= D2: Christian denom + Christian name + lm=synagogue → Christian =============
    print("\n--- D2: Christian name + Christian denom + lm=synagogue → Christian ---")
    christian_keywords = [
        'christian', 'christ', 'jesus', 'apostolic',
    ]
    
    conditions = []
    for kw in christian_keywords:
        conditions.append(f"(name LIKE '%{kw}%')")
    
    where_name = ' OR '.join(conditions)
    
    # Christian denominations to match
    christian_denoms = [
        "'Christian'", "'Apostolic Church'", "'Lutheran'",
        "'Community of Christ'", "'Bible Church (unspecified)'",
        "'Congregational'", "'Greek Orthodox'",
        "'Non-Denominational'", "'Non-Denominational / Independent'",
        "'Protestant'", "'Religious Society of Friends (Quakers)'",
    ]
    
    sql_check = f"""
        SELECT rowid, name, denomination, country FROM churches
        WHERE faith='Jewish' AND faith_tradition='Judaism'
        AND landmark_type='synagogue'
        AND denomination IN ({','.join(christian_denoms)})
        AND ({where_name})
        ORDER BY denomination
    """
    
    cur.execute(sql_check)
    rows = cur.fetchall()
    print(f"  Found: {len(rows)} entries")
    for r in rows:
        print(f"    rowid={r[0]:>7}  {str(r[1] or '')[:60]:60s}  denom={str(r[2] or '')[:30]:30s}  {r[3]:2s}")
    
    if len(rows) > 0:
        sql_update = f"""
            UPDATE churches SET
                faith = 'Christian',
                faith_tradition = NULL
            WHERE faith='Jewish' AND faith_tradition='Judaism'
            AND landmark_type='synagogue'
            AND denomination IN ({','.join(christian_denoms)})
            AND ({where_name})
        """
        cur.execute(sql_update)
        conn.commit()
        print(f"  ✅ Fixed: {len(rows)} entries → faith=Christian")
    total_changed += len(rows)
    
    # ============= D3: Apostolic Church (non-Keyword)  + lm=synagogue → Christian =============
    # Catch "APOSTOLIC CHURCH OF TRENTON ACTS2" - the name check already catches it in D2
    # But also catch other Apostolic Church entries with lm=synagogue
    print("\n--- D3: Apostolic Church denom + lm=synagogue → Christian ---")
    cur.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith='Jewish' AND faith_tradition='Judaism'
        AND landmark_type='synagogue'
        AND denomination = 'Apostolic Church'
    """)
    d3_count = cur.fetchone()[0]
    print(f"  Apostolic Church + lm=synagogue: {d3_count}")
    # D2 already catches this if name has keyword, so count remaining
    cur.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith='Jewish' AND faith_tradition='Judaism'
        AND landmark_type='synagogue'
        AND denomination = 'Apostolic Church'
        AND (name IS NULL OR name = '' OR name NOT LIKE '%apostolic%')
    """)
    d3_remaining = cur.fetchone()[0]
    if d3_remaining > 0:
        print(f"  Remaining without 'apostolic' in name: {d3_remaining}")
        cur.execute("""
            SELECT rowid, name, country FROM churches
            WHERE faith='Jewish' AND faith_tradition='Judaism'
            AND landmark_type='synagogue'
            AND denomination = 'Apostolic Church'
            AND (name IS NULL OR name = '' OR name NOT LIKE '%apostolic%')
        """)
        for r in cur.fetchall():
            print(f"    rowid={r[0]:>7}  {str(r[1] or '')[:60]:60s}  {r[2]:2s}")
        
        # These are Jewish-sounding names with denom=Apostolic Church (likely IRS coding error)
        # Keep them as Jewish — the Baptist cases showed this pattern (Hebrew name + wrong denom)
        print(f"  These have Jewish-sounding names, keeping as Jewish (likely IRS coding error)")
        d3_remaining = 0  # Don't count as fix
    else:
        print(f"  (already covered by D2)")
    
    # ============= Summary =============
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"  Total changed: {total_changed}")
    
    # Verify
    for label, denom in [("Baháʼí", "denomination = 'Bah\u00e1\u02bc\u00ed (General)'"),
                          ("Christian denom + Christian name + lm=synagogue", 
                           f"denomination IN ({','.join(christian_denoms)}) AND ({where_name}) AND landmark_type='synagogue'")]:
        pass  # Just for display
    
    conn.close()
    
    # Final verification
    conn2 = sqlite3.connect(DB)
    c2 = conn2.cursor()
    jewish_total = c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]
    bahai_still = c2.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE faith='Jewish' AND denomination LIKE 'Bah%'
    """).fetchone()[0]
    christian_still = c2.execute(f"""
        SELECT COUNT(*) FROM churches WHERE faith='Jewish'
        AND landmark_type='synagogue'
        AND denomination IN ({','.join(christian_denoms)})
        AND ({where_name})
    """).fetchone()[0]
    
    print(f"\n  Jewish total now: {jewish_total:,}")
    print(f"  Baháʼí denom still in Jewish: {bahai_still}")
    print(f"  Christian-name+denom+synagogue still in Jewish: {christian_still}")
    conn2.close()

if __name__ == '__main__':
    main()
