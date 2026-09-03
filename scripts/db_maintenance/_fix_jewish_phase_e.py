"""
Phase E: Broader cleanup of remaining Christian entries in Judaism pool
=====================================================================

E1: Baháʼí Temple denomination (2) → Baháʼí faith
E2: Christian/AME denom + Christian keyword in name + lm=synagogue → Christian
E3: YMCA entries → Christian (service org, nominally Christian)
E4: School/Christian in name → Christian
"""

import sqlite3

DB = r'E:\grid\churches.db'

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    total = 0

    # E1: Baháʼí Temple
    print("--- E1: Baháʼí Temple denomination → Baháʼí faith ---")
    cur.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith='Jewish' AND denomination LIKE 'Bah\u00e1\u02bc\u00ed%'
    """)
    cnt = cur.fetchone()[0]
    if cnt:
        print(f"  Found: {cnt}")
        cur.execute("""
            UPDATE churches SET faith='Bah\u00e1\u02bc\u00ed', faith_tradition=NULL
            WHERE faith='Jewish' AND denomination LIKE 'Bah\u00e1\u02bc\u00ed%'
        """)
        conn.commit()
        print(f"  Fixed: {cnt}")
    else:
        print("  None found")
    total += cnt

    # E2: Christian/AME denom + Christian keyword + lm=synagogue
    print("\n--- E2: Christian denom + Christian name + lm=synagogue → Christian ---")
    cur.execute("""
        SELECT rowid, name, denomination FROM churches
        WHERE faith='Jewish'
        AND landmark_type='synagogue'
        AND denomination IN ('Christian', 'AME', 'Apostolic Church')
        AND (name LIKE '%christ%' OR name LIKE '%jesus%' OR name LIKE '%church%'
             OR name LIKE '%apostolic%' OR name LIKE '%young men%')
        ORDER BY denomination
    """)
    rows = cur.fetchall()
    print(f"  Found: {len(rows)}")
    for r in rows:
        print(f"    rowid={str(r[0]):>7}  {str(r[1] or '')[:55]:55s}  {str(r[2] or '')[:25]:25s}")
    
    if rows:
        cur.execute("""
            UPDATE churches SET faith='Christian', faith_tradition=NULL
            WHERE faith='Jewish'
            AND landmark_type='synagogue'
            AND denomination IN ('Christian', 'AME', 'Apostolic Church')
            AND (name LIKE '%christ%' OR name LIKE '%jesus%' OR name LIKE '%church%'
                 OR name LIKE '%apostolic%' OR name LIKE '%young men%')
        """)
        conn.commit()
        print(f"  Fixed: {len(rows)}")
    total += len(rows)

    # E3: YMCA (catch any remaining)
    print("\n--- E3: YMCA entries → Christian ---")
    cur.execute("""
        SELECT COUNT(*) FROM churches WHERE faith='Jewish'
        AND name LIKE '%YOUNG MENS CHRISTIAN%'
    """)
    cnt = cur.fetchone()[0]
    if cnt > len([r for r in rows if 'YOUNG' in str(r[1] or '').upper()]):
        # Some not caught by E2
        cur.execute("""
            UPDATE churches SET faith='Christian', faith_tradition=NULL
            WHERE faith='Jewish' AND name LIKE '%YOUNG MENS CHRISTIAN%'
        """)
        conn.commit()
        print(f"  Fixed: {cnt}")
        total += cnt
    else:
        print("  (already covered by E2)")

    # Summary
    print(f"\n{'='*60}")
    print(f"Total fixed: {total}")

    # Verify
    c2 = sqlite3.connect(DB)
    cur2 = c2.cursor()
    jewish = cur2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]
    bahai = cur2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND denomination LIKE 'Bah%'").fetchone()[0]
    christian = cur2.execute("""
        SELECT COUNT(*) FROM churches WHERE faith='Jewish'
        AND landmark_type='synagogue'
        AND denomination IN ('Christian', 'AME', 'Apostolic Church')
        AND (name LIKE '%christ%' OR name LIKE '%jesus%' OR name LIKE '%church%'
             OR name LIKE '%apostolic%' OR name LIKE '%young men%')
    """).fetchone()[0]
    ymca = cur2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND name LIKE '%YOUNG MENS CHRISTIAN%'").fetchone()[0]
    
    print(f"\n  Jewish total: {jewish:,}")
    print(f"  Bah denom still Jewish: {bahai}")
    print(f"  Christian-name+denom+synagogue still Jewish: {christian}")
    print(f"  YMCA still Jewish: {ymca}")
    c2.close()
    conn.close()

if __name__ == '__main__':
    main()
