"""Restore Jewish cemeteries that were incorrectly moved."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Find any cemetery entries that were moved out of Judaism
print("=== Cemetery entries no longer in Judaism ===")
c.execute("""
    SELECT id, name, faith, tradition, country, city
    FROM churches 
    WHERE LOWER(COALESCE(name,'')) LIKE '%cemetery%'
      AND faith != 'Judaism'
      AND (faith = 'Other' OR faith = 'Christian')
    ORDER BY country, name
""")
rows = c.fetchall()
print(f"Found {len(rows)}")
for r in rows:
    print(f"  {r[0]:>8d} | {str(r[1] or '')[:55]:55s} | {r[2]:15s} | {str(r[3] or ''):25s} | {r[4] or '?':10s} | {r[5] or '?'}")

# Restore all cemeteries that were previously Jewish back to Judaism
# Check if any have Hebrew/Jewish names
jewish_cemetery_keywords = ['bet olam', 'beth olam', 'beit olam', 'chebra', 'chevra',
                            'gemiluth', 'chesed shel emes', 'shomrei', 'agudath',
                            'jewish cemetery', 'hebrew cemetery', 'israel cemetery',
                            'zion cemetery', 'synagogue cemetery', 'beth israel',
                            'b\'nai', 'bnai', 'bnei', 'rabb', 'talmud']

restored = 0
for r in rows:
    nl = (r[1] or '').lower()
    is_jewish = False
    for kw in jewish_cemetery_keywords:
        if kw in nl:
            is_jewish = True
            break
    
    if is_jewish or r[2] == 'Judaism':
        c.execute("UPDATE churches SET faith='Judaism', tradition='Rabbinic', last_updated=datetime('now') WHERE id=?", (r[0],))
        restored += 1
        print(f"  RESTORED: {r[0]}")

if not restored:
    print("  All cemetery entries are already correctly classified")

conn.commit()

# Also check if 'cemetery' + 'jewish' pattern is already covered
print("\n=== Cemetery entries still in Judaism ===")
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE LOWER(COALESCE(name,'')) LIKE '%cemetery%'
      AND faith='Judaism'
""")
print(f"  {c.fetchone()[0]}")

conn.close()
