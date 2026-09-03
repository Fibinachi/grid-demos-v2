"""Revert St./Saint → Non-Denom and fix Vineyard."""
import sqlite3
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()
total = 0

# 1. Revert St./Saint → Non-Denom
c.execute("""UPDATE churches SET denomination=NULL WHERE denomination='Non-Denominational'
AND (LOWER(name) LIKE '%st. %' OR LOWER(name) LIKE '%st %' OR LOWER(name) LIKE '%saint%')
AND LOWER(name) LIKE '%church%'""")
print(f"Reverted St./Saint: {c.rowcount}")
total += c.rowcount

# 2. Fix Vineyard → own denomination
c.execute("""UPDATE churches SET denomination='Vineyard' WHERE denomination='Non-Denominational'
AND LOWER(name) LIKE '%vineyard%'""")
print(f"Vineyard → Vineyard: {c.rowcount}")
total += c.rowcount

# 3. Check for any remaining Saint + Non-Denom
c.execute("""SELECT COUNT(*) FROM churches WHERE denomination='Non-Denominational'
AND (LOWER(name) LIKE '%st. %' OR LOWER(name) LIKE '%saint%')""")
print(f"Remaining Saint + Non-Denom: {c.fetchone()[0]}")

conn.commit()

# 4. Verify Saint churches are now properly distributed
c.execute("""SELECT denomination, COUNT(*) FROM churches 
WHERE LOWER(name) LIKE '%saint%church%' 
GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 8""")
print("\nSaint churches by denomination:")
for denom, cnt in c.fetchall():
    print(f"  {str(denom or 'NULL'):<30} {cnt:>8,}")

# 5. Also tag Vineyard churches that aren't yet tagged
c.execute("""UPDATE churches SET denomination='Vineyard'
WHERE faith='Christian' AND (denomination IS NULL OR denomination='')
AND LOWER(name) LIKE '%vineyard%' AND LOWER(name) LIKE '%church%'""")
print(f"Vineyard NULL denom fix: {c.rowcount}")
total += c.rowcount
conn.commit()

print(f"\nTotal fixes: {total}")
conn.close()
